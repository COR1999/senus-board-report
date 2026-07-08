# AI Usage — feature/adf-vision-extraction

## Context

User request: unlock ADF Farm Solutions (the third real Senus document, already sitting in the repo,
blocked as a scanned PDF with no text layer) via a vision-capable Gemini call rather than OCR
tooling — but explicitly not at the cost of burning the free Gemini quota, so Gemini should be a
backup used only when other systems can't run at all, not a first resort.

## What was investigated first

Checked for a free/local OCR path before reaching for Gemini, since the user was explicit about
protecting quota. PyMuPDF (already a dependency) has a built-in OCR hook, `page.get_textpage_ocr()`
— tested directly against the real ADF fixture, and it requires an actual Tesseract engine installed
on the machine, which isn't present here:

```
RuntimeError: No tessdata specified and Tesseract is not installed
```

Getting a real local OCR path working would mean installing the Tesseract binary on this Windows dev
machine *and* getting Railway's deployment to install it too (an apt/Nixpacks config change, not a
pip install) — real infra work for one document. Presented this tradeoff directly rather than
silently picking a path; the user chose the Gemini-vision-backup approach, confirmed via
`AskUserQuestion`.

## What was built

- `backend/app/services/pdf_service.py`: `render_page_images()` — renders every page of a PDF to
  JPEG bytes via `get_pixmap()` (not the embedded-image extraction, so it works regardless of how a
  given scanned PDF happens to have embedded its pages).
- `backend/app/services/gemini_service.py`: refactored the existing `generate_report`'s call/cache/
  backoff logic into a shared `_call_gemini` helper, then added `generate_report_from_images` on top
  of it — sends every page image in **one** request (not one call per page), so a 23-page document
  still costs exactly one Gemini call. Cached by a hash of the image bytes + filename together, same
  as the text path's prompt-hash cache. This was the key "protect the quota" decision: reusing the
  same rate-limit/backoff machinery the text path already had, rather than adding a second, unguarded
  call site.
- `backend/app/services/report_service.py`: `_generate` now checks whether `document.extracted_text`
  is empty *before* touching the deterministic extractor at all — a scanned document has zero
  possible baseline by definition, so there's nothing for it to find. Only in that case does it
  render page images and call the vision path; every other document takes the existing, unchanged
  text-based branch at zero extra cost. Gated entirely by the *existing* Import/Upload action — no
  new UI trigger, no background scanning.
- `backend/app/services/extraction_confidence.py`: a real architectural gap found while wiring this
  in. The existing point formula weights a deterministic table match above a Gemini-narrative guess
  — but a scanned document has **no baseline at all**, so applying the formula unchanged capped every
  vision extraction at 71 points (`15+8+8` Gemini-only weights + the 40-point format bonus),
  permanently below the 85% auto-accept/needs-review floor regardless of how accurate the extraction
  actually was. Fixed with a dedicated `vision_extracted=True` scoring path: full point weights apply
  directly (there's only one possible source, so no baseline-vs-narrative split makes sense), but the
  resulting tier is unconditionally capped at `needs_review` — never `auto_accept` — since there's no
  independent deterministic cross-check possible for a scanned document the way there is for a text
  one (the two P&L/cash-flow reconciliation checks both need real parsed line items to compare).

## Why no frontend changes were needed

Vision-extracted data always lands at `needs_review`, which reuses the exact "Pending Review" tag
already built for the confidence gate (PR #42) — visible on the Documents table, excluded from the
executive dashboard's headline KPIs until a human reviews it. The existing UI already does the right
thing for this new data source with zero changes.

## Verification performed

- `pytest tests/` — 193 passed (16 new): `test_pdf_service.py` (new, `render_page_images` against
  the real 23-page ADF fixture, including confirming it genuinely has zero extractable text);
  `test_gemini_service.py` (+5: multimodal request shape, cache-by-image-bytes, cache misses on
  different images, the shared billing/rate-limit backoff applies to the vision path too, a
  pre-disabled circuit breaker skips the call entirely); `test_extraction_confidence.py` (+5: the
  new `vision_extracted` scoring path, including the "100-point extraction still capped at
  needs_review" case); `test_vision_extraction.py` (new — end-to-end against the real fixture: a
  complete mocked vision extraction persists at `needs_review`, the deterministic extractor is
  confirmed to never even be called for a scanned document, a failed/unavailable vision response is
  correctly rejected with nothing persisted).
- **Not verified against the live Gemini API.** This same session's earlier testing had already
  exhausted the account's real quota — confirmed as a billing/prepayment-credits issue, not a
  transient rate limit (the backend logged `"Your prepayment credits are depleted..."` during earlier
  testing today). A live attempt right now would just hit the same known error rather than prove
  anything new about this feature's own correctness; the mocked test suite exercises the real 23-page
  fixture's actual page count/rendering and the full routing/scoring/persistence logic instead.
