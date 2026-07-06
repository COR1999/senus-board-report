import { DashboardShell } from '@/components/dashboard/dashboard-shell'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'

// Placeholder only -- no settings data model or persistence exists yet.
// Profile fields below mirror the hardcoded user shown in Sidebar/TopNav.
export default function SettingsPage() {
  return (
    <DashboardShell title="Settings" description="Account and workspace preferences">
      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
          <CardDescription>This section is a placeholder -- no settings are editable yet</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <Avatar className="h-14 w-14">
              <AvatarImage src="https://avatar.vercel.sh/sarah" alt="Sarah" />
              <AvatarFallback>SJ</AvatarFallback>
            </Avatar>
            <div className="flex flex-col">
              <span className="text-sm font-semibold text-foreground">Sarah Jenkins</span>
              <span className="text-xs text-muted-foreground">CEO & Co-Founder</span>
            </div>
          </div>
        </CardContent>
      </Card>
    </DashboardShell>
  )
}
