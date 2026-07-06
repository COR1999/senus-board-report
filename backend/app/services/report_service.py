from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, or_
from sqlalchemy import delete as sql_delete
from sqlalchemy import update as sql_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Report
from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.models.balance_sheet_metrics import BalanceSheetMetrics
from app.services.gemini_service import GeminiAnalysisService
from sqlalchemy.orm import selectinload


logger = logging.getLogger(__name__)


class ReportService:
    # A report stuck at status="generating" past this age is presumed to
    # belong to a crashed/killed worker (not an active generation) and is
    # safe to reclaim, so a crash mid-generation self-heals on the next
    # request instead of leaving the report permanently unrecoverable.
    GENERATION_STALE_AFTER = timedelta(minutes=10)

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

    @staticmethod
    def _plain_metric_value(value: Any) -> Any:
        """
        Unwraps an AI-shaped {"value": N} into N, passing plain values
        (including `None` for a genuinely-missing metric) through
        untouched. Unlike `_extract_metric_value`, this does NOT default
        to 0 -- it's used to normalize `report.summary["metrics"]` into a
        single consistent shape for API consumers, and collapsing
        "missing" into 0 here would re-introduce the same
        missing-vs-zero ambiguity `_baseline_is_complete` had to fix.
        """
        if isinstance(value, dict):
            return value.get("value")
        return value

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

        # Prior-period comparative (same filing's own comparison column --
        # see FinancialMetricsExtractor.extract()). No force_int/default-0
        # normalization here: these are purely optional, missing-means-None
        # fields, unlike the four required-baseline fields above.
        metrics.revenue_prior = self._plain_metric_value(metrics_data.get("revenue_prior"))
        metrics.cash_prior = self._plain_metric_value(metrics_data.get("cash_prior"))
        metrics.ebitda_prior = self._plain_metric_value(metrics_data.get("ebitda_prior"))
        metrics.gross_margin_prior = self._plain_metric_value(metrics_data.get("gross_margin_prior"))
        metrics.operating_margin_prior = self._plain_metric_value(metrics_data.get("operating_margin_prior"))

        # Bookings -- narrative-only, same missing-means-None handling as
        # the _prior fields above (never defaulted to 0).
        metrics.bookings_value = self._plain_metric_value(metrics_data.get("bookings_value"))
        metrics.bookings_customers = self._plain_metric_value(metrics_data.get("bookings_customers"))
        metrics.bookings_pipeline = self._plain_metric_value(metrics_data.get("bookings_pipeline"))

        metrics.extracted_at = datetime.utcnow()

        await self.db.commit()

    # =========================================================
    # SAVE BALANCE SHEET METRICS (Cash/Solvency/Returns inputs)
    # =========================================================
    async def _save_balance_sheet_metrics(self, document_id: int, data: Dict[str, Any]):
        """
        Populated only from the deterministic baseline extractor -- unlike
        `_save_metrics`, there's no Gemini/AI enrichment path for these
        fields, so no merge step is needed here.
        """
        stmt = select(BalanceSheetMetrics).where(
            BalanceSheetMetrics.document_id == document_id
        )
        result = await self.db.execute(stmt)
        metrics = result.scalars().first()

        if not metrics:
            metrics = BalanceSheetMetrics(document_id=document_id)
            self.db.add(metrics)

        for field in (
            "total_debt", "total_debt_prior",
            "interest_expense", "interest_expense_prior",
            "cost_of_sales", "cost_of_sales_prior",
            "administrative_expenses", "administrative_expenses_prior",
            "working_capital_change", "working_capital_change_prior",
            "capital_employed", "capital_employed_prior",
            "net_cash_used_operating", "net_cash_used_operating_prior",
            "operating_result", "operating_result_prior",
        ):
            setattr(metrics, field, data.get(field))

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
        return all(baseline_metrics.get(k) is not None for k in required)

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
                if value is not None:
                    merged_metrics[key] = value

            # Normalize to a single flat shape (plain numbers, `None` for
            # genuinely missing) -- ai_metrics entries not overridden by
            # baseline would otherwise still be {"value": N} dicts here.
            merged_metrics = {
                key: self._plain_metric_value(value)
                for key, value in merged_metrics.items()
            }

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

            balance_sheet_metrics = FinancialMetricsExtractor.extract_balance_sheet(
                document.extracted_text or ""
            )
            await self._save_balance_sheet_metrics(document.id, balance_sheet_metrics)

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

        if not report:
            new_report = Report(document_id=document_id, status="pending")
            self.db.add(new_report)
            try:
                await self.db.commit()
                report = new_report
                await self.db.refresh(report)
            except IntegrityError:
                # Lost a race with a concurrent first-time request for the
                # same document (Report.document_id is unique) -- fetch the
                # row the other request just inserted instead of crashing.
                await self.db.rollback()
                result = await self.db.execute(stmt)
                report = result.scalars().first()

        stale_generating = (
            report.status == "generating"
            and datetime.utcnow() - report.updated_at > self.GENERATION_STALE_AFTER
        )

        if not force:
            # Already completed -- nothing to do.
            if report.status == "completed":
                return report
            # Already failed -- don't silently retry on every poll and
            # re-hit Gemini. Caller must explicitly pass force=True.
            if report.status == "failed":
                return report
            # Already being generated by another request -- don't pile
            # on and double-spend a Gemini call for the same document,
            # unless that generation is stale enough to be presumed dead.
            if report.status == "generating" and not stale_generating:
                return report

        # Atomically claim the report so a concurrent request (double
        # click, retried request, overlapping poll) can't also pass this
        # point and fire a second Gemini call for the same document. A
        # report stuck in "generating" past GENERATION_STALE_AFTER is
        # also reclaimable, so a crashed worker doesn't brick the report
        # forever -- this applies regardless of `force`, since force is
        # about bypassing "already completed/failed", not about
        # interrupting a genuinely active generation.
        claim = await self.db.execute(
            sql_update(Report)
            .where(
                Report.id == report.id,
                or_(
                    Report.status != "generating",
                    Report.updated_at < datetime.utcnow() - self.GENERATION_STALE_AFTER,
                ),
            )
            .values(status="generating", updated_at=datetime.utcnow())
        )
        await self.db.commit()

        if claim.rowcount == 0:
            # Someone else already claimed it between our read and here.
            await self.db.refresh(report)
            return report

        await self.db.refresh(report)
        return await self._generate(document, report)

    # =========================================================
    # READ HELPERS
    # =========================================================
    async def get_report(self, report_id: int) -> Optional[Report]:
        stmt = (
            select(Report)
            .options(selectinload(Report.document))
            .where(Report.id == report_id)
        )

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
        from app.services.financial_metrics_extractor import FinancialMetricsExtractor

        text = document.extracted_text or ""
        statement_text = FinancialMetricsExtractor.extract_statement_text(text, max_chars=8000)

        return f"""
You are a senior financial analyst.

Extract structured financial data from this document.

Document:
{document.filename}

Text:
{statement_text}

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