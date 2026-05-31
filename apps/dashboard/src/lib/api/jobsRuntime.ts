import {
  cancelTypedJob,
  deleteTypedJob,
  fetchTypedAccountRuntimeDiagnostics,
  fetchTypedCurrentUser,
  fetchTypedExecutionPolicy,
  fetchTypedFrontendDiagnosticsSummary,
  fetchTypedHealth,
  fetchTypedJob,
  fetchTypedJobSteps,
  fetchTypedLatestJob,
  fetchTypedLatestJobs,
  fetchTypedLivePreflight,
  fetchTypedReady,
  fetchTypedRuntimeDiagnostics,
  fetchTypedWorkspaceSafetyPolicy,
  refreshTypedRuntime,
  RUNTIME_REFRESH_TIMEOUT_MS,
  typedClient,
  updateTypedExecutionPolicy,
  updateTypedWorkspaceSafetyPolicy,
  type AccountRuntimeDiagnostics,
  type CurrentUser,
  type ExecutionPolicy,
  type ExecutionPolicyUpdate,
  type FrontendDiagnosticsSummary,
  type JobDetail,
  type JobStep,
  type JobSummary,
  type LivePreflight,
  type Readiness,
  type RuntimeDiagnostics,
  type RuntimeRefresh,
  type WorkspaceSafetyPolicy,
  type WorkspaceSafetyPolicyUpdate,
} from './core'

export function fetchLatestJobs(accountId: string, limit = 10): Promise<JobSummary[]> {
  return fetchTypedLatestJobs(typedClient, accountId, limit)
}

export function fetchLatestJob(accountId: string): Promise<JobSummary> {
  return fetchTypedLatestJob(typedClient, accountId)
}

export function fetchJob(jobId: string): Promise<JobDetail> {
  return fetchTypedJob(typedClient, jobId) as Promise<JobDetail>
}

export function fetchJobSteps(jobId: string): Promise<JobStep[]> {
  return fetchTypedJobSteps(typedClient, jobId) as Promise<JobStep[]>
}

export function cancelJob(jobId: string): Promise<JobSummary> {
  return cancelTypedJob(typedClient, jobId)
}

export function deleteJob(jobId: string): Promise<void> {
  return deleteTypedJob(typedClient, jobId)
}

export function refreshRuntime(accountId: string): Promise<RuntimeRefresh> {
  return refreshTypedRuntime(typedClient, accountId, { signal: AbortSignal.timeout(RUNTIME_REFRESH_TIMEOUT_MS) })
}

export function fetchRuntimeDiagnostics(): Promise<RuntimeDiagnostics> {
  return fetchTypedRuntimeDiagnostics(typedClient)
}

export function fetchHealth(): Promise<{ status: string }> {
  return fetchTypedHealth(typedClient)
}

export function fetchReady(): Promise<Readiness> {
  return fetchTypedReady(typedClient)
}

export function fetchCurrentUser(): Promise<CurrentUser> {
  return fetchTypedCurrentUser(typedClient)
}

export function fetchLivePreflight(): Promise<LivePreflight> {
  return fetchTypedLivePreflight(typedClient) as Promise<LivePreflight>
}

export function fetchFrontendDiagnosticsSummary(): Promise<FrontendDiagnosticsSummary> {
  return fetchTypedFrontendDiagnosticsSummary(typedClient)
}

export function fetchAccountRuntimeDiagnostics(accountId: string): Promise<AccountRuntimeDiagnostics> {
  return fetchTypedAccountRuntimeDiagnostics(typedClient, accountId) as Promise<AccountRuntimeDiagnostics>
}

export function fetchExecutionPolicy(): Promise<ExecutionPolicy> {
  return fetchTypedExecutionPolicy(typedClient) as Promise<ExecutionPolicy>
}

export function updateExecutionPolicy(update: number | ExecutionPolicyUpdate): Promise<ExecutionPolicy> {
  const body = typeof update === 'number' ? { profile_job_cooldown_seconds: update } : update
  return updateTypedExecutionPolicy(typedClient, body) as Promise<ExecutionPolicy>
}

export function fetchWorkspaceSafetyPolicy(): Promise<WorkspaceSafetyPolicy> {
  return fetchTypedWorkspaceSafetyPolicy(typedClient)
}

export function updateWorkspaceSafetyPolicy(update: WorkspaceSafetyPolicyUpdate): Promise<WorkspaceSafetyPolicy> {
  return updateTypedWorkspaceSafetyPolicy(typedClient, update)
}
