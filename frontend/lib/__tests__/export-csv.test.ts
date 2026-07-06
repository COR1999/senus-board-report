import { describe, it, expect, vi, beforeEach } from 'vitest'
import { reportsToCsv, exportReportsToCsv } from '@/lib/export-csv'
import type { Report } from '@/lib/data-service'

const reports: Report[] = [
  {
    id: 1,
    document_id: 101,
    summary: { company_name: 'Senus PLC', reporting_period: 'H1 2025' },
    status: 'completed',
    created_at: '2025-12-31T00:00:00Z',
  },
  {
    id: 2,
    document_id: 102,
    summary: null,
    status: 'failed',
    created_at: '2025-09-30T00:00:00Z',
  },
]

describe('reportsToCsv', () => {
  it('includes a header row and one row per report', () => {
    const csv = reportsToCsv(reports)
    const lines = csv.split('\n')
    expect(lines).toHaveLength(3)
    expect(lines[0]).toBe('Report Name,Reporting Period,Status,Created At')
  })

  it('falls back to Document #<id> when summary is null', () => {
    const csv = reportsToCsv(reports)
    expect(csv).toContain('Document #102')
  })

  it('quotes and escapes fields containing commas or quotes', () => {
    const withComma: Report[] = [
      {
        id: 3,
        document_id: 103,
        summary: { company_name: 'Acme, Inc. "The Best"', reporting_period: null },
        status: 'completed',
        created_at: '2025-01-01T00:00:00Z',
      },
    ]
    const csv = reportsToCsv(withComma)
    expect(csv).toContain('"Acme, Inc. ""The Best"""')
  })
})

describe('exportReportsToCsv', () => {
  beforeEach(() => {
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:mock-url'),
      revokeObjectURL: vi.fn(),
    })
  })

  it('does nothing when there are no reports', () => {
    const spy = vi.spyOn(document, 'createElement')
    exportReportsToCsv([])
    expect(spy).not.toHaveBeenCalled()
  })

  it('creates and clicks a download link for non-empty reports', () => {
    const clickSpy = vi.fn()
    const linkStub = { href: '', download: '', click: clickSpy } as unknown as HTMLAnchorElement
    vi.spyOn(document, 'createElement').mockReturnValue(linkStub)

    exportReportsToCsv(reports, 'test.csv')

    expect(linkStub.download).toBe('test.csv')
    expect(clickSpy).toHaveBeenCalledOnce()
  })
})
