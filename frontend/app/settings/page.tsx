import { DashboardShell } from '@/components/dashboard/dashboard-shell'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { ThemeToggle } from '@/components/theme-toggle'
import { CURRENT_USER } from '@/lib/current-user'

// Single-user boardroom presentation tool, not a multi-tenant product --
// this page intentionally has no account/profile editing, login, or
// per-user preferences. CURRENT_USER is a fixed presenter identity shared
// with Sidebar/TopNav, not an editable account.
export default function SettingsPage() {
  return (
    <DashboardShell title="Settings" description="Presenter identity and display preferences">
      <Card>
        <CardHeader>
          <CardTitle>Presenter</CardTitle>
          <CardDescription>Shown throughout the dashboard and in the top-nav</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <Avatar className="h-14 w-14">
              <AvatarImage src={CURRENT_USER.avatarUrl} alt={CURRENT_USER.name} />
              <AvatarFallback>{CURRENT_USER.initials}</AvatarFallback>
            </Avatar>
            <div className="flex flex-col">
              <span className="text-sm font-semibold text-foreground">{CURRENT_USER.name}</span>
              <span className="text-xs text-muted-foreground">{CURRENT_USER.title}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
          <CardDescription>Choose how the dashboard looks on this device</CardDescription>
        </CardHeader>
        <CardContent>
          <ThemeToggle />
        </CardContent>
      </Card>
    </DashboardShell>
  )
}
