import { queryOptions } from '@tanstack/react-query'

import {
  fetchAccountAuditEvents,
  fetchAccountCooldowns,
  fetchAccountDeletionPreview,
  fetchAccountDeletionRequests,
  fetchAccountExportRequests,
  fetchAccountImportBatch,
  fetchAccountImportBatches,
  fetchAccountOperationLogs,
  fetchAccountProxy,
  fetchAccountRisk,
  fetchAccountRiskSummary,
  fetchAccountSafety,
  fetchAccountSafetyGate,
  fetchAccountSafetySummary,
  fetchAccountValidityChecks,
  fetchAccounts,
  fetchActionGate,
  fetchAuditEvents,
  fetchCurrentUser,
  fetchDashboard,
  fetchDisasterState,
  fetchExecutionPolicy,
  fetchFrontendDiagnosticsSummary,
  fetchGlobalOperationLogs,
  fetchJob,
  fetchJobPolicies,
  fetchJobSteps,
  fetchLatestJob,
  fetchLatestJobs,
  fetchLivePreflight,
  fetchProxySummary,
  fetchRuntimeDiagnostics,
  fetchStoryCapabilities,
  fetchStoryDrafts,
  fetchTdlibRuntimeStatus,
  fetchTelegramAuthSession,
  fetchTelegramAuthSessions,
  fetchWorkerDiagnostics,
  fetchWorkspaceSafetyPolicy,
  previewAccountBatchSafety,
  type SafetyGateIntent,
} from '@/lib/api'
import { fetchAuthRuntimeMode, fetchAuthState } from '@/modules/auth'

import { queryKeys } from './queryKeys'
import type { DashboardBundle, SettingsBundle } from './queryTypes'

export function currentUserQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.currentUser,
    queryFn: fetchCurrentUser,
    staleTime: 60_000,
  })
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

export function disasterStateQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.dashboard.disasterState,
    queryFn: fetchDisasterState,
    refetchInterval: 60_000,
  })
}

export function accountSafetySummaryQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.accountSafety.summary,
    queryFn: fetchAccountSafetySummary,
  })
}

export function accountRiskSummaryQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.accountRisk.summary,
    queryFn: fetchAccountRiskSummary,
  })
}

export function accountRiskQueryOptions(accountId: string) {
  return queryOptions({
    queryKey: queryKeys.accountRisk.account(accountId),
    queryFn: () => fetchAccountRisk(accountId),
  })
}

export function frontendDiagnosticsQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.settings.frontendDiagnostics,
    queryFn: fetchFrontendDiagnosticsSummary,
  })
}

export function workspaceSafetyPolicyQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.settings.safetyPolicy,
    queryFn: fetchWorkspaceSafetyPolicy,
  })
}

export function workerDiagnosticsQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.workers.diagnostics,
    queryFn: fetchWorkerDiagnostics,
  })
}

export function jobPoliciesQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.workers.jobPolicies,
    queryFn: fetchJobPolicies,
  })
}

export function tdlibRuntimeQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.tdlibRuntime,
    queryFn: fetchTdlibRuntimeStatus,
  })
}

export function telegramAuthSessionsQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.telegramAuth.sessions,
    queryFn: fetchTelegramAuthSessions,
  })
}

export function telegramAuthSessionQueryOptions(authSessionId: string) {
  return queryOptions({
    queryKey: queryKeys.telegramAuth.session(authSessionId),
    queryFn: () => fetchTelegramAuthSession(authSessionId),
  })
}

export function accountImportBatchesQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.accountImport.batches,
    queryFn: fetchAccountImportBatches,
  })
}

export function accountImportBatchQueryOptions(batchId: string) {
  return queryOptions({
    queryKey: queryKeys.accountImport.batch(batchId),
    queryFn: () => fetchAccountImportBatch(batchId),
  })
}

export function accountDeletionPreviewQueryOptions(accountId: string) {
  return queryOptions({
    queryKey: queryKeys.accountLifecycle.deletionPreview(accountId),
    queryFn: () => fetchAccountDeletionPreview(accountId),
  })
}

export function accountDeletionRequestsQueryOptions(accountId: string) {
  return queryOptions({
    queryKey: queryKeys.accountLifecycle.deletionRequests(accountId),
    queryFn: () => fetchAccountDeletionRequests(accountId),
  })
}

export function accountExportRequestsQueryOptions(accountId: string) {
  return queryOptions({
    queryKey: queryKeys.accountLifecycle.exportRequests(accountId),
    queryFn: () => fetchAccountExportRequests(accountId),
  })
}

export function accountAuditEventsQueryOptions(accountId: string, limit = 50) {
  return queryOptions({
    queryKey: [...queryKeys.audit.account(accountId), limit] as const,
    queryFn: () => fetchAccountAuditEvents(accountId, limit),
  })
}

export function auditEventsQueryOptions(limit = 100) {
  return queryOptions({
    queryKey: [...queryKeys.audit.global, limit] as const,
    queryFn: () => fetchAuditEvents(limit),
  })
}

export function accountCooldownsQueryOptions(accountId: string) {
  return queryOptions({
    queryKey: queryKeys.accountLifecycle.cooldowns(accountId),
    queryFn: () => fetchAccountCooldowns(accountId),
  })
}

export function actionGateQueryOptions(accountId: string, actionType: string) {
  return queryOptions({
    queryKey: queryKeys.accountRisk.actionGate(accountId, actionType),
    queryFn: () => fetchActionGate(accountId, actionType),
  })
}

export function accountSafetyQueryOptions(accountId: string) {
  return queryOptions({
    queryKey: queryKeys.accountSafety.account(accountId),
    queryFn: () => fetchAccountSafety(accountId),
  })
}

export function accountSafetyGateQueryOptions(accountId: string, intent: SafetyGateIntent) {
  return queryOptions({
    queryKey: queryKeys.accountSafety.gate(accountId, intent),
    queryFn: () => fetchAccountSafetyGate(accountId, intent),
    enabled: Boolean(accountId),
    staleTime: 30_000,
  })
}

export function proxySummaryQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.proxy.summary,
    queryFn: fetchProxySummary,
  })
}

export function accountProxyQueryOptions(accountId: string) {
  return queryOptions({
    queryKey: queryKeys.proxy.account(accountId),
    queryFn: () => fetchAccountProxy(accountId),
  })
}

export function accountOperationLogsQueryOptions(accountId: string, limit = 50) {
  return queryOptions({
    queryKey: [...queryKeys.operationLogs.account(accountId), limit] as const,
    queryFn: () => fetchAccountOperationLogs(accountId, limit),
  })
}

export function globalOperationLogsQueryOptions(limit = 100) {
  return queryOptions({
    queryKey: [...queryKeys.operationLogs.global, limit] as const,
    queryFn: () => fetchGlobalOperationLogs(limit),
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
