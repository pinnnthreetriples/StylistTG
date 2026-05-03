import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Button, PageHeader, SectionCard, StatusCard, StatusPill } from '@stylisttg/ui'
import { RefreshCw } from 'lucide-react'

import { buildAccountRisk, summarizeAccountRisks } from '@/features/accounts/accountRisk'
import { fetchHealth, fetchReady } from '@/lib/api'
import { accountSafetySummaryQueryOptions, accountsQueryOptions, proxySummaryQueryOptions } from '@/lib/queries'

export function HealthCenterPage() {
  const healthQuery = useQuery({
    queryKey: ['saas-health-center', 'health'],
    queryFn: fetchHealth,
    staleTime: 30_000,
  })
  const readyQuery = useQuery({
    queryKey: ['saas-health-center', 'ready'],
    queryFn: fetchReady,
    staleTime: 30_000,
  })
  const accountsQuery = useQuery(accountsQueryOptions())
  const safetySummaryQuery = useQuery(accountSafetySummaryQueryOptions())
  const proxySummaryQuery = useQuery(proxySummaryQueryOptions())

  const riskSummary = useMemo(() => {
    const safetyByAccount = new Map((safetySummaryQuery.data ?? []).map((item) => [item.account_id, item]))
    const proxyByAccount = new Map((proxySummaryQuery.data ?? []).map((item) => [item.account_id, item]))
    return summarizeAccountRisks(
      (accountsQuery.data ?? []).map((account) =>
        buildAccountRisk(account, safetyByAccount.get(account.account_id), proxyByAccount.get(account.account_id)),
      ),
    )
  }, [accountsQuery.data, proxySummaryQuery.data, safetySummaryQuery.data])

  const ready = readyQuery.data
  const appEnv = import.meta.env.VITE_APP_ENV?.trim() || 'local'
  const authMode = import.meta.env.VITE_SUPABASE_URL ? 'supabase_jwt' : 'local/dev'
  const storageBackend = appEnv === 'staging' ? 's3' : 'local/dev'

  function refresh() {
    void healthQuery.refetch()
    void readyQuery.refetch()
    void accountsQuery.refetch()
    void safetySummaryQuery.refetch()
    void proxySummaryQuery.refetch()
  }

  return (
    <div className="mx-auto grid max-w-6xl gap-5 px-5 py-6">
      <PageHeader
        eyebrow="Health Center"
        title="Runtime Readiness"
        description="Read-only diagnostics for API readiness, dependencies, account risk, and staging smoke posture."
        actions={
          <Button onClick={refresh} type="button" variant="secondary">
            <RefreshCw className="size-4" />
            Retry
          </Button>
        }
      />

      <SectionCard title="Service readiness">
        <div className="grid gap-3 md:grid-cols-3">
          <StatusCard
            label="API process"
            value={healthQuery.data?.status ?? (healthQuery.isError ? 'down' : 'checking')}
            tone={healthQuery.data?.status === 'ok' ? 'ok' : healthQuery.isError ? 'danger' : 'neutral'}
            detail="GET /health"
          />
          <HealthStatusCard label="Database" value={ready?.database} />
          <HealthStatusCard label="Redis" value={ready?.redis} />
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <HealthStatusCard label="TDLib" value={ready?.tdlib} notConfiguredTone="warning" />
          <StatusCard label="App environment" value={appEnv} tone={appEnv === 'staging' ? 'info' : 'neutral'} />
          <StatusCard label="Auth mode" value={authMode} tone={authMode === 'supabase_jwt' ? 'info' : 'warning'} />
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <StatusCard label="Storage backend" value={storageBackend} tone={storageBackend === 's3' ? 'info' : 'neutral'} />
          <StatusCard label="Last checked" value={new Date().toLocaleTimeString()} detail="Browser-side timestamp" />
          <StatusCard
            label="Staging smoke"
            value="external command"
            tone="neutral"
            detail="Run staging_smoke for full Neon/Supabase/Redis/B2 coverage."
          />
        </div>
        {readyQuery.isError ? (
          <div className="mt-4 rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-sm font-semibold text-red-600">
            Readiness diagnostics are unavailable. Check API network access and backend logs.
          </div>
        ) : null}
      </SectionCard>

      <SectionCard title="Account risk summary">
        <div className="grid gap-3 md:grid-cols-4">
          <StatusCard label="Total accounts" value={riskSummary.total} tone="neutral" />
          <StatusCard label="Low" value={riskSummary.low} tone="ok" />
          <StatusCard label="Medium/high" value={riskSummary.medium + riskSummary.high} tone="warning" />
          <StatusCard label="Critical" value={riskSummary.critical} tone={riskSummary.critical > 0 ? 'danger' : 'ok'} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <StatusPill tone={riskSummary.requiringReauth > 0 ? 'red' : 'green'}>
            Reauth required: {riskSummary.requiringReauth}
          </StatusPill>
          <StatusPill tone={riskSummary.withoutSession > 0 ? 'amber' : 'green'}>
            Runtime problems: {riskSummary.withoutSession}
          </StatusPill>
          <StatusPill tone={riskSummary.proxyProblems > 0 ? 'amber' : 'green'}>
            Proxy problems: {riskSummary.proxyProblems}
          </StatusPill>
        </div>
      </SectionCard>
    </div>
  )
}

function HealthStatusCard({
  label,
  notConfiguredTone = 'neutral',
  value,
}: {
  label: string
  notConfiguredTone?: 'neutral' | 'warning'
  value?: string
}) {
  const current = value ?? 'checking'
  const tone = current === 'ok' ? 'ok' : current === 'not_configured' ? notConfiguredTone : current === 'checking' ? 'neutral' : 'danger'
  return <StatusCard label={label} value={current} tone={tone} detail={current === 'not_configured' ? 'Allowed for mock staging.' : undefined} />
}
