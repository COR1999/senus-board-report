'use client'

import Link from 'next/link'
import { CURRENT_USER } from '@/lib/current-user'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'

export function TopNav() {
  return (
    // `md:ml-20` matches <main>'s offset in dashboard-shell.tsx (Sidebar's
    // permanent icon-only rail width -- it expands wider on hover as an
    // overlay, so this offset intentionally stays fixed regardless of hover
    // state). Without this offset, this header rendered underneath the
    // fixed-position Sidebar instead of starting to its right, which is what
    // actually made the (also non-functional) search box look like a stray
    // floating element clipped by the sidebar. Removed that search box
    // outright rather than just repositioning it -- it was never wired to a
    // handler, and both /reports and /documents now have their own real,
    // working search.
    <header className="sticky top-0 z-20 hidden border-b border-border/40 bg-card/95 backdrop-blur md:ml-20 md:flex md:h-16 md:items-center md:justify-end md:px-10">
      {/* Single, always-visible presenter identity -- this dashboard is a
          single-user boardroom presentation tool, not a multi-tenant
          product, so the notifications bell (nothing real ever backed it --
          no data source, a permanently-on fake "unread" dot) and the
          dropdown menu (half its items were dead no-ops: "Help & Support"
          and "Sign out" with no auth to sign out of, "Profile" duplicated
          "Settings") were removed rather than tidied piecemeal. A plain
          link to the one real destination is more honest than a menu with
          only one working item. */}
      <Link
        href="/settings"
        className="flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm transition-colors hover:bg-muted/50"
      >
        <Avatar className="h-9 w-9">
          <AvatarImage src={CURRENT_USER.avatarUrl} alt={CURRENT_USER.name} />
          <AvatarFallback>{CURRENT_USER.initials}</AvatarFallback>
        </Avatar>
        <span className="flex flex-col text-left leading-tight">
          <span className="font-medium text-foreground">{CURRENT_USER.name}</span>
          <span className="text-xs text-muted-foreground">{CURRENT_USER.title}</span>
        </span>
      </Link>
    </header>
  )
}
