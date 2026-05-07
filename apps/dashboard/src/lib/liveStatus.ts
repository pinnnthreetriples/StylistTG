import type { fetchFrontendDiagnosticsSummary, fetchWorkerDiagnostics } from '@/lib/api'

type FrontendDiagnostics = Awaited<ReturnType<typeof fetchFrontendDiagnosticsSummary>>
type WorkerDiagnostics = Awaited<ReturnType<typeof fetchWorkerDiagnostics>>

export type LiveStatus = {
  ready: boolean
  enabled: boolean
  label: string
  tone: 'green' | 'amber' | 'red' | 'muted'
}

export function getLiveStatus(
  diagnostics?: FrontendDiagnostics,
  workerDiagnostics?: WorkerDiagnostics,
): LiveStatus {
  const workerTdlib = workerDiagnostics?.tdlib
  const frontendTdlib = diagnostics?.tdlib
  const ready = Boolean(workerTdlib?.execution_plane_ready || frontendTdlib?.execution_plane_ready)
  const enabled = Boolean(workerTdlib?.live_enabled || frontendTdlib?.live_enabled)

  if (ready) {
    return {
      ready: true,
      enabled: true,
      label: 'Live-режим готов',
      tone: 'green',
    }
  }

  if (enabled) {
    return {
      ready: false,
      enabled: true,
      label: 'Live-режим требует проверки',
      tone: 'amber',
    }
  }

  return {
    ready: false,
    enabled: false,
    label: 'Отключён безопасно',
    tone: 'amber',
  }
}
