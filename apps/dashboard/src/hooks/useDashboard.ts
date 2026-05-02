import type { FormPayload, JobDetail, JobStep, JobSummary, StoryCapabilities } from '@/lib/api'
import {
  storyDraftReadToPayload,
} from '@/lib/api'
import {
  buildDashboardFormState,
  clearStoredDashboardFormDraft,
  persistStoredDashboardFormDraft,
  readStoredDashboardFormDraft,
  type FormState,
} from '@/lib/dashboard'
import { persistDashboardCache } from '@/lib/dashboardCache'
import { reconcileDashboardFormState } from '@/lib/dashboardReconciliation'
import {
  fetchDashboardBundleQuery,
  fetchJobStateQuery,
  getCachedDashboardBundle,
  type DashboardBundle,
} from '@/lib/queries'
import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useState } from 'react'
import { useDashboardJobPolling } from '@/hooks/useDashboardJobPolling'

const TERMINAL_JOB_STATES = new Set([
  'completed',
  'partially_completed',
  'failed',
  'manual_intervention_needed',
  'canceled',
  'dedup_blocked',
])

/** Dashboard data + job polling logic, extracted from App.tsx. */
export function useDashboard({
  accountId,
  authPhase,
  initialBundle,
  pollingIntervalMs,
}: {
  accountId: string | null
  authPhase: string
  initialBundle?: DashboardBundle | null
  pollingIntervalMs: number
}) {
  type DashboardPayload = DashboardBundle['dashboard']
  const queryClient = useQueryClient()

  const [dashboard, setDashboard] = useState<DashboardPayload | null>(initialBundle?.dashboard ?? null)
  const [jobs, setJobs] = useState<JobSummary[]>(initialBundle?.jobs ?? [])
  const [currentJob, setCurrentJob] = useState<JobDetail | null>(null)
  const [currentSteps, setCurrentSteps] = useState<JobStep[]>([])
  const [storyCapabilities, setStoryCapabilities] = useState<StoryCapabilities | null>(
    initialBundle?.storyCapabilities ?? null,
  )
  const [isLoading, setIsLoading] = useState(false)
  const [isBootRefreshing, setIsBootRefreshing] = useState(false)
  const [terminalJobRefreshSeq, setTerminalJobRefreshSeq] = useState(0)

  // ──────────────────────────────────────────────────────────────────────────
  // Core loaders
  // ──────────────────────────────────────────────────────────────────────────

  const loadJobState = useCallback(
    async (
      acctId: string,
      jobId: string,
      preloaded?: { latestJob?: JobSummary | null; jobs?: JobSummary[] },
    ): Promise<JobDetail | null> => {
      try {
        const jobState = await fetchJobStateQuery(queryClient, acctId, jobId, {
          latestJob: preloaded?.latestJob ?? undefined,
          jobs: preloaded?.jobs,
        })
        setCurrentJob(jobState.job)
        setCurrentSteps(jobState.steps)
        setJobs(jobState.jobs)
        setDashboard((prev) =>
          prev
            ? {
                ...prev,
                pipeline: {
                  ...prev.pipeline,
                  latest_job: jobState.latestJob,
                  latest_job_id: jobState.latestJob.job_id,
                  latest_job_state: jobState.latestJob.job_state,
                  has_active_job: !TERMINAL_JOB_STATES.has(jobState.latestJob.job_state),
                },
              }
            : prev,
        )
        return jobState.job
      } catch {
        return null
      }
    },
    [queryClient],
  )

  const loadDashboardState = useCallback(
    async (
      acctId: string,
      formRef: React.MutableRefObject<FormState>,
      formBaselineRef: React.MutableRefObject<FormState | null>,
      formInitializedRef: React.MutableRefObject<boolean>,
      setForm: (next: FormState) => void,
      options?: { resetForm?: boolean; quiet?: boolean; forceRefresh?: boolean },
    ) => {
      if (!options?.quiet) setIsLoading(true)
      try {
        const applyBundle = async (bundle: DashboardBundle) => {
          const { dashboard: dashboardPayload, jobs: jobsPayload, storyDrafts: storyDraftsPayload, storyCapabilities: capsPayload } = bundle
          setDashboard(dashboardPayload)
          persistDashboardCache(window.localStorage, acctId, dashboardPayload)
          setJobs(jobsPayload)
          setStoryCapabilities(capsPayload)

          const serverForm: FormState = {
            ...buildDashboardFormState(dashboardPayload),
            stories: storyDraftsPayload.map(storyDraftReadToPayload),
          }
          const storedDraft = readStoredDashboardFormDraft(window.localStorage, acctId)
          const reconciliation = reconcileDashboardFormState({
            currentBaseline: formBaselineRef.current,
            currentForm: formRef.current,
            formInitialized: formInitializedRef.current,
            resetForm: options?.resetForm,
            serverForm,
            storedDraft,
          })

          if (reconciliation.nextForm) {
            if (reconciliation.nextBaseline) {
              formBaselineRef.current = reconciliation.nextBaseline
            }
            formInitializedRef.current = true
            formRef.current = reconciliation.nextForm
            setForm(reconciliation.nextForm)
          }
          if (reconciliation.draftToPersist) {
            persistStoredDashboardFormDraft(window.localStorage, acctId, reconciliation.draftToPersist)
          } else if (reconciliation.shouldClearDraft) {
            clearStoredDashboardFormDraft(window.localStorage, acctId)
          }

          if (dashboardPayload.pipeline.latest_job_id) {
            await loadJobState(acctId, dashboardPayload.pipeline.latest_job_id, {
              latestJob: dashboardPayload.pipeline.latest_job,
              jobs: jobsPayload,
            })
          } else {
            setCurrentJob(null)
            setCurrentSteps([])
          }
        }

        const cachedBundle = getCachedDashboardBundle(queryClient, acctId)
        if (cachedBundle) {
          await applyBundle(cachedBundle)
        }
        const freshBundle = await fetchDashboardBundleQuery(queryClient, acctId, {
          forceRefresh: options?.forceRefresh,
        })
        await applyBundle(freshBundle)
        return true
      } catch {
        return false
      } finally {
        if (!options?.quiet) setIsLoading(false)
      }
    },
    [loadJobState, queryClient],
  )

  const handleTerminalJob = useCallback(() => setTerminalJobRefreshSeq((value) => value + 1), [])

  useDashboardJobPolling({
    accountId,
    authPhase,
    hasActiveJob: dashboard?.pipeline.has_active_job,
    latestJobId: dashboard?.pipeline.latest_job_id,
    loadJobState,
    onTerminalJob: handleTerminalJob,
    pollingIntervalMs,
    terminalJobStates: TERMINAL_JOB_STATES,
  })

  // ──────────────────────────────────────────────────────────────────────────
  // Dashboard-cache persistence
  // ──────────────────────────────────────────────────────────────────────────

  useEffect(() => {
    if (accountId && dashboard?.account.account_id === accountId) {
      persistDashboardCache(window.localStorage, accountId, dashboard)
    }
  }, [accountId, dashboard])

  // ──────────────────────────────────────────────────────────────────────────

  function resetDashboard() {
    setDashboard(null)
    setJobs([])
    setCurrentJob(null)
    setCurrentSteps([])
    setIsLoading(false)
    setIsBootRefreshing(false)
  }

  function patchDashboardPipeline(job: JobSummary) {
    setDashboard((prev) =>
      prev
        ? {
            ...prev,
            pipeline: {
              ...prev.pipeline,
              latest_job: job,
              latest_job_id: job.job_id,
              latest_job_state: job.job_state,
              has_active_job: !TERMINAL_JOB_STATES.has(job.job_state),
            },
          }
        : prev,
    )
  }

  return {
    dashboard,
    setDashboard,
    jobs,
    setJobs,
    currentJob,
    setCurrentJob,
    currentSteps,
    storyCapabilities,
    terminalJobRefreshSeq,
    isLoading,
    isBootRefreshing,
    setIsBootRefreshing,
    loadJobState,
    loadDashboardState,
    resetDashboard,
    patchDashboardPipeline,
    terminalJobStates: TERMINAL_JOB_STATES,
  }
}

// Re-export FormPayload type so consumers don't need an extra import
export type { FormPayload }
