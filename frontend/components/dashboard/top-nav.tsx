'use client'

import * as React from 'react'
import Link from 'next/link'
import { Bell } from 'lucide-react'
import { CURRENT_USER } from '@/lib/current-user'
import { Button } from '@/components/ui/button'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'

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
      {/* Right: Notifications & User Menu */}
      <div className="flex items-center gap-4">
        {/* Notifications */}
        <Button
          variant="ghost"
          size="icon"
          className="relative h-9 w-9 text-muted-foreground hover:bg-muted/50 hover:text-foreground"
        >
          <Bell className="h-5 w-5" />
          <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-emerald-600" />
        </Button>

        {/* User Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-9 w-9 rounded-full p-0"
            >
              <Avatar className="h-9 w-9">
                <AvatarImage src={CURRENT_USER.avatarUrl} alt={CURRENT_USER.name} />
                <AvatarFallback>{CURRENT_USER.initials}</AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel className="flex flex-col space-y-1">
              <p className="text-sm font-medium text-foreground">{CURRENT_USER.name}</p>
              <p className="text-xs text-muted-foreground">{CURRENT_USER.title}</p>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/settings">Profile</Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/settings">Settings</Link>
            </DropdownMenuItem>
            <DropdownMenuItem>Help & Support</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem>Sign out</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}