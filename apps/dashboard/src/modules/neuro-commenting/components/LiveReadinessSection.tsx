import { Card, Skeleton } from '@stylisttg/ui'
import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react'

import { useNeuroLiveReadiness } from '../hooks'
import type { NeuroLiveReadiness } from '../types'

export function LiveReadinessSection({ campaignId }: { campaignId: string }) {
  const readinessQuery = useNeuroLiveReadiness(campaignId)

  if (readinessQuery.isError) {
    return <Card className="p-4 text-sm text-red-600">Не удалось загрузить live readiness</Card>
  }
  if (readinessQuery.isLoading) return <Skeleton className="h-28 w-full" />

  const readiness = readinessQuery.data
  if (!readiness) return null

  const blockers = readiness.checks.filter((check) => check.severity === 'blocker').length
  const warnings = readiness.checks.filter((check) => check.severity === 'warning').length

  return (
    <Card className="p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">Live readiness</h3>
          <p className="mt-1 text-xs text-gray-500">
            {blockers} blockers / {warnings} warnings
          </p>
        </div>
        <div
          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${
            readiness.ready ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'
          }`}
        >
          {readiness.ready ? <CheckCircle2 className="size-3.5" /> : <XCircle className="size-3.5" />}
          {readiness.ready ? 'Ready' : 'Not ready'}
        </div>
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        {readiness.checks.map((check) => (
          <ReadinessCheckRow key={`${check.code}-${check.message}`} check={check} />
        ))}
      </div>
    </Card>
  )
}

function ReadinessCheckRow({ check }: { check: NeuroLiveReadiness['checks'][number] }) {
  const style = severityStyle(check.severity)
  const Icon = check.severity === 'blocker' ? AlertTriangle : check.severity === 'warning' ? XCircle : Info

  return (
    <div className={`flex min-h-12 items-start gap-2 rounded-md border px-3 py-2 text-xs ${style}`}>
      <Icon className="mt-0.5 size-3.5 shrink-0" />
      <div className="min-w-0">
        <p className="font-semibold">{check.code}</p>
        <p className="mt-0.5 break-words leading-5">{check.message}</p>
      </div>
    </div>
  )
}

function severityStyle(severity: NeuroLiveReadiness['checks'][number]['severity']): string {
  if (severity === 'blocker') return 'border-red-100 bg-red-50 text-red-700'
  if (severity === 'warning') return 'border-amber-100 bg-amber-50 text-amber-700'
  return 'border-gray-100 bg-gray-50 text-gray-600'
}
