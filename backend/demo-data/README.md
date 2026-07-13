# demo-data

Real Senus PLC filings, downloaded directly from the public investor-relations API
(`app/services/investor_relations_client.py` — `https://api.app.assiduous.tech/v1/investor-relations/senus`,
no auth required), used to pre-seed a **local-only** demo database before running Presentation Mode
(`scripts/local-demo/`). Not test fixtures (see `backend/tests/fixtures/` for those) and not used by
`pytest` — purely local-demo setup data.

- `Senus_Limited_Company_Balance_Sheet_Dec2025.pdf` (attachment id `faf71aff-286a-4a08-b064-f026ee49dc76`,
  5,382,515 bytes) — a scanned filing with no embedded text layer, so it runs through the Gemini-vision
  extraction fallback rather than the deterministic text extractor. Real, unscripted extraction-pipeline
  behavior against this file was `rejected` (0% confidence) in production at the time this was fetched —
  kept here anyway as an honest example of the confidence gate correctly refusing to promote a document
  it can't reliably read, not edited or replaced to force a nicer-looking result.

The other two pre-seed documents (`ADF Farm Solutions Consolidated Financial Statements (30 June 2025)`,
`Senus PLC Information Document December 2025`) already exist in `backend/tests/fixtures/` and
`backend/docs/source-documents/` — referenced from there directly rather than duplicated here.
