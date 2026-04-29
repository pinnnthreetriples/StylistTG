import type { FormPayload, JobDetail, JobStep, JobSummary, StoryCapabilities } from '@/lib/api'
import {
  fetchJob,
  fetchJobSteps,
  fetchLatestJob,
  fetchLatestJobs,
  storyDraftReadToPayload,
} from '@/lib/api'
import {
  areDashboardFormStatesEqual,
  buildDashboardFormState,
  clearStoredDashboardFormDraft,
  persistStoredDashboardFormDraft,
  readStoredDashboardFormDraft,
  reconcileStoredDashboardFormDraft,
  type FormState,
} from '@/lib/dashboard'
import { persistDashboardCache } from '@/lib/dashboardCache'
import { areStoryDraftsEqual } from '@/lib/jobBanner'
import { dashboardBundleQueryOptions, type DashboardBundle } from '@/lib/queries'
import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useState } from 'react'

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
  pollingIntervalMs,
}: {
  accountId: string | null
  authPhase: string
  pollingIntervalMs: number
}) {
  type DashboardPayload = DashboardBundle['dashboard']
  const queryClient = useQueryClient()

  const [dashboard, setDashboard] = useState<DashboardPayload | null>(null)
  const [jobs, setJobs] = useState<JobSummary[]>([])
  const [currentJob, setCurrentJob] = useState<JobDetail | null>(null)
  const [currentSteps, setCurrentSteps] = useState<JobStep[]>([])
  const [storyCapabilities, setStoryCapabilities] = useState<StoryCapabilities | null>(null)
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
        const [jobPayload, stepsPayload, latestJobPayload, jobsPayload] = await Promise.all([
          fetchJob(jobId),
          fetchJobSteps(jobId),
          preloaded?.latestJob ? Promise.resolve(preloaded.latestJob) : fetchLatestJob(acctId),
          preloaded?.jobs ? Promise.resolve(preloaded.jobs) : fetchLatestJobs(acctId),
        ])
        setCurrentJob(jobPayload)
        setCurrentSteps(stepsPayload)
        setJobs(jobsPayload)
        setDashboard((prev) =>
          prev
            ? {
                ...prev,
                pipeline: {
                  ...prev.pipeline,
                  latest_job: latestJobPayload,
                  latest_job_id: latestJobPayload.job_id,
                  latest_job_state: latestJobPayload.job_state,
                  has_active_job: !TERMINAL_JOB_STATES.has(latestJobPayload.job_state),
                },
              }
            : prev,
        )
        return jobPayload
      } catch {
        return null
      }
    },
    [],
  )

  const loadDashboardState = useCallback(
    async (
      acctId: string,
      formRef: React.MutableRefObject<FormState>,
      formBaselineRef: React.MutableRefObject<FormState | null>,
      formInitializedRef: React.MutableRefObject<boolean>,
      setForm: (next: FormState) => void,
      options?: { resetForm?: boolean; quiet?: boolean },
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
          const reconciledStoredDraft = storedDraft
            ? reconcileStoredDashboardFormDraft(storedDraft, serverForm)
            : null
          const isDirty = formBaselineRef.current
            ? !areDashboardFormStatesEqual(formRef.current, formBaselineRef.current)
            : false
          const shouldResetForm = options?.resetForm ?? (!formInitializedRef.current || !isDirty)

          if (shouldResetForm) {
            const nextForm =
              !options?.resetForm && reconciledStoredDraft ? reconciledStoredDraft : serverForm
            formBaselineRef.current = serverForm
            formInitializedRef.current = true
            formRef.current = nextForm
            setForm(nextForm)

            if (reconciledStoredDraft && !options?.resetForm) {
              persistStoredDashboardFormDraft(window.localStorage, acctId, reconciledStoredDraft)
            } else {
              clearStoredDashboardFormDraft(window.localStorage, acctId)
            }
          } else if (!areStoryDraftsEqual(formRef.current.stories, serverForm.stories)) {
            const nextForm = { ...formRef.current, stories: serverForm.stories }
            formRef.current = nextForm
            setForm(nextForm)
            persistStoredDashboardFormDraft(window.localStorage, acctId, nextForm)
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

        const queryOptions = dashboardBundleQueryOptions(acctId)
        const cachedBundle = queryClient.getQueryData<DashboardBundle>(queryOptions.queryKey)
        if (cachedBundle) {
          await applyBundle(cachedBundle)
        }
        const freshBundle = await queryClient.fetchQuery(queryOptions)
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

  // ──────────────────────────────────────────────────────────────────────────
  // Job polling effect
  // ──────────────────────────────────────────────────────────────────────────

  useEffect(() => {
    if (
      !accountId ||
      authPhase !== 'dashboard' ||
      !dashboard?.pipeline.has_active_job ||
      !dashboard.pipeline.latest_job_id
    ) {
      return
    }

    let cancelled = false
    let timeoutId: number | null = null

    const poll = async () => {
      if (cancelled) return
      const job = await loadJobState(accountId, dashboard.pipeline.latest_job_id!)
      if (cancelled) return
      if (job && TERMINAL_JOB_STATES.has(job.job_state)) {
        setTerminalJobRefreshSeq((value) => value + 1)
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
    dashboard?.pipeline.has_active_job,
    dashboard?.pipeline.latest_job_id,
    loadJobState,
    pollingIntervalMs,
  ])

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
