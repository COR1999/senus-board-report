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
  ebitda_margin: {
    value: '18.2%',
    change: 3.1,
    trend: 'up' as const,
    history: [12.4, 13.8, 14.9, 15.6, 16.7, 17.5, 18.2],
  },
  cash_runway: {
    value: '14.5 mo',
    change: 20.8,
    trend: 'up' as const,
    history: [8.2, 9.5, 10.8, 11.9, 12.6, 13.4, 14.5],
  },
  interest_cover: {
    value: '8.4x',
    change: 12.0,
    trend: 'up' as const,
    history: [5.1, 5.8, 6.4, 7.0, 7.5, 7.9, 8.4],
  },
  roce: {
    value: '24.1%',
    change: 5.4,
    trend: 'up' as const,
    history: [18.9, 19.8, 20.9, 21.7, 22.5, 23.2, 24.1],
  },
  bookings: {
    value: '€700K',
    change: 0,
    trend: 'neutral' as const,
    history: [700000],
  },
  current_period: 'Jul 2025 – Dec 2025',
  prior_period: 'Jul 2024 – Dec 2024',
  data_extracted_at: '2026-03-19T08:38:00',
}

export const mockChartData = [
  { period: 'Jan', revenue: 60000, ebitda: null, cash: null },
  { period: 'Feb', revenue: 75000, ebitda: null, cash: null },
  { period: 'Mar', revenue: 95000, ebitda: null, cash: null },
  { period: 'Apr', revenue: 110000, ebitda: null, cash: null },
  { period: 'May', revenue: 132000, ebitda: null, cash: null },
  { period: 'Jun', revenue: 158000, ebitda: null, cash: null },
  { period: 'Jul', revenue: 185000, ebitda: null, cash: null },
  { period: 'Aug', revenue: 215000, ebitda: null, cash: null },
  { period: 'Sep', revenue: 245000, ebitda: null, cash: null },
  { period: 'Oct', revenue: 280000, ebitda: null, cash: null },
  { period: 'Nov', revenue: 520000, ebitda: null, cash: null },
  { period: 'Dec', revenue: 836991, ebitda: null, cash: null },
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