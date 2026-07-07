// The assignment's 5 required KPI categories (see project_assignment_context)
// -- single source of truth so dashboard-container.tsx's stat strip and
// lib/insights.ts's AI commentary tag insights against the same taxonomy.
export const KPI_CATEGORIES = [
  'Growth & Revenue',
  'Profitability',
  'Cash & Liquidity',
  'Solvency & Leverage',
  'Returns',
] as const

export type KpiCategory = (typeof KPI_CATEGORIES)[number]
