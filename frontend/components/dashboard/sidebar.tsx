"use client"

import * as React from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard,
  FileText,
  FolderOpen,
  Settings,
  Menu,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetTrigger,
} from "@/components/ui/sheet"

export interface SidebarProps extends React.HTMLAttributes<HTMLDivElement> {}

/**
 * Responsive Sidebar component for the executive dashboard.
 * Renders as a fixed sidebar on desktop (md screens and up), and
 * automatically transitions to a top navigation bar with a collapsible left Drawer (Sheet) on mobile.
 */
export function Sidebar({ className, ...props }: SidebarProps) {
  const pathname = usePathname()
  const [isOpen, setIsOpen] = React.useState(false)

  const menuItems = [
    { label: "Dashboard", href: "/", icon: LayoutDashboard },
    { label: "Reports", href: "/reports", icon: FileText },
    { label: "Documents", href: "/documents", icon: FolderOpen },
    { label: "Settings", href: "/settings", icon: Settings },
  ]

  // Clean and modern environmental SaaS logo (Senus)
  const Logo = () => (
    <Link
      href="/"
      className="flex items-center gap-2.5 font-semibold text-foreground transition-opacity hover:opacity-90"
      onClick={() => setIsOpen(false)}
    >
      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-600 text-white shadow-md shadow-emerald-600/20 dark:bg-emerald-500 dark:shadow-emerald-500/10">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-5 w-5"
        >
          <path d="M12 2a10 10 0 0 1 10 10c0 5.523-4.477 10-10 10S2 17.523 2 12c0-5.5 4.5-10 10-10z" />
          <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
          <path d="M2 12h20" />
        </svg>
      </div>
      <div className="flex flex-col">
        <span className="text-sm font-bold tracking-tight text-foreground leading-none">Senus</span>
        <span className="text-[10px] text-muted-foreground font-medium tracking-wider uppercase mt-0.5">Board Intel</span>
      </div>
    </Link>
  )

  // Navigation Links component
  const NavLinks = () => (
    <nav className="flex-1 space-y-1.5 px-4 py-6">
      {menuItems.map((item) => {
        const Icon = item.icon
        // Strict active check or prefix check for child pages (e.g., active on /reports/1 if href is /reports)
        const isActive =
          item.href === "/"
            ? pathname === "/"
            : pathname === item.href || pathname.startsWith(item.href + "/")

        return (
          <Link
            key={item.label}
            href={item.href}
            onClick={() => setIsOpen(false)}
            className={cn(
              "flex items-center gap-3.5 rounded-lg px-3.5 py-2.5 text-sm font-medium transition-all duration-200",
              isActive
                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-400"
                : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
            )}
          >
            <Icon
              className={cn(
                "h-4 w-4",
                isActive
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-muted-foreground group-hover/link:text-foreground"
              )}
            />
            <span>{item.label}</span>
          </Link>
        )
      })}
    </nav>
  )

  // Sidebar Footer profile section (CEO/Executive profile)
  const FooterProfile = () => (
    <div className="mt-auto border-t border-border/40 p-4 bg-muted/20">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-100 text-emerald-800 font-semibold text-xs dark:bg-emerald-900/30 dark:text-emerald-400">
          SJ
        </div>
        <div className="flex flex-col min-w-0 flex-1">
          <span className="text-xs font-semibold text-foreground truncate">Sarah Jenkins</span>
          <span className="text-[10px] text-muted-foreground truncate font-medium">CEO & Co-Founder</span>
        </div>
      </div>
    </div>
  )

  return (
    <>
      {/* 1. Desktop Sidebar (Visible on medium/large viewports) */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-border/60 bg-card md:flex",
          className
        )}
        {...props}
      >
        <div className="flex h-16 items-center border-b border-border/40 px-6">
          <Logo />
        </div>
        <NavLinks />
        <FooterProfile />
      </aside>

      {/* 2. Mobile Sticky Header & Sheet (Visible on small viewports) */}
      <header className="fixed top-0 left-0 right-0 z-30 flex h-14 items-center justify-between border-b border-border/60 bg-card px-4 md:hidden">
        <Logo />
        <Sheet open={isOpen} onOpenChange={setIsOpen}>
          <SheetTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-9 w-9 text-muted-foreground hover:text-foreground hover:bg-muted/50"
            >
              <Menu className="h-5 w-5" />
              <span className="sr-only">Toggle navigation menu</span>
            </Button>
          </SheetTrigger>
          <SheetContent
            side="left"
            className="w-72 p-0 flex flex-col h-full bg-card"
          >
            <div className="flex h-14 items-center border-b border-border/40 px-6">
              <Logo />
            </div>
            <NavLinks />
            <FooterProfile />
          </SheetContent>
        </Sheet>
      </header>
    </>
  )
}
