import { queryOptions } from '@tanstack/react-query'

import {
  fetchAccounts,
  fetchDashboard,
  fetchExecutionPolicy,
  fetchLatestJobs,
  fetchLivePreflight,
  fetchRuntimeDiagnostics,
  fetchStoryCapabilities,
  fetchStoryDrafts,
} from '@/lib/api'
import { fetchAuthRuntimeMode, fetchAuthState } from '@/lib/auth'

export const queryKeys = {
  accounts: ['accounts'] as const,
  authState: (accountId: string) => ['authState', accountId] as const,
  settings: {
    runtime: ['settings', 'runtime'] as const,
    preflight: ['settings', 'preflight'] as const,
    policy: ['settings', 'policy'] as const,
    authMode: ['settings', 'authMode'] as const,
    all: [['settings', 'runtime'], ['settings', 'preflight'], ['settings', 'policy'], ['settings', 'authMode']] as const,
  },
  dashboard: {
    root: ['dashboard'] as const,
    account: (accountId: string) => ['dashboard', accountId] as const,
    jobs: (accountId: string) => ['dashboard', accountId, 'jobs'] as const,
    storyDrafts: (accountId: string) => ['dashboard', accountId, 'storyDrafts'] as const,
    storyCapabilities: (accountId: string) => ['dashboard', accountId, 'storyCapabilities'] as const,
    bundle: (accountId: string) => ['dashboard', accountId, 'bundle'] as const,
  },
  job: {
    detail: (jobId: string) => ['job', jobId] as const,
    steps: (jobId: string) => ['job', jobId, 'steps'] as const,
  },
}

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

export function settingsBundleQueryOptions() {
  return queryOptions({
    queryKey: ['settings', 'bundle'] as const,
    queryFn: async (): Promise<SettingsBundle> => {
      const [runtime, preflight, policy, authMode] = await Promise.all([
        fetchRuntimeDiagnostics(),
        fetchLivePreflight(),
        fetchExecutionPolicy(),
        fetchAuthRuntimeMode(),
      ])
      return { runtime, preflight, policy, authMode }
    },
  })
}

export function accountsQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.accounts,
    queryFn: fetchAccounts,
  })
}

export function authStateQueryOptions(accountId: string) {
  return queryOptions({
    queryKey: queryKeys.authState(accountId),
    queryFn: () => fetchAuthState(accountId),
    staleTime: 10_000,
  })
}

export function dashboardBundleQueryOptions(accountId: string) {
  return queryOptions({
    queryKey: queryKeys.dashboard.bundle(accountId),
    queryFn: async (): Promise<DashboardBundle> => {
      const [dashboard, jobs, storyDrafts, storyCapabilities] = await Promise.all([
        fetchDashboard(accountId),
        fetchLatestJobs(accountId),
        fetchStoryDrafts(accountId),
        fetchStoryCapabilities(accountId),
      ])
      return { dashboard, jobs, storyDrafts, storyCapabilities }
    },
  })
}
