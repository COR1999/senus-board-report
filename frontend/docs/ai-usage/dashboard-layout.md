# AI Usage — feature/dashboard-layout

## What was built

- `DashboardShell`: shared sidebar + top nav + content wrapper, extracted
  from `dashboard-container.tsx` so every route uses the same layout.
- Three new pages behind it: `/reports` (full `ReportsTable`), `/documents`
  (list + working upload button, new `getDocuments()`), `/settings`
  (placeholder profile card).
- Wired the top-right avatar dropdown's Profile/Settings items to actually
  navigate to `/settings` (previously dead no-op menu items).
- Fixed the root layout's leftover default `"Create Next App"` metadata.

## AI-generated vs. human-reviewed

All code in this branch was written by Claude Code (Sonnet 5). This branch
was the most iterative one so far: the user tested live in their own
browser after each change (no browser tooling was available this session)
and drove several of the actual fixes through what they found:

- Found the sidebar's dead links (`/reports`, `/documents`, `/settings`
  all 404'd) was flagged by AI before writing code, then the user chose
  the "add minimal placeholder pages" option over leaving it or just
  repointing links.
- User found and reported: duplicate PDF uploads aren't detected (deferred,
  added to roadmap as `feature/document-dedup` at user's request), and that
  the avatar dropdown's Settings/Profile items didn't navigate anywhere
  once a real Settings page existed to compare against (fixed same session).
- User also asked to track delete-document/regenerate-report UI as future
  work (`feature/document-report-actions`) -- both backend endpoints
  already exist, this is pure frontend wiring for a later branch.

## Notable decisions made along the way

- **DashboardShell takes a `title`/`description` pair rather than a raw
  header slot** -- every page so far wants the same two-line header
  pattern, so a small typed prop keeps pages terser than passing JSX.
- **Documents page reuses the existing, already-implemented `uploadPDF()`**
  rather than building new upload logic -- the only new client-side code
  is `getDocuments()`, wrapping a backend endpoint (`GET /api/documents`)
  that already existed but had no frontend caller.
- **Settings page is explicitly a placeholder** (code comment says so) --
  no settings data model exists anywhere in the backend, so it shows the
  same hardcoded profile info already displayed in the sidebar/top nav
  rather than inventing fake editable fields.
- **Help & Support / Sign out left non-functional, deliberately** -- this
  app has no auth system by original design ("no authentication
  required"), so Sign out has nothing to do; confirmed with the user
  rather than assumed.

## Verification performed

- `cd frontend && npx vitest run` -- 63 passed.
- `cd frontend && npx tsc --noEmit` -- no type errors.
- **User manually verified in their own live dev server** throughout this
  branch (no browser/screenshot tooling available this session): all four
  nav links resolve without 404s, mobile responsiveness, CSV export /
  upload both work end-to-end, and the avatar dropdown now navigates to
  Settings correctly.
