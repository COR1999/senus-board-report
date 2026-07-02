import { DollarSign, Users, Wallet, TrendingUp } from 'lucide-react'
import { Sidebar } from '@/components/dashboard/sidebar'
import { TopNav } from '@/components/dashboard/top-nav'
import { KpiCard } from '@/components/dashboard/kpi-card'
import { RevenueChart } from '@/components/dashboard/revenue-chart'
import { AiInsights } from '@/components/dashboard/ai-insights'
import { ReportsTable } from '@/components/dashboard/reports-table'
import { mockMetrics } from '@/lib/mock-data'

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      <Sidebar />
      <TopNav />

      {/* Main Content */}
      <main className="flex-1 md:ml-64 md:pt-0 pt-14">
        <div className="space-y-8 p-6 md:p-8">
          {/* Header */}
          <div className="flex flex-col gap-2">
            <h1 className="text-3xl font-bold tracking-tight text-foreground">
              Executive Dashboard
            </h1>
            <p className="text-muted-foreground">
              Welcome to your AI-powered board reporting platform
            </p>
          </div>

          {/* KPI Cards Grid */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <KpiCard
              title="Total Revenue"
              value={mockMetrics.revenue.value}
              changePercentage={mockMetrics.revenue.change}
              trend={mockMetrics.revenue.trend}
              icon={DollarSign}
              timeframe="vs last year"
            />
            <KpiCard
              title="Active Customers"
              value={mockMetrics.customers.value}
              changePercentage={mockMetrics.customers.change}
              trend={mockMetrics.customers.trend}
              icon={Users}
              timeframe="vs last quarter"
            />
            <KpiCard
              title="Cash Position"
              value={mockMetrics.cash.value}
              changePercentage={mockMetrics.cash.change}
              trend={mockMetrics.cash.trend}
              icon={Wallet}
              timeframe="vs last month"
            />
            <KpiCard
              title="EBITDA"
              value={mockMetrics.ebitda.value}
              changePercentage={mockMetrics.ebitda.change}
              trend={mockMetrics.ebitda.trend}
              icon={TrendingUp}
              timeframe="vs target"
            />
          </div>

          {/* Charts & Insights Section */}
          <div className="grid gap-6 lg:grid-cols-3">
            <RevenueChart />
          </div>

          {/* AI Insights */}
          <AiInsights />

          {/* Reports Table */}
          <ReportsTable />
        </div>
      </main>
    </div>
  )
}