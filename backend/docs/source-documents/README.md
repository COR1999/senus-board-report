# Source documents

Real financial/governance documents for Senus PLC, downloaded directly from Senus's investor
relations page (`app.assiduous.tech/investor-relations/senus`, powered by Assiduous's own
investor-relations platform). See the root `README.md`'s "Assumptions" section for how these were
found and the "Investor relations API" section for the endpoints used to fetch them.

| File | Published | Contents | Ingested? |
|---|---|---|---|
| `Senus_PLC_Information_Document_Dec2025.pdf` | 18 Dec 2025 | Euronext listing prospectus (53 pages) — includes real FY2024/FY2025 annual P&L, balance sheet, cash flow, and customer/KPI figures | Not yet — flagged as the top follow-up priority in `docs/roadmap.md` |
| `ADF_Farm_Solutions_Financial_Statements_Jun2025.pdf` | 18 Dec 2025 | Senus's predecessor entity's (ADF Farm Solutions Ltd, pre-PLC-re-registration) full audited annual statutory accounts for the year ended 30 June 2025 (23 pages) | Not yet — same follow-up priority |

The existing half-year filing already powering the dashboard
(`backend/tests/fixtures/Senus_HalfYearResultsDec2025_PR_V19032026 FINAL clean.pdf`) remains the
only document actually wired into `financial_metrics_extractor.py` today.

**Not downloaded** (governance/constitutional documents, not financial-facts sources): AGM notices
and proxy forms, the Memo & Articles of Association, and the pre-listing company balance sheet
(8 Dec 2025) — none of these carry extractable P&L/balance-sheet/cash-flow figures.
