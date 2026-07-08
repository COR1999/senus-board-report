// Shared "filter by year/month" logic for Reports and Documents -- both
// tables only have a reliable structured date on `created_at` (Reports'
// `summary.reporting_period` is free-text, AI-extracted, and not
// guaranteed to follow any fixed format, so it's not safe to filter on).
// Options are derived from the dates actually present in the fetched data,
// not a full static calendar -- with only a handful of real
// documents/reports, a generated list of every possible month would be
// almost entirely empty options.

export interface PeriodOption {
  /** "2026-07" -- sortable, stable value for the <Select>. */
  value: string
  /** "July 2026" -- shown to the user. */
  label: string
}

function yearMonthValue(isoDate: string): string | null {
  const date = new Date(isoDate)
  if (Number.isNaN(date.getTime())) return null
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
}

/** Distinct year-month options present in `dates`, newest first. */
export function buildPeriodOptions(dates: string[]): PeriodOption[] {
  const seen = new Map<string, PeriodOption>()
  for (const isoDate of dates) {
    const value = yearMonthValue(isoDate)
    if (!value || seen.has(value)) continue
    const label = new Date(isoDate).toLocaleDateString('en-US', { year: 'numeric', month: 'long' })
    seen.set(value, { value, label })
  }
  return Array.from(seen.values()).sort((a, b) => b.value.localeCompare(a.value))
}

/** Whether `isoDate` falls in the given "YYYY-MM" period value. */
export function matchesPeriod(isoDate: string, periodValue: string): boolean {
  return yearMonthValue(isoDate) === periodValue
}
