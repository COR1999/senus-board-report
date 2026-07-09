# Feature screenshots

Captured 2026-07-08 against the real deployed app (`https://senus-board-report.vercel.app`, backed
by the real Railway production API) using Playwright, one screenshot per major feature. Two panels
(11, 12) use a throwaway local database instead — they cover the review/approve workflow that had
just shipped and hadn't reached production data yet at capture time.

| # | File | Feature |
|---|---|---|
| 01 | `01-dashboard-overview.png` | Executive Dashboard — hero KPI row + compact stat strip covering all 5 required metric categories |
| 02 | `02-ai-board-insights.png` | AI Board Insights panel — Gemini-generated commentary with category tags and recommended board actions |
| 03 | `03-revenue-trend-chart.png` | Revenue Trend chart with the metric-swap toggle (Revenue/EBITDA/Cash) and forecast switch |
| 04 | `04-period-selector.png` | Period selector — switching the whole dashboard between the two real reporting periods (FY2025 / HY2026) |
| 05 | `05-dashboard-dark-mode.png` | Dark mode theme |
| 06 | `06-documents-page.png` | Documents page — uploaded filings list, investor-relations "new filings available" banner |
| 07 | `07-reports-page.png` | Reports page |
| 08 | `08-settings-page.png` | Settings page (theme toggle) |
| 09 | `09-sidebar-expanded.png` | Sidebar hover-to-expand navigation |
| 10 | `10-documents-pending-and-rejected-tags.png` | Documents table showing both a "Pending Review" and a "Rejected" confidence tag |
| 11 | `11-review-needs-review-panel.png` | Review panel for a `needs_review` document — extracted values, confidence reasons, Approve button |
| 12 | `12-review-rejected-panel.png` | Review panel for a `rejected` document — same layout, view-only, no Approve button |
