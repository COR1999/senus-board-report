from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy import delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Report
from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.services.gemini_service import GeminiAnalysisService

logger = logging.getLogger(__name__)


class ReportService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.gemini = GeminiAnalysisService()

    # =========================================================
    # NORMALISATION (AI + fallback safe)
    # =========================================================
    def _normalize_metric(self, value: Any, force_int: bool = False) -> float | int:
        if isinstance(value, dict):
            value = value.get("value", 0)

        try:
            if force_int:
                return int(float(value))
            return float(value)
        except Exception:
            return 0

    def _extract_metric_value(self, value: Any) -> float | int:
        """
        Handles BOTH formats safely:
        - AI: {"value": 123}
        - fallback: 123
        """
        if isinstance(value, dict):
            return value.get("value", 0) or 0
        return value or 0

    # =========================================================
    # SAVE METRICS (NO SILENT FAILURES)
    # =========================================================
    async def _save_metrics(self, document_id: int, content: Dict[str, Any]):
        metrics_data = content.get("financial_metrics") or {}

        stmt = select(FinancialMetrics).where(
            FinancialMetrics.document_id == document_id
        )
        result = await self.db.execute(stmt)
        metrics = result.scalars().first()

        if not metrics:
            metrics = FinancialMetrics(document_id=document_id)
            self.db.add(metrics)

        # SAFE EXTRACTION (AI + fallback compatible)
        metrics.revenue = self._normalize_metric(
            self._extract_metric_value(metrics_data.get("revenue"))
        )

        metrics.customers = int(
            self._normalize_metric(
                self._extract_metric_value(metrics_data.get("customers")),
                force_int=True
            )
        )

        metrics.cash = self._normalize_metric(
            self._extract_metric_value(metrics_data.get("cash"))
        )

        metrics.ebitda = self._normalize_metric(
            self._extract_metric_value(metrics_data.get("ebitda"))
        )

        metrics.gross_margin = self._normalize_metric(
            self._extract_metric_value(metrics_data.get("gross_margin"))
        )

        metrics.operating_margin = self._normalize_metric(
            self._extract_metric_value(metrics_data.get("operating_margin"))
        )

        metrics.extracted_at = datetime.utcnow()

        await self.db.commit()

    # =========================================================
    # Does the baseline (regex) extraction already have everything
    # we need? If so, there's no reason to spend a Gemini call on
    # financial_metrics extraction at all -- baseline always wins
    # in the merge anyway (see _generate below).
    # =========================================================
    @staticmethod
    def _baseline_is_complete(baseline_metrics: Dict[str, Any]) -> bool:
        required = ("revenue", "cash", "ebitda", "customers")
        return all(baseline_metrics.get(k) not in (None, 0) for k in required)

    # =========================================================
    # MAIN PIPELINE (FAILSAFE FIRST)
    # =========================================================
    async def _generate(self, document: Document, report: Report) -> Report:
        try:
            from app.services.financial_metrics_extractor import FinancialMetricsExtractor

            # =====================================================
            # 1. BASELINE (DETERMINISTIC EXTRACTION - SOURCE OF TRUTH)
            # =====================================================
            baseline_metrics = FinancialMetricsExtractor.extract(
                document.extracted_text or ""
            )

            # =====================================================
            # 2. AI LAYER (OPTIONAL ENRICHMENT)
            # Only spend a Gemini call if baseline extraction didn't
            # already get everything -- baseline wins the merge below
            # regardless, so calling Gemini when baseline is already
            # complete just burns quota for a result we'd throw away.
            # =====================================================
            if self._baseline_is_complete(baseline_metrics):
                content: Dict[str, Any] = {
                    "company_name": document.filename,
                    "reporting_period": None,
                    "financial_metrics": {},
                    "key_findings": [],
                    "ai_commentary": "",
                    "model_version": "baseline-only",
                }
            else:
                prompt = self._build_prompt(document)
                content = self.gemini.generate_report(prompt) or {}

            ai_metrics = content.get("financial_metrics") or {}

            # =====================================================
            # 3. SAFE MERGE (BASELINE WINS)
            # =====================================================
            merged_metrics = dict(ai_metrics)
            for key, value in baseline_metrics.items():
                if value not in (None, 0):
                    merged_metrics[key] = value

            content["financial_metrics"] = merged_metrics

            # =====================================================
            # 4. REPORT FIELDS
            # =====================================================
            report.ai_commentary = content.get("ai_commentary", "")
            report.key_findings = content.get("key_findings") or []
            report.model_version = content.get("model_version", "gemini-2.0-flash")
            report.generation_source = "hybrid"

            report.summary = {
                "company_name": content.get("company_name"),
                "reporting_period": content.get("reporting_period"),
                "metrics": merged_metrics,
                "key_findings": report.key_findings,
            }

            report.status = "completed"
            report.updated_at = datetime.utcnow()

            # =====================================================
            # 5. PERSIST (ALWAYS SAFE)
            # =====================================================
            await self._save_metrics(document.id, content)

            await self.db.commit()
            await self.db.refresh(report)

            return report

        except Exception as e:
            # THIS is the fix for reports getting stuck in "pending" forever
            # and re-triggering a fresh Gemini call on every subsequent poll.
            logger.error(f"Report generation failed for document {document.id}: {e}")

            report.status = "failed"
            report.ai_commentary = f"Generation failed: {e}"
            report.generation_source = "error"
            report.updated_at = datetime.utcnow()

            await self.db.commit()
            await self.db.refresh(report)

            return report

    # =========================================================
    # PUBLIC API
    # =========================================================
    async def generate_report(self, document_id: int, force: bool = False) -> Report:

        stmt = select(Document).where(Document.id == document_id)
        result = await self.db.execute(stmt)
        document = result.scalars().first()

        if not document:
            raise ValueError("Document not found")

        stmt = select(Report).where(Report.document_id == document_id)
        result = await self.db.execute(stmt)
        report = result.scalars().first()

        if report and not force:
            # Already completed -- nothing to do.
            if report.status == "completed":
                return report
            # Already failed -- don't silently retry on every poll and
            # re-hit Gemini. Caller must explicitly pass force=True.
            if report.status == "failed":
                return report

        if not report:
            report = Report(document_id=document_id, status="pending")
            self.db.add(report)
            await self.db.commit()
            await self.db.refresh(report)

        return await self._generate(document, report)

    # =========================================================
    # READ HELPERS
    # =========================================================
    async def get_report(self, report_id: int) -> Optional[Report]:
        stmt = select(Report).where(Report.id == report_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def delete_report(self, report_id: int) -> bool:
        stmt = select(Report).where(Report.id == report_id)
        result = await self.db.execute(stmt)
        report = result.scalars().first()

        if not report:
            return False

        await self.db.execute(sql_delete(Report).where(Report.id == report_id))
        await self.db.commit()
        return True

    async def list_reports(self, document_id: Optional[int] = None) -> List[Report]:
        query = select(Report)

        if document_id:
            query = query.where(Report.document_id == document_id)

        result = await self.db.execute(query.order_by(Report.created_at.desc()))
        return list(result.scalars().all())

    async def get_or_create_report(self, document_id: int) -> Report:
        stmt = select(Report).where(Report.document_id == document_id)
        result = await self.db.execute(stmt)
        report = result.scalars().first()

        if report:
            return report

        return await self.generate_report(document_id)

    # =========================================================
    # PROMPT
    # =========================================================
    def _build_prompt(self, document: Document) -> str:
        text = document.extracted_text or ""

        return f"""
You are a senior financial analyst.

Extract structured financial data from this document.

Document:
{document.filename}

Text:
{text[:8000]}

Return JSON ONLY:

{{
  "company_name": "...",
  "reporting_period": "...",
  "financial_metrics": {{
    "revenue": {{"value": 0}},
    "customers": {{"value": 0}},
    "cash": {{"value": 0}},
    "ebitda": {{"value": 0}},
    "gross_margin": {{"value": 0}},
    "operating_margin": {{"value": 0}}
  }},
  "key_findings": [],
  "ai_commentary": ""
}}
""".strip()