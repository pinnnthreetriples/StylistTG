import { Badge, Tooltip } from '@stylisttg/ui'
import { useQuery } from '@tanstack/react-query'

import { fetchProfileCompleteness } from '@/lib/api'

type ProfileCompletenessBarProps = {
  accountId: string
}

export function ProfileCompletenessBar({ accountId }: ProfileCompletenessBarProps) {
  const query = useQuery({
    queryKey: ['profileCompleteness', accountId] as const,
    queryFn: () => fetchProfileCompleteness(accountId),
    enabled: Boolean(accountId),
    staleTime: 60_000,
  })

  if (query.isLoading) {
    return (
      <div className="h-10 animate-pulse rounded-lg border border-border bg-card px-3 py-2">
        <div className="h-2 rounded-full bg-muted" />
        <div className="mt-2 h-2 w-28 rounded-full bg-muted" />
      </div>
    )
  }

  if (query.isError || !query.data) {
    return <p className="text-xs text-muted-foreground">Profile completeness unavailable.</p>
  }

  const report = query.data
  const percentage = Math.round(report.score * 100)
  const barClass = scoreColorClass(report.score)
  const missingText = formatMissing(report.missing_required, report.missing_recommended)

  return (
    <Tooltip content={missingText} side="bottom" className="w-full">
      <div
        className="rounded-lg border border-border bg-card px-3 py-2 text-xs text-muted-foreground shadow-sm"
        title={missingText}
      >
        <div className="mb-1.5 flex items-center justify-between gap-3">
          <span className="font-medium text-foreground">Profile completeness</span>
          <Badge tone={badgeTone(report.score)}>{percentage}%</Badge>
        </div>
        <div
          aria-label="Profile completeness"
          aria-valuemax={100}
          aria-valuemin={0}
          aria-valuenow={percentage}
          className="h-1.5 overflow-hidden rounded-full bg-muted"
          role="progressbar"
        >
          <div className={`h-full rounded-full ${barClass}`} style={{ width: `${percentage}%` }} />
        </div>
      </div>
    </Tooltip>
  )
}

function scoreColorClass(score: number): string {
  if (score < 0.5) return 'bg-destructive'
  if (score < 0.8) return 'bg-muted'
  return 'bg-muted'
}

function badgeTone(score: number): 'red' | 'amber' | 'green' {
  if (score < 0.5) return 'red'
  if (score < 0.8) return 'amber'
  return 'green'
}

function formatMissing(required: string[], recommended: string[]): string {
  const parts = []
  if (required.length > 0) parts.push(`Required: ${required.join(', ')}`)
  if (recommended.length > 0) parts.push(`Recommended: ${recommended.join(', ')}`)
  return parts.length > 0 ? parts.join(' · ') : 'All profile fields are complete.'
}
