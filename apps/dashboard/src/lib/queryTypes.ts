import {
  fetchDashboard,
  fetchExecutionPolicy,
  fetchJob,
  fetchJobSteps,
  fetchLatestJob,
  fetchLatestJobs,
  fetchLivePreflight,
  fetchRuntimeDiagnostics,
  fetchStoryCapabilities,
  fetchStoryDrafts,
} from '@/lib/api'
import { fetchAuthRuntimeMode } from '@/modules/auth'

export type SettingsBundle = {
  runtime: Awaited<ReturnType<typeof fetchRuntimeDiagnostics>>
  preflight: Awaited<ReturnType<typeof fetchLivePreflight>>
  policy: Awaited<ReturnType<typeof fetchExecutionPolicy>>
  authMode: Awaited<ReturnType<typeof fetchAuthRuntimeMode>>
}

export type DashboardBundle = {
  dashboard: Awaited<ReturnType<typeof fetchDashboard>>
  jobs: Awaited<ReturnType<typeof fetchLatestJobs>>
  storyDrafts: Awaited<ReturnType<typeof fetchStoryDrafts>>
  storyCapabilities: Awaited<ReturnType<typeof fetchStoryCapabilities>>
}

export type JobStateBundle = {
  job: Awaited<ReturnType<typeof fetchJob>>
  steps: Awaited<ReturnType<typeof fetchJobSteps>>
  latestJob: Awaited<ReturnType<typeof fetchLatestJob>>
  jobs: Awaited<ReturnType<typeof fetchLatestJobs>>
}
