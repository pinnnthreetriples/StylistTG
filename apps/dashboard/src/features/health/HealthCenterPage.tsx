import { useQuery } from '@tanstack/react-query'
import { Badge, PageHeader, SectionCard, StatusPill } from '@stylisttg/ui'

import { fetchRuntimeDiagnostics } from '@/lib/api'

export function HealthCenterPage() {
  const diagnosticsQuery = useQuery({
    queryKey: ['saas-health-center', 'runtime-diagnostics'],
    queryFn: fetchRuntimeDiagnostics,
    staleTime: 30_000,
  })
  const diagnostics = diagnosticsQuery.data

  return (
    <div className="mx-auto grid max-w-6xl gap-5 px-5 py-6">
      <PageHeader
        eyebrow="Health Center"
        title="Runtime Readiness"
        description="Read-only diagnostics for API readiness, Redis, database, and TDLib configuration."
      />
      <SectionCard title="Current dependencies">
        <div className="grid gap-3 sm:grid-cols-3">
          <HealthItem label="Database" value={diagnostics?.database} />
          <HealthItem label="Redis" value={diagnostics?.redis} />
          <HealthItem label="TDLib" value={diagnostics?.tdlib} />
        </div>
        {diagnosticsQuery.isError ? (
          <div className="mt-4 rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-sm font-semibold text-red-600">
            Runtime diagnostics are unavailable.
          </div>
        ) : null}
      </SectionCard>
    </div>
  )
}

function HealthItem({ label, value }: { label: string; value?: string }) {
  const current = value ?? 'loading'
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="text-xs font-bold uppercase text-gray-400">{label}</div>
      <div className="mt-2 flex items-center justify-between gap-3">
        <span className="text-sm font-semibold text-navy-900">{current}</span>
        {current === 'ok' ? <StatusPill tone="green">ok</StatusPill> : <Badge tone="gray">{current}</Badge>}
      </div>
    </div>
  )
}
