import { Button } from '@stylisttg/ui'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ShieldOff } from 'lucide-react'
import { useState } from 'react'

import { accountSafetyGateQueryOptions } from '@/lib/queries'
import type { SafetyGateIntent, SafetyGateVerdict } from '@/lib/api'

type SafetyGateBannerProps = {
  accountId: string
  intent: SafetyGateIntent
}

export function SafetyGateBanner({ accountId, intent }: SafetyGateBannerProps) {
  const [expanded, setExpanded] = useState(false)
  const query = useQuery(accountSafetyGateQueryOptions(accountId, intent))

  if (query.isLoading) {
    return (
      <div className="h-12 animate-pulse rounded-lg border border-border bg-card px-3 py-2">
        <div className="h-2 w-40 rounded-full bg-muted" />
        <div className="mt-2 h-2 w-64 rounded-full bg-muted" />
      </div>
    )
  }

  if (query.isError) {
    return <p className="text-xs text-muted-foreground">Safety gate unavailable.</p>
  }

  const verdict = query.data
  if (!verdict || verdict.severity === 'ok') return null

  const blocked = verdict.severity === 'blocked'
  const Icon = blocked ? ShieldOff : AlertTriangle
  const toneClass = blocked
    ? 'border-destructive/20 bg-destructive/10 text-destructive'
    : 'border-border bg-muted text-muted-foreground'
  const iconClass = blocked ? 'text-destructive' : 'text-muted-foreground'
  const firstReason = verdict.reasons[0]
  const extraCount = Math.max(0, verdict.reasons.length - 1)
  const message = firstReason
    ? `${firstReason.message}${extraCount > 0 ? ` and ${extraCount} more` : ''}`
    : 'Safety gate returned a non-ok verdict.'

  return (
    <div className={`rounded-lg border px-3 py-3 text-sm shadow-sm ${toneClass}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2">
          <Icon className={`mt-0.5 size-4 shrink-0 ${iconClass}`} aria-hidden="true" />
          <div className="min-w-0">
            <div className="font-semibold">{blocked ? 'Account safety blocked' : 'Account safety warning'}</div>
            <div className="mt-0.5 break-words text-xs opacity-85">{message}</div>
          </div>
        </div>
        {verdict.reasons.length > 0 ? (
          <Button type="button" variant="secondary" size="sm" onClick={() => setExpanded((value) => !value)}>
            See details
          </Button>
        ) : null}
      </div>

      {expanded ? <ReasonDetails verdict={verdict} /> : null}
    </div>
  )
}

function ReasonDetails({ verdict }: { verdict: SafetyGateVerdict }) {
  return (
    <div className="mt-3 space-y-2 border-t border-current/15 pt-3">
      {verdict.reasons.map((reason) => (
        <div key={`${reason.code}:${reason.severity}`} className="rounded-md bg-card/70 px-2.5 py-2 text-xs">
          <div className="font-semibold">{reason.code}</div>
          <div className="mt-0.5">{reason.message}</div>
          {reason.metadata && Object.keys(reason.metadata).length > 0 ? (
            <pre className="mt-1 max-h-28 overflow-auto whitespace-pre-wrap rounded bg-foreground/5 p-2 text-[11px]">
              {JSON.stringify(reason.metadata, null, 2)}
            </pre>
          ) : null}
        </div>
      ))}
    </div>
  )
}
