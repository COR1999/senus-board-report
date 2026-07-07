/**
 * Placeholder identity shown in the sidebar footer, top-nav user menu, and
 * settings profile card -- there's no auth or user data model yet (see
 * settings/page.tsx), so this is the single source for that placeholder
 * rather than each of the three duplicating the same name/title/avatar.
 */
export const CURRENT_USER = {
  name: 'Sarah Jenkins',
  title: 'CEO & Co-Founder',
  initials: 'SJ',
  avatarUrl: 'https://avatar.vercel.sh/sarah',
} as const
