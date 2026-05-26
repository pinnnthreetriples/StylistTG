import { Badge, Button } from '@stylisttg/ui'
import { ShieldCheck, TimerReset } from 'lucide-react'
import { useEffect, useState } from 'react'

import { dashboardApiClient } from '@/lib/apiClient'

export type BoughtOnboardingStep =
  | 'enable_2fa'
  | 'terminate_other_sessions'
  | 'rest_period'
  | 'ggr_precheck'
  | 'completed'

export type BoughtOnboardingStatus = {
  account_id: string
  current_step: BoughtOnboardingStep
  completion_percent: number
  started_at: string
  completed_at: string | null
  details_json: Record<string, unknown>
}

type BoughtAccountOnboardingWizardProps = {
  accountId: string
  initialStatus?: BoughtOnboardingStatus | null
}

const STEP_LABELS: Record<BoughtOnboardingStep, string> = {
  enable_2fa: 'Enable 2FA',
  terminate_other_sessions: 'Terminate sessions',
  rest_period: 'Rest period',
  ggr_precheck: 'GGR pre-check',
  completed: 'Ready',
}

const STEPS: BoughtOnboardingStep[] = [
  'enable_2fa',
  'terminate_other_sessions',
  'rest_period',
  'ggr_precheck',
]

export function BoughtAccountOnboardingWizard({
  accountId,
  initialStatus,
}: BoughtAccountOnboardingWizardProps) {
  const [status, setStatus] = useState<BoughtOnboardingStatus | null | undefined>(initialStatus)
  const [isStarting, setIsStarting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (initialStatus !== undefined) return
    let cancelled = false
    dashboardApiClient
      .request<BoughtOnboardingStatus>(
        `/api/accounts/${encodeURIComponent(accountId)}/bought-onboarding/status`,
      )
      .then((payload) => {
        if (!cancelled) setStatus(payload)
      })
      .catch(() => {
        if (!cancelled) setStatus(null)
      })
    return () => {
      cancelled = true
    }
  }, [accountId, initialStatus])

  async function startOnboarding() {
    setIsStarting(true)
    setError(null)
    try {
      const payload = await dashboardApiClient.request<BoughtOnboardingStatus>(
        `/api/accounts/${encodeURIComponent(accountId)}/bought-onboarding/start`,
        { method: 'POST' },
      )
      setStatus(payload)
    } catch {
      setError('Could not start bought-account onboarding.')
    } finally {
      setIsStarting(false)
    }
  }

  const currentStep = status?.current_step ?? 'enable_2fa'
  const completion = status?.completion_percent ?? 0

  return (
    <section className="rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="size-4 text-primary" aria-hidden="true" />
          <h3 className="text-sm font-semibold text-foreground">Bought-account onboarding</h3>
        </div>
        <Badge tone={status?.completed_at ? 'green' : 'amber'}>{completion}%</Badge>
      </div>

      <div className="mt-4 grid gap-2">
        {STEPS.map((step) => {
          const isCurrent = step === currentStep
          return (
            <div
              className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm"
              key={step}
            >
              <span className={isCurrent ? 'font-medium text-foreground' : 'text-muted-foreground'}>
                {STEP_LABELS[step]}
              </span>
              <Badge tone={isCurrent ? 'amber' : 'gray'}>{isCurrent ? 'Current' : 'Queued'}</Badge>
            </div>
          )
        })}
      </div>

      {error ? <p className="mt-3 text-xs text-destructive">{error}</p> : null}

      {!status ? (
        <Button
          className="mt-4"
          disabled={isStarting}
          icon={<TimerReset className="size-4" />}
          onClick={startOnboarding}
          type="button"
        >
          Start onboarding
        </Button>
      ) : null}
    </section>
  )
}
