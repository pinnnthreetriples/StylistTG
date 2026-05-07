import type { fetchFrontendDiagnosticsSummary, fetchWorkerDiagnostics } from '@/lib/api'

type FrontendDiagnostics = Awaited<ReturnType<typeof fetchFrontendDiagnosticsSummary>>
type WorkerDiagnostics = Awaited<ReturnType<typeof fetchWorkerDiagnostics>>

export type LiveStatus = {
  ready: boolean
  enabled: boolean
  label: string
  tone: 'green' | 'amber' | 'red' | 'muted'
}

export function liveStatusCardTone(status: LiveStatus): 'ok' | 'warning' | 'danger' | 'neutral' {
  if (status.tone === 'green') return 'ok'
  if (status.tone === 'red') return 'danger'
  if (status.tone === 'amber') return 'warning'
  return 'neutral'
}

export function getLiveStatus(
  diagnostics?: FrontendDiagnostics,
  workerDiagnostics?: WorkerDiagnostics,
): LiveStatus {
  if (!diagnostics && !workerDiagnostics) {
    return {
      ready: false,
      enabled: false,
      label: 'Live-статус проверяется',
      tone: 'muted',
    }
  }

  const workerTdlib = workerDiagnostics?.tdlib
  const frontendTdlib = diagnostics?.tdlib
  const ready = Boolean(workerTdlib?.execution_plane_ready || frontendTdlib?.execution_plane_ready)
  const enabled = Boolean(workerTdlib?.live_enabled || frontendTdlib?.live_enabled)

  if (ready && enabled) {
    return {
      ready: true,
      enabled: true,
      label: 'Live-режим включён',
      tone: 'green',
    }
  }

  if (ready) {
    return {
      ready: true,
      enabled: false,
      label: 'Live-инфраструктура готова, запуск выключен',
      tone: 'amber',
    }
  }

  if (enabled) {
    return {
      ready: false,
      enabled: true,
      label: 'Live включён, среда не готова',
      tone: 'red',
    }
  }

  return {
    ready: false,
    enabled: false,
    label: 'Отключён безопасно',
    tone: 'amber',
  }
}
