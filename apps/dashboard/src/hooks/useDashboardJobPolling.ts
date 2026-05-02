import type { JobDetail } from '@/lib/api'
import { useEffect } from 'react'

type UseDashboardJobPollingParams = {
  accountId: string | null
  authPhase: string
  hasActiveJob: boolean | undefined
  latestJobId: string | null | undefined
  pollingIntervalMs: number
  terminalJobStates: ReadonlySet<string>
  loadJobState: (accountId: string, jobId: string) => Promise<JobDetail | null>
  onTerminalJob: () => void
}

export function useDashboardJobPolling({
  accountId,
  authPhase,
  hasActiveJob,
  latestJobId,
  pollingIntervalMs,
  terminalJobStates,
  loadJobState,
  onTerminalJob,
}: UseDashboardJobPollingParams) {
  useEffect(() => {
    if (!accountId || authPhase !== 'dashboard' || !hasActiveJob || !latestJobId) {
      return
    }

    let cancelled = false
    let timeoutId: number | null = null

    const poll = async () => {
      if (cancelled) return
      const job = await loadJobState(accountId, latestJobId)
      if (cancelled) return
      if (job && terminalJobStates.has(job.job_state)) {
        onTerminalJob()
        return
      }
      timeoutId = window.setTimeout(() => void poll(), pollingIntervalMs)
    }

    void poll()

    return () => {
      cancelled = true
      if (timeoutId !== null) window.clearTimeout(timeoutId)
    }
  }, [
    accountId,
    authPhase,
    hasActiveJob,
    latestJobId,
    loadJobState,
    onTerminalJob,
    pollingIntervalMs,
    terminalJobStates,
  ])
}
