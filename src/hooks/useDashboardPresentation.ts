import { useMemo } from 'react'

import type { JobDetail, JobStep, JobSummary, ProfilePreview } from '@/lib/api'
import type { ApiError } from '@/lib/dashboard'
import { buildRuntimeBanner } from '@/lib/dashboard'
import {
  buildJobDisplayItems,
  buildJobProgressSummary,
  buildJobResultSummary,
  buildJobStepItems,
} from '@/lib/jobs'

export function useDashboardPresentation({
  apiError,
  currentJob,
  currentSteps,
  hiddenJobPanelKey,
  jobs,
  preview,
  submittedPreview,
  terminalJobStates,
}: {
  apiError: ApiError | null
  currentJob: JobDetail | null
  currentSteps: JobStep[]
  hiddenJobPanelKey: string | null
  jobs: JobSummary[]
  preview: ProfilePreview | null
  submittedPreview: ProfilePreview | null
  terminalJobStates: ReadonlySet<string>
}) {
  const runtimeBanner = useMemo(() => buildRuntimeBanner({ apiError }), [apiError])
  const latestJobPlan = useMemo(() => {
    if (!currentJob) return null
    const latest = jobs.find((job) => job.job_id === currentJob.job_id)
    if (!latest?.plan_summary.length) return null
    return {
      steps: latest.plan_summary.map((step_key) => ({ step_key })),
    }
  }, [currentJob, jobs])
  const jobPlan = submittedPreview ?? preview ?? latestJobPlan
  const jobStepItems = useMemo(
    () => buildJobStepItems(currentSteps, jobPlan, currentJob?.job_state),
    [currentJob?.job_state, currentSteps, jobPlan],
  )
  const jobResultSummary = useMemo(
    () => buildJobResultSummary(currentJob, currentSteps),
    [currentJob, currentSteps],
  )
  const jobProgressSummary = useMemo(() => buildJobProgressSummary(jobStepItems), [jobStepItems])
  const jobDisplayItems = useMemo(() => buildJobDisplayItems(jobStepItems), [jobStepItems])
  const activeJobKey = currentJob && !terminalJobStates.has(currentJob.job_state) ? currentJob.job_id : null
  const jobPanelKey = activeJobKey ?? preview?.execution_intent_hash ?? currentJob?.job_id ?? (jobStepItems.length > 0 ? 'steps' : null)
  const shouldShowJobPanel = Boolean(jobPanelKey && hiddenJobPanelKey !== jobPanelKey)

  return {
    jobDisplayItems,
    jobPanelKey,
    jobProgressSummary,
    jobResultSummary,
    runtimeBanner,
    shouldShowJobPanel,
  }
}
