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
    document_id: 101,
    summary: { company_name: 'Senus PLC', reporting_period: 'Q4 2025' },
    status: 'completed' as const,
    created_at: '2025-12-31T00:00:00Z',
  },
  {
    id: 2,
    document_id: 102,
    summary: { company_name: 'Senus PLC', reporting_period: 'Q3 2025' },
    status: 'completed' as const,
    created_at: '2025-09-30T00:00:00Z',
  },
  {
    id: 3,
    document_id: 103,
    summary: { company_name: 'Senus PLC', reporting_period: 'H1 2025' },
    status: 'generating' as const,
    created_at: '2025-06-30T00:00:00Z',
  },
  {
    id: 4,
    document_id: 104,
    summary: null,
    status: 'failed' as const,
    created_at: '2025-03-31T00:00:00Z',
  },
]