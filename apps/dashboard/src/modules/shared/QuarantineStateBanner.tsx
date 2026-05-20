import { Button, Badge } from '@stylisttg/ui'
import { useEffect, useState } from 'react'

import { dashboardApiClient } from '@/lib/apiClient'

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
}

export function QuarantineStateBanner({
  accountId,
  isAdmin = false,
  compact = false,
  initialQuarantine,
}: QuarantineStateBannerProps) {
  const [quarantine, setQuarantine] = useState<AccountQuarantine | null | undefined>(initialQuarantine)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [reason, setReason] = useState('')
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
          body: JSON.stringify({ reason: reason || null, override_gate_block: false }),
        },
      )
      setQuarantine(released.released_at ? null : released)
      setIsModalOpen(false)
      setReason('')
    } catch {
      setError('Не удалось снять карантин')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (compact) {
    return (
      <span className="inline-flex max-w-[12rem] items-center truncate rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
        {label}
      </span>
    )
  }

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="amber">{label}</Badge>
          <span className="text-xs text-amber-700">{quarantine.reason}</span>
        </div>
        {isAdmin ? (
          <Button type="button" variant="secondary" onClick={() => setIsModalOpen(true)}>
            Release early
          </Button>
        ) : null}
      </div>

      {isModalOpen ? (
        <div className="mt-3 rounded-lg border border-amber-200 bg-white p-3">
          <label className="grid gap-1 text-xs font-medium text-gray-700">
            Reason
            <textarea
              className="min-h-20 rounded-lg border border-gray-200 p-2 text-sm"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          {error ? <p className="mt-2 text-xs text-red-600">{error}</p> : null}
          <div className="mt-3 flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => setIsModalOpen(false)}>
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

export function formatQuarantineUntil(value: string): string {
  return new Date(value).toLocaleString('ru-RU', {
    hour: '2-digit',
    minute: '2-digit',
    day: '2-digit',
    month: '2-digit',
  })
}
