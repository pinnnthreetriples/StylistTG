import { useQuery } from '@tanstack/react-query'
import { ShieldAlert } from 'lucide-react'

import type { DisasterState } from '@/lib/api'
import { disasterStateQueryOptions } from '@/lib/queries'
import { appRoutes } from '@/lib/routes'

export function DisasterModeBanner() {
  const query = useQuery(disasterStateQueryOptions())
  const state = query.data

  if (!state?.is_disaster) return null

  return (
    <section
      aria-label="Disaster mode"
      className="fixed left-0 right-0 top-14 z-[60] border-b border-destructive/20 bg-destructive text-primary-foreground shadow-lg xl:left-64"
    >
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-3 sm:px-6 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <ShieldAlert className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
          <div className="min-w-0">
            <h2 className="text-sm font-bold">
              Disaster mode: {state.quarantined_count}/{state.total_accounts} accounts in quarantine
            </h2>
            <p className="mt-0.5 text-xs text-primary-foreground/85">Detected {humanizeDetectedAgo(state.detected_at)} ago</p>
            {state.sample_quarantined_account_ids.length > 0 ? (
              <details className="mt-2 text-xs">
                <summary className="cursor-pointer font-semibold text-primary-foreground/90">Sample quarantined accounts</summary>
                <div className="mt-2 flex flex-wrap gap-2">
                  {state.sample_quarantined_account_ids.map((accountId) => (
                    <a
                      className="rounded-md bg-card/15 px-2 py-1 font-mono text-[11px] text-primary-foreground underline-offset-2 hover:bg-card/25 hover:underline"
                      href={appRoutes.account(accountId)}
                      key={accountId}
                    >
                      {accountId}
                    </a>
                  ))}
                </div>
              </details>
            ) : null}
          </div>
        </div>
        <a
          className="inline-flex h-9 shrink-0 items-center justify-center rounded-md border border-background/30 bg-card px-3 text-sm font-semibold text-destructive transition hover:bg-destructive/10"
          href={buildDisasterSupportHref(state)}
        >
          Escalate to support
        </a>
      </div>
    </section>
  )
}

function buildDisasterSupportHref(state: DisasterState): string {
  const subject = encodeURIComponent(
    `Disaster mode: ${state.quarantined_count}/${state.total_accounts} accounts in quarantine`,
  )
  return `mailto:support@?subject=${subject}`
}

function humanizeDetectedAgo(value: string): string {
  const detectedAt = new Date(value).getTime()
  if (!Number.isFinite(detectedAt)) return 'moments'

  const elapsedSeconds = Math.max(0, Math.floor((Date.now() - detectedAt) / 1000))
  if (elapsedSeconds < 60) return 'less than 1 minute'

  const elapsedMinutes = Math.floor(elapsedSeconds / 60)
  if (elapsedMinutes < 60) return `${elapsedMinutes} ${elapsedMinutes === 1 ? 'minute' : 'minutes'}`

  const elapsedHours = Math.floor(elapsedMinutes / 60)
  if (elapsedHours < 24) return `${elapsedHours} ${elapsedHours === 1 ? 'hour' : 'hours'}`

  const elapsedDays = Math.floor(elapsedHours / 24)
  return `${elapsedDays} ${elapsedDays === 1 ? 'day' : 'days'}`
}
