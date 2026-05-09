import { describe, expect, it } from 'vitest'

import { getLiveStatus } from '@/lib/liveStatus'
import type { WorkerDiagnostics } from '@/lib/api'

function workerDiagnostics(liveEnabled: boolean, executionPlaneReady: boolean): WorkerDiagnostics {
  return {
    queues: [],
    mode: 'redis_rq',
    redis: {},
    scheduler: {},
    reaper: {},
    rate_limits: {},
    tdlib: {
      live_enabled: liveEnabled,
      execution_plane_ready: executionPlaneReady,
    },
  }
}

describe('getLiveStatus', () => {
  it('does not claim a live state while diagnostics are missing', () => {
    expect(getLiveStatus()).toMatchObject({
      enabled: false,
      ready: false,
      label: 'Live-статус проверяется',
      tone: 'muted',
    })
  })

  it('shows green only when live execution is enabled and ready', () => {
    expect(
      getLiveStatus(
        undefined,
        workerDiagnostics(true, true),
      ),
    ).toMatchObject({
      enabled: true,
      ready: true,
      label: 'Live-режим включён',
      tone: 'green',
    })
  })

  it('does not show green when live infrastructure is ready but execution is disabled', () => {
    expect(
      getLiveStatus(
        undefined,
        workerDiagnostics(false, true),
      ),
    ).toMatchObject({
      enabled: false,
      ready: true,
      label: 'Live-инфраструктура готова, запуск выключен',
      tone: 'amber',
    })
  })

  it('warns when live execution is enabled but infrastructure is not ready', () => {
    expect(
      getLiveStatus(
        undefined,
        workerDiagnostics(true, false),
      ),
    ).toMatchObject({
      enabled: true,
      ready: false,
      label: 'Live включён, среда не готова',
      tone: 'red',
    })
  })
})
