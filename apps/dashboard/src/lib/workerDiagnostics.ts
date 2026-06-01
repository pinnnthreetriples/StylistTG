import type { WorkerDiagnostics } from '@/lib/api'

export function hasConfiguredRateLimits(workerDiagnostics?: WorkerDiagnostics): boolean {
  const rateLimits = workerDiagnostics?.rate_limits

  return Boolean(rateLimits && Object.keys(rateLimits).length > 0)
}

