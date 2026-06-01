import { unwrap } from './core'
import type {
  AccountBatchSafetyPreview,
  AccountDeletionPreview,
  AccountDeletionRequest,
  AccountDeletionRequestCreate,
  AccountExportRequest,
  AccountListItem,
  AccountOperationCooldown,
  AccountOperationLogPage,
  AccountProxy,
  AccountProxyInput,
  AccountProxySummary,
  AccountReadinessRisk,
  AccountReadinessRiskSummary,
  AccountSafety,
  AccountSafetyOverride,
  AccountSafetySummary,
  AccountValidityCheck,
  ActionGate,
  CurrentUser,
  DashboardProfile,
  DisasterState,
  JobDetail,
  JobStep,
  JobSummary,
  ProfileCompletenessReport,
  QueueDescriptor,
  RetryPolicy,
  SafetyGateIntent,
  SafetyGateVerdict,
  SensitiveAuditEventPage,
  StylistTgClient,
  WorkerDiagnostics,
} from './types'
export async function fetchAccounts(client: StylistTgClient): Promise<AccountListItem[]> {
  return unwrap(client.openapi.GET('/api/accounts'), 'accounts')
}

export async function fetchCurrentUser(client: StylistTgClient): Promise<CurrentUser> {
  return client.request<CurrentUser>('/api/me')
}
export async function fetchDashboard(client: StylistTgClient, accountId: string): Promise<DashboardProfile> {
  return unwrap(
    client.openapi.GET('/api/dashboard/profile/{account_id}', {
      params: { path: { account_id: accountId } },
    }),
    'dashboard profile',
  )
}

export async function fetchDisasterState(client: StylistTgClient): Promise<DisasterState> {
  return unwrap(client.openapi.GET('/api/dashboard/disaster-state'), 'dashboard disaster state')
}

export async function fetchAccountSafetySummary(client: StylistTgClient): Promise<AccountSafetySummary[]> {
  return unwrap(client.openapi.GET('/api/accounts/safety-summary'), 'account safety summary')
}

export async function fetchAccountSafety(client: StylistTgClient, accountId: string): Promise<AccountSafety> {
  return unwrap(
    client.openapi.GET('/api/accounts/{account_id}/safety', {
      params: { path: { account_id: accountId } },
    }),
    'account safety',
  )
}

export async function fetchAccountRiskSummary(client: StylistTgClient): Promise<AccountReadinessRiskSummary> {
  return unwrap(client.openapi.GET('/api/accounts/risk-summary'), 'account risk summary')
}

export async function fetchAccountRisk(client: StylistTgClient, accountId: string): Promise<AccountReadinessRisk> {
  return unwrap(
    client.openapi.GET('/api/accounts/{account_id}/risk', {
      params: { path: { account_id: accountId } },
    }),
    'account risk',
  )
}

export async function fetchAccountDeletionPreview(client: StylistTgClient, accountId: string): Promise<AccountDeletionPreview> {
  return unwrap(
    client.openapi.GET('/api/accounts/{account_id}/deletion-preview', {
      params: { path: { account_id: accountId } },
    }),
    'account deletion preview',
  )
}

export async function createAccountDeletionRequest(
  client: StylistTgClient,
  accountId: string,
  payload: AccountDeletionRequestCreate,
): Promise<AccountDeletionRequest> {
  return unwrap(
    client.openapi.POST('/api/accounts/{account_id}/deletion-requests', {
      params: { path: { account_id: accountId } },
      body: payload,
    }),
    'account deletion request',
  )
}

export async function fetchAccountDeletionRequests(client: StylistTgClient, accountId: string): Promise<AccountDeletionRequest[]> {
  return unwrap(
    client.openapi.GET('/api/accounts/{account_id}/deletion-requests', {
      params: { path: { account_id: accountId } },
    }),
    'account deletion requests',
  )
}

export async function createAccountExportRequest(client: StylistTgClient, accountId: string): Promise<AccountExportRequest> {
  return unwrap(
    client.openapi.POST('/api/accounts/{account_id}/export-requests', {
      params: { path: { account_id: accountId } },
    }),
    'account export request',
  )
}

export async function fetchAccountExportRequests(client: StylistTgClient, accountId: string): Promise<AccountExportRequest[]> {
  return unwrap(
    client.openapi.GET('/api/accounts/{account_id}/export-requests', {
      params: { path: { account_id: accountId } },
    }),
    'account export requests',
  )
}

export async function fetchAccountAuditEvents(
  client: StylistTgClient,
  accountId: string,
  limit = 50,
): Promise<SensitiveAuditEventPage> {
  return unwrap(
    client.openapi.GET('/api/accounts/{account_id}/audit-events', {
      params: { path: { account_id: accountId }, query: { limit } },
    }),
    'account audit events',
  )
}

export async function fetchAuditEvents(client: StylistTgClient, limit = 100): Promise<SensitiveAuditEventPage> {
  return unwrap(
    client.openapi.GET('/api/audit/events', {
      params: { query: { limit } },
    }),
    'audit events',
  )
}

export async function fetchAccountCooldowns(client: StylistTgClient, accountId: string): Promise<AccountOperationCooldown[]> {
  return unwrap(
    client.openapi.GET('/api/accounts/{account_id}/cooldowns', {
      params: { path: { account_id: accountId } },
    }),
    'account cooldowns',
  )
}

export async function fetchActionGate(client: StylistTgClient, accountId: string, actionType: string): Promise<ActionGate> {
  return unwrap(
    client.openapi.GET('/api/accounts/{account_id}/action-gate', {
      params: { path: { account_id: accountId }, query: { action_type: actionType } },
    }),
    'account action gate',
  )
}

export async function fetchAccountSafetyGate(
  client: StylistTgClient,
  accountId: string,
  intent: SafetyGateIntent,
): Promise<SafetyGateVerdict> {
  return unwrap(
    client.openapi.GET('/api/accounts/{account_id}/safety-gate', {
      params: { path: { account_id: accountId }, query: { intent } },
    }),
    'account safety gate',
  )
}

export async function fetchWorkerDiagnostics(client: StylistTgClient): Promise<WorkerDiagnostics> {
  return unwrap(client.openapi.GET('/api/workers/diagnostics'), 'worker diagnostics')
}

export async function fetchWorkerQueues(client: StylistTgClient): Promise<QueueDescriptor[]> {
  return unwrap(client.openapi.GET('/api/workers/queues'), 'worker queues')
}

export async function fetchJobPolicies(client: StylistTgClient): Promise<Record<string, RetryPolicy>> {
  return unwrap(client.openapi.GET('/api/jobs/policies'), 'job policies')
}

export async function fetchProxySummary(client: StylistTgClient): Promise<AccountProxySummary[]> {
  return unwrap(client.openapi.GET('/api/accounts/proxy-summary'), 'proxy summary')
}

export async function fetchAccountProxy(client: StylistTgClient, accountId: string): Promise<AccountProxy | null> {
  return unwrap(
    client.openapi.GET('/api/accounts/{account_id}/proxy', {
      params: { path: { account_id: accountId } },
    }),
    'account proxy',
  )
}

export async function fetchProfileCompleteness(
  client: StylistTgClient,
  accountId: string,
): Promise<ProfileCompletenessReport> {
  return unwrap(
    client.openapi.GET('/api/accounts/{account_id}/profile-completeness', {
      params: { path: { account_id: accountId } },
    }),
    'profile completeness',
  )
}

export async function saveAccountProxy(
  client: StylistTgClient,
  accountId: string,
  payload: AccountProxyInput,
): Promise<AccountProxy> {
  return unwrap(
    client.openapi.PUT('/api/accounts/{account_id}/proxy', {
      params: { path: { account_id: accountId } },
      body: payload,
    }),
    'save account proxy',
  )
}

export async function deleteAccountProxy(client: StylistTgClient, accountId: string): Promise<void> {
  await client.request<void>(`/api/accounts/${encodeURIComponent(accountId)}/proxy`, { method: 'DELETE' })
}

export async function checkAccountProxy(client: StylistTgClient, accountId: string): Promise<AccountProxy> {
  return unwrap(
    client.openapi.POST('/api/accounts/{account_id}/proxy/check', {
      params: { path: { account_id: accountId } },
    }),
    'check account proxy',
  )
}

export async function fetchAccountOperationLogs(
  client: StylistTgClient,
  accountId: string,
  limit = 50,
): Promise<AccountOperationLogPage> {
  return unwrap(
    client.openapi.GET('/api/accounts/{account_id}/operation-logs', {
      params: { path: { account_id: accountId }, query: { limit } },
    }),
    'account operation logs',
  )
}

export async function fetchGlobalOperationLogs(client: StylistTgClient, limit = 100): Promise<AccountOperationLogPage> {
  return unwrap(
    client.openapi.GET('/api/operation-logs', {
      params: { query: { limit } },
    }),
    'operation logs',
  )
}

export async function previewAccountBatchSafety(
  client: StylistTgClient,
  accountIds: string[],
  operation: string,
  allowWarningOverrides = false,
): Promise<AccountBatchSafetyPreview> {
  return unwrap(
    client.openapi.POST('/api/accounts/safety-batch-preview', {
      body: {
        account_ids: accountIds,
        operation,
        allow_warning_overrides: allowWarningOverrides,
      },
    }),
    'account batch safety preview',
  )
}

export async function runAccountValidityCheck(
  client: StylistTgClient,
  accountId: string,
  mode = 'db_snapshot',
): Promise<AccountValidityCheck> {
  return client.request<AccountValidityCheck>(`/api/accounts/${encodeURIComponent(accountId)}/validity-check`, {
    method: 'POST',
    body: JSON.stringify({ mode }),
  })
}

export async function fetchAccountValidityChecks(
  client: StylistTgClient,
  accountId: string,
): Promise<AccountValidityCheck[]> {
  return unwrap(
    client.openapi.GET('/api/accounts/{account_id}/validity-checks', {
      params: { path: { account_id: accountId } },
    }),
    'account validity checks',
  )
}

export async function createAccountSafetyOverride(
  client: StylistTgClient,
  accountId: string,
  payload: { operation: string; reason: string; requested_blockers: string[] },
): Promise<AccountSafetyOverride> {
  return unwrap(
    client.openapi.POST('/api/accounts/{account_id}/safety-overrides', {
      params: { path: { account_id: accountId } },
      body: payload,
    }),
    'account safety override',
  )
}

export async function deleteAccount(client: StylistTgClient, accountId: string): Promise<void> {
  await client.request<void>(`/api/accounts/${encodeURIComponent(accountId)}`, { method: 'DELETE' })
}

export async function fetchLatestJobs(
  client: StylistTgClient,
  accountId: string,
  limit = 10,
): Promise<JobSummary[]> {
  return unwrap(
    client.openapi.GET('/api/accounts/{account_id}/jobs', {
      params: { path: { account_id: accountId }, query: { limit } },
    }),
    'jobs',
  )
}

export async function fetchLatestJob(client: StylistTgClient, accountId: string): Promise<JobSummary> {
  return unwrap(
    client.openapi.GET('/api/accounts/{account_id}/jobs/latest', {
      params: { path: { account_id: accountId } },
    }),
    'latest job',
  )
}

export async function fetchJob(client: StylistTgClient, jobId: string): Promise<JobDetail> {
  return unwrap(
    client.openapi.GET('/api/jobs/{job_id}', {
      params: { path: { job_id: jobId } },
    }),
    'job',
  )
}

export async function fetchJobSteps(client: StylistTgClient, jobId: string): Promise<JobStep[]> {
  return unwrap(
    client.openapi.GET('/api/jobs/{job_id}/steps', {
      params: { path: { job_id: jobId } },
    }),
    'job steps',
  )
}

export async function cancelJob(client: StylistTgClient, jobId: string): Promise<JobSummary> {
  return unwrap(
    client.openapi.POST('/api/jobs/{job_id}/cancel', {
      params: { path: { job_id: jobId } },
    }),
    'cancel job',
  )
}

export async function deleteJob(client: StylistTgClient, jobId: string): Promise<void> {
  await client.request<void>(`/api/jobs/${encodeURIComponent(jobId)}`, { method: 'DELETE' })
}
