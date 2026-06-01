import { describe, expect, it } from 'vitest'

import type { WorkerDiagnostics } from '@/lib/api'
import { hasConfiguredRateLimits } from '@/lib/workerDiagnostics'

function workerDiagnostics(rateLimits: WorkerDiagnostics['rate_limits']): WorkerDiagnostics {
  return {
    queues: [],
    mode: 'redis_rq',
    redis: {},
    scheduler: {},
    reaper: {},
    rate_limits: rateLimits,
    tdlib: {},
  }
}

describe('hasConfiguredRateLimits', () => {
  it('waits while worker diagnostics are missing', () => {
    expect(hasConfiguredRateLimits()).toBe(false)
  })

  it('treats a non-empty rate limit map as configured', () => {
    expect(
      hasConfiguredRateLimits(
        workerDiagnostics({
          auth_jobs_per_tenant_per_hour: 10,
        }),
      ),
    ).toBe(true)
  })

  it('keeps an empty rate limit map in checking state', () => {
    expect(hasConfiguredRateLimits(workerDiagnostics({}))).toBe(false)
  })
})

