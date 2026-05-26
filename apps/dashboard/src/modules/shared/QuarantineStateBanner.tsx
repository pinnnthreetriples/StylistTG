import { Button, Badge } from '@stylisttg/ui'
import { useEffect, useState } from 'react'

import { dashboardApiClient } from '@/lib/apiClient'

import { buildReleaseQuarantinePayload } from './quarantineReleasePayload'

export type AccountQuarantine = {
  id: string
  workspace_id: string
  account_id: string
  reason: 'flood_wait' | 'status_degraded' | 'manual' | 'bought_rest_period' | 'fraud_high'
  started_at: string
  until: string
  released_at: string | null
  released_by_user_id: string | null
  metadata_json: Record<string, unknown>
}

type QuarantineStateBannerProps = {
  accountId: string
  isAdmin?: boolean
  compact?: boolean
  initialQuarantine?: AccountQuarantine | null
  defaultReleaseModalOpen?: boolean
}

export function QuarantineStateBanner({
  accountId,
  isAdmin = false,
  compact = false,
  initialQuarantine,
  defaultReleaseModalOpen = false,
}: QuarantineStateBannerProps) {
  const [quarantine, setQuarantine] = useState<AccountQuarantine | null | undefined>(initialQuarantine)
  const [isModalOpen, setIsModalOpen] = useState(defaultReleaseModalOpen)
  const [reason, setReason] = useState('')
  const [overrideGateBlock, setOverrideGateBlock] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (initialQuarantine !== undefined) return
    let cancelled = false
    dashboardApiClient
      .request<AccountQuarantine | null>(`/api/accounts/${encodeURIComponent(accountId)}/quarantine`)
      .then((row) => {
        if (!cancelled) setQuarantine(row)
      })
      .catch(() => {
        if (!cancelled) setQuarantine(null)
      })
    return () => {
      cancelled = true
    }
  }, [accountId, initialQuarantine])

  if (!quarantine) return null

  const label = `В карантине до ${formatQuarantineUntil(quarantine.until)}`

  async function releaseEarly() {
    if (!quarantine) return
    setIsSubmitting(true)
    setError(null)
    try {
      const released = await dashboardApiClient.request<AccountQuarantine>(
        `/api/accounts/${encodeURIComponent(accountId)}/quarantine/release`,
        {
          method: 'POST',
          body: JSON.stringify(buildReleaseQuarantinePayload(reason, overrideGateBlock)),
        },
      )
      setQuarantine(released.released_at ? null : released)
      setIsModalOpen(false)
      setReason('')
      setOverrideGateBlock(false)
    } catch {
      setError('Не удалось снять карантин')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (compact) {
    return (
      <span className="inline-flex max-w-[12rem] items-center truncate rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
        {label}
      </span>
    )
  }

  return (
    <div className="rounded-xl border border-border bg-muted p-3 text-sm text-muted-foreground">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="amber">{label}</Badge>
          <span className="text-xs text-muted-foreground">{quarantine.reason}</span>
        </div>
        {isAdmin ? (
          <Button type="button" variant="secondary" onClick={() => setIsModalOpen(true)}>
            Release early
          </Button>
        ) : null}
      </div>

      {isModalOpen ? (
        <div className="mt-3 rounded-lg border border-border bg-card p-3">
          <label className="grid gap-1 text-xs font-medium text-foreground">
            Reason
            <textarea
              className="min-h-20 rounded-lg border border-border p-2 text-sm"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          <label className="mt-3 flex items-start gap-2 rounded-lg border border-border bg-muted p-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 rounded border-border text-muted-foreground"
              checked={overrideGateBlock}
              onChange={(event) => setOverrideGateBlock(event.target.checked)}
            />
            <span>Override safety gate block for this release.</span>
          </label>
          <p role="alert" className="mt-2 rounded-lg border border-destructive/20 bg-destructive/10 p-2 text-xs text-destructive">
            When checked, releasing quarantine also grants a 24-hour safety gate override. Use only after manual
            operator verification.
          </p>
          {error ? <p className="mt-2 text-xs text-destructive">{error}</p> : null}
          <div className="mt-3 flex justify-end gap-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setIsModalOpen(false)
                setOverrideGateBlock(false)
              }}
            >
              Cancel
            </Button>
            <Button type="button" onClick={releaseEarly} disabled={isSubmitting}>
              Release early
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}

function formatQuarantineUntil(value: string): string {
  return new Date(value).toLocaleString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    day: '2-digit',
    month: '2-digit',
  })
}
