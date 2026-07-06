// lib/mock-data.ts
export const mockMetrics = {
  revenue: {
    value: '€836,991',
    change: 38,
    trend: 'up' as const,
    history: [420000, 480000, 510000, 560000, 610000, 705000, 780000, 836991],
  },
  customers: {
    value: '158',
    change: 2.5,
    trend: 'up' as const,
    history: [120, 128, 135, 140, 148, 152, 155, 158],
  },
  cash: {
    value: '€1.2M',
    change: 15,
    trend: 'up' as const,
    history: [980000, 1010000, 1055000, 1090000, 1140000, 1180000, 1200000],
  },
  ebitda: {
    value: '€150K',
    change: 22,
    trend: 'up' as const,
    history: [98000, 105000, 112000, 120000, 132000, 141000, 150000],
  },
}

export const mockChartData = [
  { month: 'Jan', revenue: 60000 },
  { month: 'Feb', revenue: 75000 },
  { month: 'Mar', revenue: 95000 },
  { month: 'Apr', revenue: 110000 },
  { month: 'May', revenue: 132000 },
  { month: 'Jun', revenue: 158000 },
  { month: 'Jul', revenue: 185000 },
  { month: 'Aug', revenue: 215000 },
  { month: 'Sep', revenue: 245000 },
  { month: 'Oct', revenue: 280000 },
  { month: 'Nov', revenue: 520000 },
  { month: 'Dec', revenue: 836991 },
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