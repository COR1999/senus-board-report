'use client'

import { useState, useEffect } from 'react'
import { Sidebar } from './sidebar'
import { TopNav } from './top-nav'
import { KpiCard } from './kpi-card'
import { RevenueChart } from './revenue-chart'
import { SegmentBreakdown } from './segment-breakdown'
import { AiInsights } from './ai-insights'
import { ReportsTable } from './reports-table'
import {
  getMetrics,
  getChartData,
  getSegmentBreakdown,
  getReports,
  type Metrics,
  type ChartDataPoint,
  type SegmentValue,
  type Report,
} from '@/lib/data-service'
import { DollarSign, Users, Wallet, TrendingUp } from 'lucide-react'

export function DashboardContainer() {
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [chartData, setChartData] = useState<ChartDataPoint[]>([])
  const [segments, setSegments] = useState<SegmentValue[]>([])
  const [reports, setReports] = useState<Report[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchAllData = async () => {
      try {
        setLoading(true)
        const [metricsData, chartDataResponse, segmentsData, reportsData] = await Promise.all([
          getMetrics(),
          getChartData(),
          getSegmentBreakdown(),
          getReports(),
        ])
        setMetrics(metricsData)
        setChartData(chartDataResponse)
        setSegments(segmentsData)
        setReports(reportsData)
        setError(null)
      } catch (err) {
        setError('Failed to load dashboard data')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    fetchAllData()
  }, [])

  if (error) {
    return (
      <div className="flex min-h-screen flex-col bg-background">
        <Sidebar />
        <TopNav />
        <main className="flex-1 md:ml-64 md:pt-0 pt-14">
          <div className="p-8">
            <div className="text-red-600 bg-red-50 dark:bg-red-950 p-4 rounded-lg">
              Error: {error}
            </div>
          </div>
        </main>
      </div>
    )
  }

  if (loading || !metrics) {
    return (
      <div className="flex min-h-screen flex-col bg-background">
        <Sidebar />
        <TopNav />
        <main className="flex-1 md:ml-64 md:pt-0 pt-14">
          <div className="p-8">
            <div className="animate-pulse space-y-4">
              <div className="h-10 bg-muted rounded w-1/4" />
              <div className="grid gap-4 md:grid-cols-4">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="h-32 bg-muted rounded" />
                ))}
              </div>
            </div>
          </div>
        </main>
      </div>
    )
  }

  const metricConfig = [
    { key: 'revenue' as const, title: 'Total Revenue', icon: DollarSign, timeframe: 'vs last year' },
    { key: 'customers' as const, title: 'Active Customers', icon: Users, timeframe: 'vs last quarter' },
    { key: 'cash' as const, title: 'Cash Position', icon: Wallet, timeframe: 'vs last month' },
    { key: 'ebitda' as const, title: 'EBITDA', icon: TrendingUp, timeframe: 'vs target' },
  ]

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
            {metricConfig.map(({ key, title, icon: Icon, timeframe }) => (
              <KpiCard
                key={key}
                title={title}
                value={metrics[key].value}
                changePercentage={metrics[key].change}
                trend={metrics[key].trend}
                icon={Icon}
                timeframe={timeframe}
              />
            ))}
          </div>

          {/* Charts & Insights Section */}
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <RevenueChart data={chartData} />
            </div>
            <div className="flex flex-col gap-6">
              <AiInsights />
              <SegmentBreakdown data={segments} />
            </div>
          </div>

          {/* Reports Table */}
          <ReportsTable reports={reports} />
        </div>
      </main>
    </div>
  )
}