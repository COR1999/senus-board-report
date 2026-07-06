// lib/mock-data.ts
export const mockMetrics = {
  revenue: {
    value: '€836,991',
    change: 38,
    trend: 'up' as const,
  },
  customers: {
    value: '158',
    change: 2.5,
    trend: 'up' as const,
  },
  cash: {
    value: '€1.2M',
    change: 15,
    trend: 'up' as const,
  },
  ebitda: {
    value: '€150K',
    change: 22,
    trend: 'up' as const,
  },
}

export const mockChartData = [
  { period: 'Jan', revenue: 60000 },
  { period: 'Feb', revenue: 75000 },
  { period: 'Mar', revenue: 95000 },
  { period: 'Apr', revenue: 110000 },
  { period: 'May', revenue: 132000 },
  { period: 'Jun', revenue: 158000 },
  { period: 'Jul', revenue: 185000 },
  { period: 'Aug', revenue: 215000 },
  { period: 'Sep', revenue: 245000 },
  { period: 'Oct', revenue: 280000 },
  { period: 'Nov', revenue: 520000 },
  { period: 'Dec', revenue: 836991 },
]

// Placeholder only -- no backend extraction for customer segments yet.
// See getSegmentBreakdown() in data-service.ts for why.
export const mockSegments = [
  { segment: 'Corporate', value: 502195, percentage: 60 },
  { segment: 'Government', value: 251097, percentage: 30 },
  { segment: 'Agriculture', value: 83699, percentage: 10 },
]

export const mockReports = [
  {
    id: 1,
    name: 'Q4 2025 Financial Report',
    date: '2025-12-31',
    status: 'completed' as const,
  },
  {
    id: 2,
    name: 'Q3 2025 Board Report',
    date: '2025-09-30',
    status: 'completed' as const,
  },
  {
    id: 3,
    name: 'H1 2025 Investor Update',
    date: '2025-06-30',
    status: 'completed' as const,
  },
  {
    id: 4,
    name: 'Q1 2025 Performance Review',
    date: '2025-03-31',
    status: 'completed' as const,
  },
]