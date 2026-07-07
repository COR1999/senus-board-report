interface ErrorBannerProps {
  error: string
}

/**
 * Shared inline error banner for page-level fetch failures -- was
 * duplicated identically across dashboard-container.tsx, reports/page.tsx,
 * and documents/page.tsx.
 */
export function ErrorBanner({ error }: ErrorBannerProps) {
  return (
    <div className="mb-4 rounded-lg bg-red-50 p-4 text-red-600 dark:bg-red-950" role="alert">
      Error: {error}
    </div>
  )
}
