from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional, cast, overload

from sqlalchemy import CursorResult, select, or_
from sqlalchemy import delete as sql_delete
from sqlalchemy import update as sql_update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Report
from app.models.document import Document
from app.models.financial_metrics import FinancialMetrics
from app.models.balance_sheet_metrics import BalanceSheetMetrics
from app.services.gemini_service import GeminiAnalysisService
from app.services.extraction_confidence import score_extraction, LowConfidenceExtractionError
from app.services.pdf_service import PDFExtractionService
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
    # Overloads so a `force_int=True` call site (e.g. `metrics.customers`,
    # an `Optional[int]` column) narrows to `Optional[int]` instead of the
    # broader `float | int | None` union the un-overloaded signature gave --
    # that broader union was never assignable to an `Optional[int]` column.
    @overload
    def _normalize_metric(self, value: Any, force_int: Literal[True]) -> Optional[int]: ...
    @overload
    def _normalize_metric(self, value: Any, force_int: Literal[False] = False) -> Optional[float]: ...

    def _normalize_metric(self, value: Any, force_int: bool = False) -> float | int | None:
        """
        Coerces to a real number, preserving `None` for a genuinely missing
        value rather than defaulting to 0 -- a document the extractor found
        nothing in (e.g. a non-financial filing run through this pipeline
        via the investor-relations import feature) must not get a fake
        all-zero metrics row that can then shadow a real document's data on
        the dashboard (see docs/roadmap.md's note on this exact incident).
        """
        if value is None:
            return None

        try:
            return int(float(value)) if force_int else float(value)
        except Exception:
            return None

    def _extract_metric_value(self, value: Any) -> float | int | None:
        """
        Handles BOTH formats safely, preserving `None` (genuinely missing)
        rather than defaulting to 0:
        - AI: {"value": 123} or {"value": None}
        - fallback: 123 or None
        """
        if isinstance(value, dict):
            return value.get("value")
        return value

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

        metrics.customers = self._normalize_metric(
            self._extract_metric_value(metrics_data.get("customers")),
            force_int=True
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

        # Reporting period -- narrative-only (e.g. "HY2026"/"HY25"), same
        # missing-means-None handling as bookings above.
        metrics.reporting_period = self._plain_metric_value(metrics_data.get("reporting_period"))
        metrics.reporting_period_prior = self._plain_metric_value(metrics_data.get("reporting_period_prior"))
        metrics.reporting_period_end = self._plain_metric_value(metrics_data.get("reporting_period_end"))
        metrics.reporting_period_end_prior = self._plain_metric_value(
            metrics_data.get("reporting_period_end_prior")
        )
        metrics.reporting_period_start = self._plain_metric_value(metrics_data.get("reporting_period_start"))
        metrics.reporting_period_start_prior = self._plain_metric_value(
            metrics_data.get("reporting_period_start_prior")
        )

        # Extraction confidence -- set by `_generate` before calling this
        # method (stashed on `content`, not `metrics_data`, since it's a
        # property of the whole extraction attempt, not one of the
        # individual financial-metrics fields above). `None` for anything
        # that reaches `_save_metrics` without it having been computed
        # (there shouldn't be one today -- `_generate` always computes it
        # first -- but this keeps the method safe to call from anywhere
        # without a hard dependency on that caller).
        confidence = content.get("extraction_confidence")
        metrics.extraction_confidence = confidence.score if confidence else None
        metrics.extraction_confidence_tier = confidence.tier if confidence else None
        metrics.extraction_confidence_reasons = confidence.reasons if confidence else None

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
    async def _generate(self, document: Document, report: Report, *, persist_on_reject: bool = True) -> Report:
        """
        `persist_on_reject` distinguishes a first-time extraction (upload,
        IR import, or `get_or_create_report`'s first call -- nothing exists
        for this document yet, so a rejected attempt is safe, and useful,
        to keep for review) from a `force=True` regenerate of a document
        that already has better data (`generate_report` passes
        `persist_on_reject=not force`) -- a regenerate that scores worse
        than what's already there must never overwrite it. See the
        `confidence.tier == "rejected"` branch below.
        """
        try:
            from app.services.financial_metrics_extractor import FinancialMetricsExtractor

            extracted_text = document.extracted_text or ""
            # A scanned PDF with no text layer at all (confirmed for e.g.
            # ADF Farm Solutions' statements via PyMuPDF: every page is a
            # single embedded image, get_text() returns nothing) -- the
            # deterministic extractor has zero baseline to work with by
            # definition, so Gemini vision is the *only* possible source
            # here. Used strictly as a backup for a document the normal
            # text pipeline structurally cannot handle at all, never for
            # one a text-based extraction could already read (that always
            # takes the branch below instead, at zero extra Gemini cost).
            #
            # NOT `not extracted_text.strip()` -- a real bug found by
            # actually running this against the real ADF fixture, not
            # caught by any mocked test (every mock set extracted_text=""
            # directly, skipping the real extractor entirely).
            # PDFExtractionService.extract_text() prepends a
            # "--- Page N ---" marker for *every* page regardless of
            # whether that page had real text, so a fully scanned document's
            # extracted_text is never a truly empty string -- plain
            # `.strip()` saw those markers as "real content" and silently
            # routed a scanned document down the text path (with nothing
            # for the deterministic extractor to find) instead of vision.
            vision_extracted = not PDFExtractionService.has_extractable_text(extracted_text)

            if vision_extracted:
                # =====================================================
                # 1v. VISION BASELINE (ONLY POSSIBLE SOURCE FOR A SCAN)
                # =====================================================
                baseline_metrics: Dict[str, Any] = {}
                images = (
                    PDFExtractionService.render_page_images(document.file_path)
                    if document.file_path else []
                )
                content: Dict[str, Any] = (
                    self.gemini.generate_report_from_images(images, document.filename) or {}
                    if images else {}
                )

                # Gemini vision only ever returns a free-text `reporting_period`
                # (e.g. "Financial year ended 30 June 2025") -- there's no
                # separate start/end/cadence structure the way the
                # deterministic extractor derives one from a filing's full
                # text. Without reporting_period_start/end, a vision-extracted
                # document's cadence is unknowable (_cadence_months in
                # metrics.py returns None), so the mixed-cadence safety filter
                # can't protect it at all. Confirmed as a real production bug:
                # ADF Farm Solutions (a genuine FY2025 filing) was diffed
                # against the Information Document's own FY2025 figure (the
                # *same* period, not a real prior year) instead of that
                # document's real FY2024 comparative, purely because nothing
                # could tell two full-year filings apart from a half-year one.
                # Fixed by reusing the exact same "ended DD Month YYYY" +
                # cadence-cue parser the deterministic extractor already runs
                # against a filing's full text (_extract_period_fields), here
                # applied to Gemini's own period string instead -- the ADF
                # example above is literally a match for that parser's
                # existing pattern, no new regex needed.
                reporting_period_text = content.get("reporting_period")
                if reporting_period_text:
                    baseline_metrics.update({
                        key: value
                        for key, value in FinancialMetricsExtractor._extract_period_fields(reporting_period_text).items()
                        if value is not None
                    })
            else:
                # =====================================================
                # 1. BASELINE (DETERMINISTIC EXTRACTION - SOURCE OF TRUTH)
                # =====================================================
                baseline_metrics = FinancialMetricsExtractor.extract(extracted_text)

                # =====================================================
                # 2. AI LAYER (OPTIONAL ENRICHMENT)
                # Only spend a Gemini call if baseline extraction didn't
                # already get everything -- baseline wins the merge below
                # regardless, so calling Gemini when baseline is already
                # complete just burns quota for a result we'd throw away.
                # =====================================================
                if self._baseline_is_complete(baseline_metrics):
                    content = {
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
            # 3b. EXTRACTION CONFIDENCE (see extraction_confidence.py)
            # Computed before anything is persisted -- a rejected
            # extraction must not leave any trace in the database at all.
            # =====================================================
            if vision_extracted:
                # No text at all to run is_format_recognized/
                # check_reconciliation against -- "format recognized" here
                # means Gemini vision actually returned a real result
                # rather than the empty-response fallback (which fires
                # when Gemini is unavailable/exhausted, or found nothing
                # resembling a financial statement in the images).
                format_recognized = content.get("model_version") != "gemini-unavailable"
                pnl_reconciles = None
                cashflow_reconciles = None
            else:
                reconciliation = FinancialMetricsExtractor.check_reconciliation(extracted_text)
                format_recognized = FinancialMetricsExtractor.is_format_recognized(extracted_text)
                pnl_reconciles = reconciliation["pnl_reconciles"]
                cashflow_reconciles = reconciliation["cashflow_reconciles"]

            confidence = score_extraction(
                format_recognized=format_recognized,
                baseline_metrics=baseline_metrics,
                merged_metrics=merged_metrics,
                pnl_reconciles=pnl_reconciles,
                cashflow_reconciles=cashflow_reconciles,
                vision_extracted=vision_extracted,
            )
            content["extraction_confidence"] = confidence

            if confidence.tier == "rejected":
                if persist_on_reject:
                    # A rejected document is still persisted (revised from
                    # this project's original PR #42 policy of keeping
                    # nothing at all) -- a human reviewing *why* an
                    # extraction failed needs the actual attempted values
                    # and the confidence gate's own reasons on hand, not
                    # just the one-time 422 message below. Never a risk to
                    # the dashboard either way: `_IS_CONFIDENT_ENOUGH_FOR_
                    # DASHBOARD` (metrics.py) excludes any row scoring
                    # below 95 that hasn't been human-approved, and a
                    # `rejected` row is never offered an approve path (see
                    # documents.py's `approve_document`) -- this is
                    # strictly view-only. Skipped on a `force=True`
                    # regenerate of a document that already has better
                    # data (`persist_on_reject=False`) -- a worse retry
                    # must never overwrite what's already there.
                    await self._save_metrics(document.id, content)
                    report.status = "rejected"
                    report.updated_at = datetime.utcnow()
                    await self.db.commit()
                # Raised ahead of the broad `except Exception` below (see
                # the `except LowConfidenceExtractionError: raise` clause)
                # so it reaches whichever caller invoked `generate_report`
                # as a distinguishable error, not a generic "failed" status
                # -- each caller (a brand-new upload/import vs. a
                # regenerate of an existing document) applies its own
                # consequence. See extraction_confidence.py's module
                # docstring for the incident this closes.
                raise LowConfidenceExtractionError(confidence)

            # =====================================================
            # 4. REPORT FIELDS
            # =====================================================
            report.ai_commentary = content.get("ai_commentary", "")
            report.key_findings = content.get("key_findings") or []
            report.model_version = content.get(
                "model_version", "gemini-vision" if vision_extracted else "gemini-2.5-flash"
            )
            # Distinct from "hybrid" (deterministic baseline + optional text
            # Gemini enrichment) -- a scanned document has no baseline at
            # all, so its provenance is worth recording separately.
            report.generation_source = "vision" if vision_extracted else "hybrid"

            # Falls back to the document's filename when neither Gemini nor
            # the baseline produced a company name -- previously only the
            # `_baseline_is_complete` branch above had this fallback, so any
            # document routed through Gemini (baseline incomplete -- exactly
            # the Information Document's case, since its EBITDA is
            # genuinely undisclosed) that didn't itself return a
            # company_name fell through to the frontend's own "Document
            # #{id}" placeholder instead. Found via a real report showing
            # "Document #13" in production instead of a real name.
            company_name = content.get("company_name") or document.filename

            report.summary = {
                "company_name": company_name,
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

        except LowConfidenceExtractionError:
            # Not caught by the broad `except Exception` below -- whatever
            # this method itself decided to persist (see `persist_on_reject`
            # above) already happened before this raise; the caller
            # (documents.py's `_ingest_document`, reports.py's
            # `generate_or_get_report`, or reports.py's regenerate route)
            # only decides the HTTP-level consequence from here.
            raise

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

            if report is None:
                # Only reachable if the concurrent request's row vanished
                # again between our IntegrityError and the re-fetch above
                # (e.g. it was deleted mid-race) -- practically never, but
                # narrows `report` to non-Optional for every branch below
                # and gives a clear error instead of an AttributeError on
                # `report.status` if it ever did happen.
                raise ValueError("Report not found or could not be created")

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
        # AsyncSession.execute()'s declared return type is the generic
        # `Result[Any]`, which has no `rowcount` -- but a Core UPDATE
        # statement always executes through a `CursorResult` at runtime,
        # which does. A known SQLAlchemy async-typing gap, not a real
        # runtime risk; the cast documents the actual type instead of
        # suppressing the check entirely.
        claim = cast(CursorResult, await self.db.execute(
            sql_update(Report)
            .where(
                Report.id == report.id,
                or_(
                    Report.status != "generating",
                    Report.updated_at < datetime.utcnow() - self.GENERATION_STALE_AFTER,
                ),
            )
            .values(status="generating", updated_at=datetime.utcnow())
        ))
        await self.db.commit()

        if claim.rowcount == 0:
            # Someone else already claimed it between our read and here.
            await self.db.refresh(report)
            return report

        await self.db.refresh(report)
        # `force=True` is always a regenerate of a document that already has
        # (better) existing data -- `persist_on_reject=False` there protects
        # it from being overwritten by a worse retry. See `_generate`'s own
        # docstring.
        return await self._generate(document, report, persist_on_reject=not force)

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
            # An explicit single-document lookup (e.g. the Documents page's
            # own review panel) must still resolve a superseded document's
            # own report -- excluding it here would break "view the
            # original source report" for a document the merge feature is
            # specifically designed to leave untouched and independently
            # visible (see period_merge_service.py's own docstring).
            query = query.where(Report.document_id == document_id)
        else:
            # The "list every report" case (GET /api/reports, and the
            # dashboard's own "Recent Reports" panel) excludes a
            # superseded document's report -- confirmed as a real, live
            # bug: uploading two documents that merge into one new period
            # left the two ORIGINAL reports still listed here too, so
            # "ADF Farm Solutions Limited" appeared twice in Recent
            # Reports with no indication either was superseded (unlike the
            # Documents table, which has its own "Merged" badge for
            # exactly this). The merged document's own report is what
            # actually represents that period going forward.
            query = query.outerjoin(
                FinancialMetrics, FinancialMetrics.document_id == Report.document_id
            ).where(
                or_(
                    FinancialMetrics.superseded_by_document_id.is_(None),
                    FinancialMetrics.document_id.is_(None),
                )
            )

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