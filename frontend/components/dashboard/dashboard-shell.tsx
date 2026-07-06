import { Sidebar } from './sidebar'
import { TopNav } from './top-nav'

interface DashboardShellProps {
  title: string
  description?: string
  children: React.ReactNode
}

/**
 * Shared page shell (sidebar + top nav + content wrapper) for every
 * dashboard route, so /reports, /documents, /settings, and the main
 * dashboard page all get the same nav and responsive layout instead of
 * each duplicating it.
 */
export function DashboardShell({ title, description, children }: DashboardShellProps) {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <Sidebar />
      <TopNav />
      <main className="flex-1 md:ml-64 md:pt-0 pt-14">
        <div className="space-y-8 p-6 md:p-8">
          <div className="flex flex-col gap-2">
            <h1 className="text-3xl font-bold tracking-tight text-foreground">{title}</h1>
            {description && <p className="text-muted-foreground">{description}</p>}
          </div>
          {children}
        </div>
      </main>
    </div>
  )
}
