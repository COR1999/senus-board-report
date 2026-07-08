# AI Usage — fix/backend-gemini-pinned-model-quota

## Context

User dropped a new key into Railway's `GEMINI_API_KEY` after the original was confirmed exhausted
(a real "prepayment credits depleted" billing error, hit live earlier this session). Asked to verify
it worked — testing surfaced two real, unrelated bugs, both found only by actually running the
pipeline against the real API and the real ADF Farm Solutions fixture, not by reasoning about it.

## Bug 1: the pinned model had zero free-tier quota on the new key

Importing ADF Farm Solutions into production immediately failed with a 422 ("no recognized
financial-statement section"). The Railway log for that request showed the real cause:

```
Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests,
limit: 0, model: gemini-2.0-flash
```

Not a billing/prepayment problem this time — this specific Google Cloud project/key was simply never
granted free-tier access to the pinned `gemini-2.0-flash` model at all. The frontend had already hit
and fixed this exact failure class (see `GEMINI_INSIGHTS_MODEL`'s own code comment, written after an
earlier incident) by defaulting to the `-latest` alias instead of a pinned version — but the backend's
`gemini_service.py` and `core/config.py` still both defaulted to the pinned string, with only a
comment warning it could happen.

Tried `gemini-flash-latest` first (matching the frontend's fix exactly) — it hit a *different*,
transient `503 UNAVAILABLE: high demand` error repeatedly against this same key, unrelated to quota.
Listed the key's actually-available models directly (`client.models.list()`) and tested
`gemini-2.5-flash` (specific, current, non-preview, not an alias) — confirmed working cleanly.
Changed the default in `gemini_service.py`, `core/config.py`, and `.env.example` consistently (still
overridable via the existing `GEMINI_MODEL` env var with no redeploy, unchanged).

## Bug 2: a real Gemini success was still rejected — `has_extractable_text` needed real logic

With the model fixed, importing ADF Farm Solutions *still* failed the same way. Direct diagnosis
(bypassing the app to call the raw Gemini client) showed the vision extraction genuinely worked —
revenue, cash, EBITDA, margins, all real and correct. So the bug had to be inside `_generate`'s own
routing logic, not Gemini.

Traced it by monkeypatching `_call_gemini` to print what `contents` it actually received: a plain
878-character **string**, not the expected `[prompt, ...23 image Parts]` list. That meant
`vision_extracted` was evaluating `False` for a genuinely scanned document — the deterministic text
path was being taken instead, with nothing for it to find.

Root cause: `PDFExtractionService.extract_text()` prepends a `"--- Page N ---"` marker for *every*
page regardless of whether that page had real text. A fully scanned PDF's `extracted_text` is
therefore never a truly empty string — `not extracted_text.strip()` saw those markers as "real
content" and silently misrouted the document. This slipped past every test in PR #48 because all of
them set `extracted_text=""` directly on a mock `Document`, never exercising the real
`extract_text()` output shape.

Fixed with a new `PDFExtractionService.has_extractable_text()` that strips the page markers before
checking for real content, used in `_generate` instead of the naive check. Added a regression test
using the *real* `extract_text()` output (not a hand-written `""`) specifically to lock this in —
the gap that let it through the first time.

## Verification performed

- `pytest tests/` — 205 passed (5 new: `has_extractable_text` unit tests covering empty string,
  whitespace, markers-only, and markers-plus-real-content; a `_generate`-level regression test using
  the real `extract_text()` output for the ADF fixture, confirming it still takes the vision path).
- **Full real end-to-end verification, not mocked**: ran the actual `upload_document` route against
  the real ADF Farm Solutions fixture with the real (new) Gemini key. Result: revenue €836,991, cash
  €140,135 (both matching the Information Document's own figures exactly — strong evidence this is
  genuinely the source data Senus's summary table was built from), EBITDA -€613,313 (real, new data
  never available from any other ingested filing), gross margin 77.47%, operating margin -75.71%,
  confidence 85% / `needs_review` (correctly capped — see PR #48's design, unchanged by this fix).
