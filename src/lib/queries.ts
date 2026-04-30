import { queryOptions, type QueryClient } from '@tanstack/react-query'

import {
  type AccountListItem,
  fetchAccountSafety,
  fetchAccountSafetySummary,
  fetchAccountValidityChecks,
  previewAccountBatchSafety,
  fetchAccounts,
  fetchDashboard,
  fetchJob,
  fetchJobSteps,
  fetchLatestJob,
  fetchExecutionPolicy,
  fetchLatestJobs,
  fetchLivePreflight,
  fetchRuntimeDiagnostics,
  fetchStoryCapabilities,
  fetchStoryDrafts,
} from '@/lib/api'
import type { AccountSafetySummary } from '@/lib/accountSafety'
import { fetchAuthRuntimeMode, fetchAuthState } from '@/lib/auth'

export const queryKeys = {
  accounts: ['accounts'] as const,
  accountSafety: {
    root: ['accountSafety'] as const,
    summary: ['accountSafety', 'summary'] as const,
    account: (accountId: string) => ['accountSafety', accountId] as const,
    checks: (accountId: string) => ['accountSafety', accountId, 'checks'] as const,
    batchPreview: (operation: string, accountIds: string[]) =>
      ['accountSafety', 'batchPreview', operation, [...accountIds].sort().join(',')] as const,
    batchPreviewWithOverride: (operation: string, accountIds: string[], allowWarningOverrides: boolean) =>
      ['accountSafety', 'batchPreview', operation, [...accountIds].sort().join(','), allowWarningOverrides] as const,
  },
  authState: (accountId: string) => ['authState', accountId] as const,
  settings: {
    root: ['settings'] as const,
    bundle: ['settings', 'bundle'] as const,
    runtime: ['settings', 'runtime'] as const,
    preflight: ['settings', 'preflight'] as const,
    policy: ['settings', 'policy'] as const,
    authMode: ['settings', 'authMode'] as const,
  },
  dashboard: {
    root: ['dashboard'] as const,
    account: (accountId: string) => ['dashboard', accountId] as const,
    profile: (accountId: string) => ['dashboard', accountId, 'profile'] as const,
    jobs: (accountId: string) => ['dashboard', accountId, 'jobs'] as const,
    latestJob: (accountId: string) => ['dashboard', accountId, 'latestJob'] as const,
    storyDrafts: (accountId: string) => ['dashboard', accountId, 'storyDrafts'] as const,
    storyCapabilities: (accountId: string) => ['dashboard', accountId, 'storyCapabilities'] as const,
    bundle: (accountId: string) => ['dashboard', accountId, 'bundle'] as const,
  },
  job: {
    detail: (jobId: string) => ['job', jobId] as const,
    steps: (jobId: string) => ['job', jobId, 'steps'] as const,
    stateBundle: (jobId: string) => ['job', jobId, 'stateBundle'] as const,
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

export type JobStateBundle = {
  job: Awaited<ReturnType<typeof fetchJob>>
  steps: Awaited<ReturnType<typeof fetchJobSteps>>
  latestJob: Awaited<ReturnType<typeof fetchLatestJob>>
  jobs: Awaited<ReturnType<typeof fetchLatestJobs>>
}

export function settingsBundleQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.settings.bundle,
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

export function accountSafetySummaryQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.accountSafety.summary,
    queryFn: fetchAccountSafetySummary,
  })
}

export function accountSafetyQueryOptions(accountId: string) {
  return queryOptions({
    queryKey: queryKeys.accountSafety.account(accountId),
    queryFn: () => fetchAccountSafety(accountId),
  })
}

export function accountValidityChecksQueryOptions(accountId: string) {
  return queryOptions({
    queryKey: queryKeys.accountSafety.checks(accountId),
    queryFn: () => fetchAccountValidityChecks(accountId),
  })
}

export function accountBatchSafetyPreviewQueryOptions(
  accountIds: string[],
  operation: string,
  allowWarningOverrides = false,
) {
  return queryOptions({
    queryKey: queryKeys.accountSafety.batchPreviewWithOverride(operation, accountIds, allowWarningOverrides),
    queryFn: () => previewAccountBatchSafety(accountIds, operation, allowWarningOverrides),
    enabled: accountIds.length > 0,
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

export function dashboardProfileQueryOptions(accountId: string) {
  return queryOptions({
    queryKey: queryKeys.dashboard.profile(accountId),
    queryFn: () => fetchDashboard(accountId),
  })
}

export function latestJobsQueryOptions(accountId: string) {
  return queryOptions({
    queryKey: queryKeys.dashboard.jobs(accountId),
    queryFn: () => fetchLatestJobs(accountId),
  })
}

export function storyDraftsQueryOptions(accountId: string) {
  return queryOptions({
    queryKey: queryKeys.dashboard.storyDrafts(accountId),
    queryFn: () => fetchStoryDrafts(accountId),
  })
}

export function storyCapabilitiesQueryOptions(accountId: string) {
  return queryOptions({
    queryKey: queryKeys.dashboard.storyCapabilities(accountId),
    queryFn: () => fetchStoryCapabilities(accountId),
  })
}

export function latestJobQueryOptions(accountId: string) {
  return queryOptions({
    queryKey: queryKeys.dashboard.latestJob(accountId),
    queryFn: () => fetchLatestJob(accountId),
  })
}

export function jobDetailQueryOptions(jobId: string) {
  return queryOptions({
    queryKey: queryKeys.job.detail(jobId),
    queryFn: () => fetchJob(jobId),
    staleTime: 5_000,
  })
}

export function jobStepsQueryOptions(jobId: string) {
  return queryOptions({
    queryKey: queryKeys.job.steps(jobId),
    queryFn: () => fetchJobSteps(jobId),
    staleTime: 5_000,
  })
}

export function getCachedDashboardBundle(queryClient: QueryClient, accountId: string): DashboardBundle | undefined {
  return queryClient.getQueryData<DashboardBundle>(queryKeys.dashboard.bundle(accountId))
}

export async function fetchDashboardBundleQuery(
  queryClient: QueryClient,
  accountId: string,
  options?: {
    forceRefresh?: boolean
    queryFn?: () => Promise<DashboardBundle>
  },
): Promise<DashboardBundle> {
  const query = {
    ...dashboardBundleQueryOptions(accountId),
    ...(options?.queryFn ? { queryFn: options.queryFn } : {}),
    ...(options?.forceRefresh ? { staleTime: 0 } : {}),
  }
  return queryClient.fetchQuery(query)
}

export async function fetchJobStateQuery(
  queryClient: QueryClient,
  accountId: string,
  jobId: string,
  options?: {
    latestJob?: JobStateBundle['latestJob']
    jobs?: JobStateBundle['jobs']
    queryFn?: () => Promise<Pick<JobStateBundle, 'job' | 'steps'>>
  },
): Promise<JobStateBundle> {
  const [jobAndSteps, latestJob, jobs] = await Promise.all([
    options?.queryFn
      ? queryClient.fetchQuery({
          queryKey: queryKeys.job.stateBundle(jobId),
          queryFn: options.queryFn,
          staleTime: 0,
        })
      : Promise.all([
          queryClient.fetchQuery(jobDetailQueryOptions(jobId)),
          queryClient.fetchQuery(jobStepsQueryOptions(jobId)),
        ]).then(([job, steps]) => ({ job, steps })),
    options?.latestJob
      ? Promise.resolve(options.latestJob)
      : queryClient.fetchQuery(latestJobQueryOptions(accountId)),
    options?.jobs ? Promise.resolve(options.jobs) : queryClient.fetchQuery(latestJobsQueryOptions(accountId)),
  ])

  queryClient.setQueryData(queryKeys.job.detail(jobId), jobAndSteps.job)
  queryClient.setQueryData(queryKeys.job.steps(jobId), jobAndSteps.steps)
  return { job: jobAndSteps.job, steps: jobAndSteps.steps, latestJob, jobs }
}

export function removeAccountScopedQueries(queryClient: QueryClient, accountId: string): void {
  queryClient.removeQueries({ queryKey: queryKeys.dashboard.account(accountId) })
  queryClient.removeQueries({ queryKey: queryKeys.authState(accountId), exact: true })
}

export function invalidateAccountSafetyQueries(queryClient: QueryClient, accountId: string): void {
  void queryClient.invalidateQueries({ queryKey: queryKeys.accountSafety.summary })
  void queryClient.invalidateQueries({ queryKey: queryKeys.accountSafety.account(accountId), exact: true })
  void queryClient.invalidateQueries({ queryKey: queryKeys.accountSafety.checks(accountId), exact: true })
}

export function removeAccountSafetyFromCache(queryClient: QueryClient, accountId: string): void {
  queryClient.removeQueries({ queryKey: queryKeys.accountSafety.account(accountId), exact: true })
  queryClient.removeQueries({ queryKey: queryKeys.accountSafety.checks(accountId), exact: true })
  queryClient.setQueryData(queryKeys.accountSafety.summary, (current: AccountSafetySummary[] | undefined) =>
    (current ?? []).filter((safety) => safety.account_id !== accountId),
  )
}


export function removeAccountFromAccountsCache(queryClient: QueryClient, accountId: string): void {
  queryClient.setQueryData(queryKeys.accounts, (current: AccountListItem[] | undefined) =>
    (current ?? []).filter((account) => account.account_id !== accountId),
  )
}

export function updateSettingsPolicyInCache(queryClient: QueryClient, policy: SettingsBundle['policy']): void {
  queryClient.setQueryData(queryKeys.settings.bundle, (current: SettingsBundle | undefined) =>
    current ? { ...current, policy } : current,
  )
}

export function updateSettingsAuthModeInCache(queryClient: QueryClient, authMode: SettingsBundle['authMode']): void {
  queryClient.setQueryData(queryKeys.settings.bundle, (current: SettingsBundle | undefined) =>
    current ? { ...current, authMode } : current,
  )
}
