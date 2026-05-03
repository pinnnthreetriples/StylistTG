import { useQuery } from '@tanstack/react-query'
import { Button, PageHeader, SectionCard, StatusCard, StatusPill } from '@stylisttg/ui'
import { RefreshCw } from 'lucide-react'

import { EMPTY_ACCOUNT_RISK_SUMMARY } from '@/features/accounts/accountRisk'
import { fetchHealth, fetchReady } from '@/lib/api'
import {
  accountRiskSummaryQueryOptions,
  frontendDiagnosticsQueryOptions,
  jobPoliciesQueryOptions,
  workerDiagnosticsQueryOptions,
} from '@/lib/queries'

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
  const diagnosticsQuery = useQuery(frontendDiagnosticsQueryOptions())
  const workerDiagnosticsQuery = useQuery(workerDiagnosticsQueryOptions())
  const jobPoliciesQuery = useQuery(jobPoliciesQueryOptions())
  const accountRiskQuery = useQuery(accountRiskSummaryQueryOptions())
  const ready = readyQuery.data
  const diagnostics = diagnosticsQuery.data
  const workerDiagnostics = workerDiagnosticsQuery.data
  const jobPolicies = jobPoliciesQuery.data
  const riskSummary = accountRiskQuery.data ?? EMPTY_ACCOUNT_RISK_SUMMARY

  function refresh() {
    void healthQuery.refetch()
    void readyQuery.refetch()
    void diagnosticsQuery.refetch()
    void workerDiagnosticsQuery.refetch()
    void jobPoliciesQuery.refetch()
    void accountRiskQuery.refetch()
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
          <StatusCard
            label="App environment"
            value={diagnostics?.app_env ?? 'checking'}
            tone={diagnostics?.app_env === 'staging' ? 'info' : 'neutral'}
          />
          <StatusCard
            label="Auth mode"
            value={diagnostics?.auth_mode ?? 'checking'}
            tone={diagnostics?.auth_mode === 'supabase_jwt' ? 'info' : 'warning'}
          />
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <StatusCard
            label="Storage backend"
            value={diagnostics?.storage.backend ?? 'checking'}
            tone={diagnostics?.storage.backend === 's3' ? 'info' : 'neutral'}
            detail={diagnostics ? storageDetail(diagnostics.storage) : undefined}
          />
          <StatusCard
            label="Last checked"
            value={diagnostics?.generated_at ? new Date(diagnostics.generated_at).toLocaleTimeString() : 'checking'}
            detail="Backend diagnostics timestamp"
          />
          <StatusCard
            label="Staging smoke"
            value="external command"
            tone="neutral"
            detail="Run staging_smoke for full Neon/Supabase/Redis/B2 coverage."
          />
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <StatusCard
            label="TDLib live"
            value={diagnostics?.tdlib.live_enabled ? 'enabled' : 'disabled'}
            tone={diagnostics?.tdlib.live_enabled ? 'danger' : 'ok'}
            detail={diagnostics ? `runtime ${diagnostics.tdlib.runtime_mode}; worker ${workerDiagnostics?.tdlib.adapter ?? 'checking'}` : 'backend diagnostics'}
          />
          <StatusCard
            label="TDLib library"
            value={diagnostics?.tdlib.library_loadable ? 'loadable' : diagnostics?.tdlib.library_configured ? 'configured' : 'not configured'}
            tone={diagnostics?.tdlib.library_loadable ? 'ok' : diagnostics?.tdlib.library_configured ? 'warning' : 'neutral'}
            detail="No raw TDLib paths are exposed."
          />
          <StatusCard
            label="Auth worker"
            value={diagnostics?.tdlib.auth_worker_ready ? 'ready' : 'checking'}
            tone={diagnostics?.tdlib.auth_worker_ready ? 'ok' : 'neutral'}
            detail={diagnostics?.tdlib.readonly_smoke_available ? 'read-only smoke available' : 'read-only smoke disabled'}
          />
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <StatusCard
            label="API credentials"
            value={diagnostics?.tdlib.api_id_configured ? 'api id configured' : 'not configured'}
            tone={diagnostics?.tdlib.api_id_configured && diagnostics?.tdlib.api_hash_configured ? 'ok' : 'neutral'}
            detail="Only configured flags are shown; hash value is never exposed."
          />
          <StatusCard
            label="Scheduler"
            value={workerDiagnostics?.scheduler.enabled ? 'enabled' : 'disabled'}
            tone={workerDiagnostics?.scheduler.enabled ? 'warning' : 'ok'}
            detail={workerDiagnostics ? `mode ${workerDiagnostics.scheduler.mode}` : 'worker diagnostics'}
          />
          <StatusCard
            label="Reaper"
            value={workerDiagnostics?.reaper.enabled ? String(workerDiagnostics.reaper.mode) : 'disabled'}
            tone={workerDiagnostics?.reaper.mode === 'execute_safe' ? 'warning' : 'ok'}
            detail="Destructive cleanup is not enabled by default."
          />
        </div>
        {readyQuery.isError ? (
          <div className="mt-4 rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-sm font-semibold text-red-600">
            Readiness diagnostics are unavailable. Check API network access and backend logs.
          </div>
        ) : null}
        {diagnosticsQuery.isError ? (
          <div className="mt-4 rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-700">
            Backend diagnostics summary is unavailable. Readiness may still be available from /ready.
          </div>
        ) : null}
        {workerDiagnosticsQuery.isError ? (
          <div className="mt-4 rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-700">
            Worker diagnostics are unavailable.
          </div>
        ) : null}
      </SectionCard>

      <SectionCard title="Worker execution plane">
        <div className="grid gap-3 md:grid-cols-3">
          <StatusCard
            label="Queue taxonomy"
            value={workerDiagnostics ? workerDiagnostics.queues.length : 'checking'}
            tone="info"
            detail={workerDiagnostics ? workerDiagnostics.queues.map((queue) => queue.name).join(', ') : undefined}
          />
          <StatusCard
            label="Rate limits"
            value={workerDiagnostics?.rate_limits.enabled ? 'configured' : 'checking'}
            tone={workerDiagnostics?.rate_limits.enabled ? 'ok' : 'neutral'}
          />
          <StatusCard
            label="Retry policies"
            value={jobPolicies ? Object.keys(jobPolicies).length : 'checking'}
            tone="info"
            detail="bounded retry decisions by error category"
          />
        </div>
      </SectionCard>

      <SectionCard title="Account risk summary">
        <div className="grid gap-3 md:grid-cols-4">
          <StatusCard label="Total accounts" value={riskSummary.total} tone="neutral" />
          <StatusCard label="Low" value={riskSummary.low} tone="ok" />
          <StatusCard label="Medium/high" value={riskSummary.medium + riskSummary.high} tone="warning" />
          <StatusCard label="Critical" value={riskSummary.critical} tone={riskSummary.critical > 0 ? 'danger' : 'ok'} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <StatusPill tone={riskSummary.reauth_required > 0 ? 'red' : 'green'}>
            Reauth required: {riskSummary.reauth_required}
          </StatusPill>
          <StatusPill tone={riskSummary.missing_session + riskSummary.runtime_unhealthy > 0 ? 'amber' : 'green'}>
            Runtime problems: {riskSummary.missing_session + riskSummary.runtime_unhealthy}
          </StatusPill>
          <StatusPill tone={riskSummary.proxy_problem > 0 ? 'amber' : 'green'}>
            Proxy problems: {riskSummary.proxy_problem}
          </StatusPill>
        </div>
        {accountRiskQuery.isError ? (
          <div className="mt-4 rounded-lg border border-amber-100 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-700">
            Account risk summary is unavailable.
          </div>
        ) : null}
      </SectionCard>
    </div>
  )
}

function storageDetail(storage: {
  bucket_configured: boolean
  signed_url_enabled: boolean
  public_base_url_configured: boolean
}): string {
  const bucket = storage.bucket_configured ? 'bucket configured' : 'bucket missing'
  const signedUrls = storage.signed_url_enabled ? 'signed URLs enabled' : 'signed URLs off'
  const publicBase = storage.public_base_url_configured ? 'public base configured' : 'private/object URLs only'
  return `${bucket}; ${signedUrls}; ${publicBase}`
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
