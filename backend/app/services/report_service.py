from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Report
from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics

# ====================== Gemini Integration ======================
try:
    from app.services.gemini_service import GeminiAnalysisService
    from google.genai import types
except ImportError:
    GeminiAnalysisService = None
    types = None

logger = logging.getLogger(__name__)


class ReportService:
    def __init__(self, db: AsyncSession):
        self.db = db
        if GeminiAnalysisService:
            self.gemini = GeminiAnalysisService()
        else:
            self.gemini = None

    @staticmethod
    def _normalize_metric_value(value: Any, default: Any = 0, *, cast_int: bool = False) -> Any:
        """Normalize metric values from Gemini or fallback payloads."""
        if isinstance(value, dict):
            if "value" in value:
                value = value["value"]
            elif "amount" in value:
                value = value["amount"]
            else:
                return default

        if isinstance(value, str):
            cleaned = value.replace(",", "").strip()
            try:
                value = float(cleaned)
            except ValueError:
                return default

        if cast_int:
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _extract_metrics_payload(self, content: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Extract a normalized metrics payload from Gemini or fallback content."""
        if not content:
            return None

        payload = content.get("financial_metrics")
        if isinstance(payload, dict):
            metrics_payload = payload
        else:
            payload = content.get("summary")
            metrics_payload = payload if isinstance(payload, dict) else content

        if not metrics_payload:
            return None

        return {
            "revenue": self._normalize_metric_value(metrics_payload.get("revenue"), 0.0),
            "customers": self._normalize_metric_value(metrics_payload.get("customers"), 0, cast_int=True),
            "cash": self._normalize_metric_value(metrics_payload.get("cash"), 0.0),
            "ebitda": self._normalize_metric_value(metrics_payload.get("ebitda"), 0.0),
            "gross_margin": self._normalize_metric_value(metrics_payload.get("gross_margin"), 0.0),
            "operating_margin": self._normalize_metric_value(metrics_payload.get("operating_margin"), 0.0),
        }

    async def _save_metrics(self, document_id: int, content: Optional[Dict[str, Any]]) -> Optional[FinancialMetrics]:
        """Persist normalized metrics for a document, updating the existing row when present."""
        metrics_payload = self._extract_metrics_payload(content)
        if not metrics_payload:
            return None

        stmt = select(FinancialMetrics).where(FinancialMetrics.document_id == document_id)
        result = await self.db.execute(stmt)
        metrics = result.scalars().first()

        if metrics is None:
            metrics = FinancialMetrics(document_id=document_id)
            self.db.add(metrics)

        for key, value in metrics_payload.items():
            setattr(metrics, key, value)

        metrics.extracted_at = datetime.utcnow()

        await self.db.flush()
        return metrics

    @staticmethod
    def _parse_currency_value(raw_value: Any, default: float = 0.0) -> float:
        """Parse values like 354.8k, 735,189, or 1.1m into floats."""
        if raw_value is None:
            return default

        if isinstance(raw_value, (int, float)):
            return float(raw_value)

        if not isinstance(raw_value, str):
            raw_value = str(raw_value)

        cleaned = raw_value.replace(",", "").replace("€", "").replace("$", "").strip()
        if not cleaned:
            return default

        multiplier = 1.0
        suffix = cleaned[-1].lower() if cleaned else ""
        if suffix in {"k", "m", "b"}:
            multiplier = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}[suffix]
            cleaned = cleaned[:-1]

        try:
            return float(cleaned) * multiplier
        except ValueError:
            return default

    # ============================================================
    # Public API (ALL ASYNC)
    # ============================================================
    async def get_or_create_report(self, document_id: int) -> Report:
        """Get existing report or trigger generation."""
        stmt = select(Report).where(Report.document_id == document_id)
        result = await self.db.execute(stmt)
        report = result.scalars().first()
        
        if report:
            return report
        return await self.generate_report(document_id)

    async def generate_report(self, document_id: int, force: bool = False) -> Report:
        """Generate or regenerate a report for a document."""
        # Fetch document
        doc_stmt = select(Document).where(Document.id == document_id)
        doc_result = await self.db.execute(doc_stmt)
        document = doc_result.scalars().first()
        
        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Check if report already exists
        report_stmt = select(Report).where(Report.document_id == document_id)
        report_result = await self.db.execute(report_stmt)
        existing = report_result.scalars().first()

        if existing and not force:
            if existing.status == "completed":
                return existing
            if existing.status in ("pending", "failed"):
                return await self._generate_with_gemini_or_fallback(document, existing)

        # Create new report record
        report = existing or Report(
            document_id=document_id,
            status="pending",
            version=1 if not existing else (existing.version + 1),
        )

        if not existing:
            self.db.add(report)
            await self.db.commit()
            await self.db.refresh(report)

        return await self._generate_with_gemini_or_fallback(document, report)

    async def get_report(self, report_id: int) -> Optional[Report]:
        """Fetch a report by ID."""
        stmt = select(Report).where(Report.id == report_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def list_reports(self, document_id: Optional[int] = None) -> List[Report]:
        """List reports with optional filtering."""
        query = select(Report)
        if document_id:
            query = query.where(Report.document_id == document_id)
        
        query = query.order_by(Report.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def delete_report(self, report_id: int) -> bool:
        """Delete a report by ID."""
        # Check if exists
        stmt = select(Report).where(Report.id == report_id)
        result = await self.db.execute(stmt)
        report = result.scalars().first()
        
        if not report:
            return False
        
        # Delete it
        delete_stmt = sql_delete(Report).where(Report.id == report_id)
        await self.db.execute(delete_stmt)
        await self.db.commit()
        return True

    # ============================================================
    # Core Generation Logic (ASYNC)
    # ============================================================
    async def _generate_with_gemini_or_fallback(
    self, document: Document, report: Report
) -> Report:
        """Core generation logic – Gemini first, then fallback."""

        report.status = "pending"
        await self.db.commit()

        try:
            # ============================================================
            # Generate content
            # ============================================================
            if self.gemini and self.gemini.is_available() and self.gemini.client:
                content = await self._call_gemini(document)
                report.generation_source = "gemini"
            else:
                content = self._fallback_generation(document)
                report.generation_source = "fallback"

            # ============================================================
            # AI LAYER ONLY (no financial duplication anymore)
            # ============================================================
            report.ai_commentary = content.get("ai_commentary", "")
            report.key_findings = content.get("key_findings", [])
            report.model_version = content.get("model_version", "gemini-2.0-flash")
            report.summary = {
                "company_name": content.get("company_name") or document.filename,
                "reporting_period": content.get("reporting_period") or "unknown",
                "metrics": self._extract_metrics_payload(content) or {},
                "key_findings": content.get("key_findings", []),
                "ai_commentary": content.get("ai_commentary", ""),
                "model_version": content.get("model_version", "gemini-2.0-flash"),
            }

            report.status = "completed"
            try:
                await self._save_metrics(document.id, content)
            except Exception as e:
                logger.warning(f"Failed to save financial metrics: {e}")

        except Exception as e:
            logger.error(f"Report generation failed for doc {document.id}: {e}")

            report.status = "failed"
            report.ai_commentary = f"Generation failed: {str(e)}"
            report.generation_source = "error"

        report.updated_at = datetime.utcnow()

        await self.db.commit()
        await self.db.refresh(report)

        return report

    async def _call_gemini(self, document: Document) -> Dict[str, Any]:
        """Call Gemini to generate report content."""
        if not self.gemini or not self.gemini.client or not types:
            return self._fallback_generation(document)

        prompt = self._build_prompt(document)

        try:
            response = self.gemini.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=1200,
                ),
            )

            return self._parse_gemini_response(response)

        except Exception as e:
            logger.warning(f"Gemini call failed, falling back: {e}")
            
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                if self.gemini:
                    self.gemini._disable_ai_temporarily(60)
            
            return self._fallback_generation(document)

    def _build_prompt(self, document: Document) -> str:
        """Build prompt to extract structured financial data."""
        text = document.extracted_text or ""
        return f"""
    You are a senior financial analyst. Extract ALL financial metrics from this document.

    **Document:** {document.filename}

    **Text:**
    {text[:10000]}

    Return ONLY valid JSON with this EXACT structure:
    {{
    "company_name": "string",
    "reporting_period": "string (e.g., '30 June 2025')",
    "financial_metrics": {{
        "revenue": {{"value": number, "currency": "string", "period": "string"}},
        "gross_profit": {{"value": number, "currency": "string"}},
        "operating_profit": {{"value": number, "currency": "string"}},
        "ebitda": {{"value": number, "currency": "string"}},
        "net_income": {{"value": number, "currency": "string"}},
        "customers": {{"value": number}},
        "cash": {{"value": number, "currency": "string"}},
        "debt": {{"value": number, "currency": "string"}}
    }},
    "key_insights": [
        "insight 1",
        "insight 2",
        "insight 3"
    ],
    "growth_rates": {{
        "revenue_yoy": "percentage string",
        "customer_growth": "percentage string"
    }},
    "ai_commentary": "2-3 sentence executive summary"
    }}
        """.strip()

    def _parse_gemini_response(self, response: Any) -> Dict[str, Any]:
        """Parse Gemini JSON response."""
        import json

        text = getattr(response, "text", "") or ""
        match = re.search(r"\{.*\}", text, re.DOTALL)
        
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                logger.warning("Failed to parse Gemini JSON response")
        
        return self._fallback_generation(None)

    def _fallback_generation(self, document: Optional[Document]) -> Dict[str, Any]:
        """Generate fallback content with proper financial data extraction."""
        if not document:
            return {
                "ai_commentary": "Report generation is currently unavailable.",
                "key_findings": [],
                "summary": {
                    "revenue": 0,
                    "customers": 0,
                    "cash": 0,
                    "ebitda": 0,
                    "gross_margin": 0,
                    "operating_margin": 0,
                },
            }

        text = document.extracted_text or ""
        findings = []
        
        # ============================================================
        # Extract Revenue
        # ============================================================
        revenue = 0.0
        revenue_patterns = [
            r"Group\s+Revenue\s+(?:up\s+[\d.]+%\s+)?to\s+€?([\d,]+(?:\.\d+)?)\s*(k|m|b)?",
            r"Turnover\s+€?([\d,]+(?:\.\d+)?)\s*(k|m|b)?",
            r"(?:Group\s+)?[Rr]evenue[:\s]+€?([\d,]+(?:\.\d+)?)\s*(k|m|b)?",
        ]
        for pattern in revenue_patterns:
            revenue_match = re.search(pattern, text, re.IGNORECASE)
            if revenue_match:
                revenue = self._parse_currency_value(
                    f"{revenue_match.group(1)}{revenue_match.group(2) or ''}"
                )
                if revenue > 0:
                    break
        
        # ============================================================
        # Extract Cash
        # ============================================================
        cash = 0.0
        cash_patterns = [
            r"Cash\s+and\s+cash\s+equivalents\s+€?([\d,]+(?:\.\d+)?)\s*(k|m|b)?",
            r"Cash\s+and\s+bank\s+debt\s+balances\s+were\s+€?([\d,]+(?:\.\d+)?)\s*(k|m|b)?",
            r"[Cc]ash\s+(?:balance|position)[:\s]+€?([\d,]+(?:\.\d+)?)\s*(k|m|b)?",
        ]
        for pattern in cash_patterns:
            cash_match = re.search(pattern, text, re.IGNORECASE)
            if cash_match:
                cash = self._parse_currency_value(
                    f"{cash_match.group(1)}{cash_match.group(2) or ''}"
                )
                if cash > 0:
                    break
        
        # Extract Operating Margin - simpler
        operating_margin = 0.0
        om_match = re.search(r"group\s+operating\s+loss\s+of\s+€?([\d,]+(?:\.\d+)?)\s*(k|m|b)?", text, re.IGNORECASE)
        if om_match:
            loss_val = self._parse_currency_value(
                f"{om_match.group(1)}{om_match.group(2) or ''}"
            )
            if revenue > 0:
                operating_margin = -(loss_val / revenue) * 100
        
        # Extract Gross Margin - simpler
        gross_margin = 0.0
        gm_match = re.search(r"gross\s+margin\s+of\s+([\d.]+)", text, re.IGNORECASE)
        if gm_match:
            try:
                gross_margin = float(gm_match.group(1))
            except (ValueError, IndexError):
                gross_margin = 0.0
        
        # ============================================================
        # Extract EBITDA
        # ============================================================
        ebitda = 0.0
        ebitda_patterns = [
            r"EBITDA[:\s]+€?([\d,]+(?:\.\d+)?)\s*(k|m|b)?",
            r"[Ee]BITDA\s+of\s+€?([\d,]+(?:\.\d+)?)\s*(k|m|b)?",
        ]
        for pattern in ebitda_patterns:
            ebitda_match = re.search(pattern, text, re.IGNORECASE)
            if ebitda_match:
                ebitda = self._parse_currency_value(
                    f"{ebitda_match.group(1)}{ebitda_match.group(2) or ''}"
                )
                if ebitda > 0:
                    break
        
        # Extract Customers - simpler version
        customers = 0
        customers_match = re.search(r"(\d+)\s+customer", text, re.IGNORECASE)
        if customers_match:
            try:
                customers = int(customers_match.group(1))
            except (ValueError, IndexError):
                customers = 0

        
        # ============================================================
        # Generate Key Findings
        # ============================================================
        if revenue > 0:
            findings.append(f"Revenue of €{revenue:,.0f}")
        if cash > 0:
            findings.append(f"Cash position of €{cash:,.0f}")
        if gross_margin > 0:
            findings.append(f"Gross margin of {gross_margin:.1f}%")
        if customers > 0:
            findings.append(f"{customers:,} customer accounts")
        if ebitda > 0:
            findings.append(f"EBITDA of €{ebitda:,.0f}")

        # ============================================================
        # Generate AI Commentary
        # ============================================================
        commentary = f"Financial analysis of {document.filename}. "
        if revenue > 0:
            commentary += f"Revenue: €{revenue:,.0f}. "
        if customers > 0:
            commentary += f"Customers: {customers:,}. "
        if cash > 0:
            commentary += f"Cash: €{cash:,.0f}. "
        if gross_margin > 0:
            commentary += f"Gross margin: {gross_margin:.1f}%."

        return {
            "ai_commentary": commentary,
            "key_findings": findings if findings else ["Document processed successfully."],
            "summary": {
                "revenue": {"value": revenue, "currency": "EUR"},
                "customers": customers,
                "cash": {"value": cash, "currency": "EUR"},
                "ebitda": {"value": ebitda, "currency": "EUR"},
                "gross_margin": gross_margin,
                "operating_margin": operating_margin,
            },
            "model_version": "fallback-v1",
        }