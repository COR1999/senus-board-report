'use client'

import * as React from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  FileText,
  FolderOpen,
  Settings,
  Menu,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { CURRENT_USER } from '@/lib/current-user'
import { Button } from '@/components/ui/button'
import {
  Sheet,
  SheetContent,
  SheetTrigger,
} from '@/components/ui/sheet'

export interface SidebarProps extends React.HTMLAttributes<HTMLDivElement> {}

const menuItems = [
  { label: 'Dashboard', href: '/', icon: LayoutDashboard },
  { label: 'Reports', href: '/reports', icon: FileText },
  { label: 'Documents', href: '/documents', icon: FolderOpen },
  { label: 'Settings', href: '/settings', icon: Settings },
]

// Logo Component (moved outside)
function Logo() {
  return (
    <Link
      href="/"
      className="flex items-center gap-2.5 font-semibold text-neutral-50 transition-opacity hover:opacity-90"
    >
      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-500 text-white shadow-md shadow-emerald-500/20">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-6 w-6"
        >
          <path d="M12 2a10 10 0 0 1 10 10c0 5.523-4.477 10-10 10S2 17.523 2 12c0-5.5 4.5-10 10-10z" />
          <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
          <path d="M2 12h20" />
        </svg>
      </div>
      <div className="flex flex-col">
        <span className="text-sm font-bold tracking-tight text-neutral-50 leading-none">Senus</span>
        <span className="text-[10px] text-neutral-400 font-medium tracking-wider uppercase mt-0.5">Board Intel</span>
      </div>
    </Link>
  )
}

// Navigation Links (moved outside)
interface NavLinksProps {
  onClose?: () => void
}

function NavLinks({ onClose }: NavLinksProps) {
  const pathname = usePathname()

  return (
    <nav className="flex-1 space-y-1.5 px-4 py-6">
      {menuItems.map((item) => {
        const Icon = item.icon
        const isActive =
          item.href === '/'
            ? pathname === '/'
            : pathname === item.href || pathname.startsWith(item.href + '/')

        return (
          <Link
            key={item.label}
            href={item.href}
            onClick={() => onClose?.()}
            className={cn(
              'flex items-center gap-3.5 rounded-lg px-3.5 py-2.5 text-sm font-medium tracking-tight transition-all duration-200',
              isActive
                ? 'bg-emerald-950/40 text-emerald-400'
                : 'text-neutral-400 hover:bg-neutral-800/60 hover:text-neutral-50'
            )}
          >
            <Icon className={cn('h-5 w-5', isActive ? 'text-emerald-400' : 'text-neutral-400')} />
            <span>{item.label}</span>
          </Link>
        )
      })}
    </nav>
  )
}

// Footer Profile (moved outside)
function FooterProfile() {
  return (
    <div className="mt-auto border-t border-neutral-800 bg-neutral-900/40 p-4">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-900/40 text-emerald-400 font-semibold text-xs">
          {CURRENT_USER.initials}
        </div>
        <div className="flex flex-col min-w-0 flex-1">
          <span className="truncate text-xs font-semibold text-neutral-50">
            {CURRENT_USER.name}
          </span>
          <span className="truncate text-[10px] font-medium text-neutral-400">
            {CURRENT_USER.title}
          </span>
        </div>
      </div>
    </div>
  )
}

// Main Sidebar Component
//
// Deliberately NOT theme-following (no `dark:` variants) -- the sidebar
// stays a fixed dark palette in both light and dark mode, matching the
// reference design the user provided. A dark, branded sidebar next to a
// light content area is a common, intentional pattern (Stripe/Linear-style
// dashboards), not an oversight.
export function Sidebar({ className, ...props }: SidebarProps) {
  const [isOpen, setIsOpen] = React.useState(false)

  return (
    <>
      {/* Desktop Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-neutral-800 bg-neutral-950 md:flex',
          className
        )}
        {...props}
      >
        <div className="flex h-16 items-center border-b border-neutral-800 px-6">
          <Logo />
        </div>
        <NavLinks />
        <FooterProfile />
      </aside>

      {/* Mobile Header & Sheet */}
      <header className="fixed left-0 right-0 top-0 z-30 flex h-14 items-center justify-between border-b border-neutral-800 bg-neutral-950 px-4 md:hidden">
        <Logo />
        <Sheet open={isOpen} onOpenChange={setIsOpen}>
          <SheetTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-9 w-9 text-neutral-400 hover:bg-neutral-800/60 hover:text-neutral-50"
            >
              <Menu className="h-6 w-6" />
              <span className="sr-only">Toggle navigation menu</span>
            </Button>
          </SheetTrigger>
          <SheetContent
            side="left"
            className="flex h-full w-72 flex-col bg-neutral-950 p-0"
          >
            <div className="flex h-14 items-center border-b border-neutral-800 px-6">
              <Logo />
            </div>
            <NavLinks onClose={() => setIsOpen(false)} />
            <FooterProfile />
          </SheetContent>
        </Sheet>
      </header>
    </>
  )
}
