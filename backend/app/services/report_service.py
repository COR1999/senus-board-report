from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Report
from app.models.document import Document

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
            # Check if Gemini is available AND properly initialized
            if self.gemini and self.gemini.is_available() and self.gemini.client:
                content = await self._call_gemini(document)
                report.generation_source = "gemini"
            else:
                content = self._fallback_generation(document)
                report.generation_source = "fallback"

            report.ai_commentary = content.get("ai_commentary")
            report.key_findings = content.get("key_findings", [])
            report.summary = content.get("summary", {})
            report.status = "completed"
            report.model_version = content.get("model_version", "gemini-2.0-flash")

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
        """Build the Gemini prompt for report generation."""
        text = document.extracted_text or ""
        return f"""
You are a senior financial analyst.

Create a professional financial report for the following document:

**Filename:** {document.filename}
**File Size:** {document.file_size} bytes

**Extracted Text (truncated):**
{text[:8000]}

Return ONLY valid JSON with this exact structure:
{{
  "ai_commentary": "2-3 paragraph executive summary in professional tone",
  "key_findings": ["bullet 1", "bullet 2", "bullet 3", "bullet 4"],
  "summary": {{ "revenue": "...", "ebitda": "...", "other": {{}} }},
  "model_version": "gemini-2.0-flash"
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
        """Generate fallback content when Gemini is unavailable."""
        if not document:
            return {
                "ai_commentary": "Report generation is currently unavailable.",
                "key_findings": [],
                "summary": {},
            }

        text = document.extracted_text or ""
        findings = []

        if re.search(r"revenue|sales", text, re.I):
            findings.append("Revenue figures detected.")
        if re.search(r"ebitda|cash flow", text, re.I):
            findings.append("EBITDA or cash flow data present.")
        if re.search(r"margin", text, re.I):
            findings.append("Margin metrics identified.")

        return {
            "ai_commentary": (
                f"Fallback report for {document.filename}. "
                "AI service is currently unavailable. Basic content generated."
            ),
            "key_findings": findings or ["Unable to extract automatic key findings."],
            "summary": {
                "filename": document.filename,
                "file_size": document.file_size,
                "status": "fallback",
            },
            "model_version": "fallback-v1",
        }