import createClient, { type Client } from 'openapi-fetch'

import type { components, paths } from './generated/schema'

type Schema<K extends keyof components['schemas']> = components['schemas'][K]

export type ApiClientError = {
  status?: number
  code?: string
  message: string
  details?: unknown
}

export type ApiClientOptions = {
  baseUrl?: string
  fetch?: typeof fetch
  getAccessToken?: () => string | Promise<string | null> | null
}

export type StylistTgClient = {
  baseUrl: string
  openapi: Client<paths>
  request: <T>(path: string, init?: RequestInit) => Promise<T>
  buildUrl: (path: string) => string
}

export type AccountListItem = Schema<'AccountListItemRead'>
export type AccountRead = Schema<'AccountRead'>
export type AccountReadinessRisk = Schema<'AccountReadinessRiskRead'>
export type AccountReadinessRiskSummary = Schema<'AccountReadinessRiskSummaryRead'>
export type AccountDeletionPreview = Schema<'AccountDeletionPreviewRead'>
export type AccountDeletionRequestCreate = Schema<'AccountDeletionRequestCreate'>
export type AccountDeletionRequest = Schema<'AccountDeletionRequestRead'>
export type AccountExportRequest = Schema<'AccountExportRequestRead'>
export type ActionGate = Schema<'ActionGateRead'>
export type SensitiveAuditEventPage = Schema<'SensitiveAuditEventPageRead'>
export type AccountSafety = Schema<'AccountSafetyRead'>
export type AccountSafetySummary = Schema<'AccountSafetySummaryRead'>
export type AccountValidityCheck = Schema<'AccountValidityCheckRead'>
export type AccountOperationCooldown = Schema<'AccountOperationCooldownRead'>
export type AccountProxy = Schema<'AccountProxyRead'>
export type AccountProxySummary = Schema<'AccountProxySummaryRead'>
export type AccountRuntimeDiagnostics = Schema<'AccountRuntimeDiagnosticsRead'>
export type AccountBatchSafetyPreview = Schema<'AccountBatchSafetyPreviewRead'>
export type AccountSafetyOverride = Schema<'AccountSafetyOverrideRead'>
export type AccountOperationLogPage = Schema<'AccountOperationLogPageRead'>
export type AccountProxyInput = Schema<'AccountProxyUpsert'>
export type DashboardProfile = Schema<'DashboardProfileRead'>
export type DiagnosticsRead = Schema<'DiagnosticsRead'>
export type FrontendDiagnosticsSummary = Schema<'FrontendDiagnosticsSummaryRead'>
export type ExecutionPolicy = Schema<'ExecutionPolicyRead'>
export type ExecutionPolicyUpdate = Schema<'ExecutionPolicyUpdate'>
export type JobDetail = Schema<'JobDetailRead'>
export type JobStep = Schema<'JobStepListItemRead'>
export type JobSummary = Schema<'JobSummaryRead'>
export type LivePreflight = Schema<'LivePreflightRead'>
export type ProfilePreview = Schema<'ProfilePreviewRead'> | Schema<'AccountUpdatePreviewRead'>
export type RuntimeDiagnostics = Schema<'DiagnosticsRead'>
export type RuntimeRefresh = Schema<'RuntimeRefreshRead'>
export type StoryCapabilities = Schema<'StoryCapabilitiesRead'>
export type StoryDraftRead = Schema<'StoryDraftRead'>
export type StoryDraftCreate = Schema<'StoryDraftCreate'>
export type StoryDraftUpdate = Schema<'StoryDraftUpdate'>
export type AuthState = Schema<'AuthStateRead'>
export type AuthRuntimeMode = Schema<'AuthRuntimeModeRead'>
export type AuthRuntimeModeUpdate = Schema<'AuthRuntimeModeUpdate'>
export type AuthBatchPhoneInput = Schema<'AuthBatchPhoneInput'>
export type AuthBatchValidate = Schema<'AuthBatchValidateRead'>
export type AuthBatchCreate = Schema<'AuthBatchCreate'>
export type AuthBatchRead = Schema<'AuthBatchRead'>
export type AuthBatchSnapshot = Schema<'AuthBatchSnapshotRead'>
export type AuthBatchPoll = Schema<'AuthBatchPollRead'>
export type AuthBatchItem = Schema<'AuthBatchItemRead'>
export type AuthBatchEvent = Schema<'AuthBatchEventRead'>
export type WorkerDiagnostics = Schema<'WorkerDiagnosticsRead'>
export type QueueDescriptor = Schema<'QueueDescriptorRead'>
export type RetryPolicy = Schema<'RetryPolicyRead'>

export function resolveApiBaseUrl(value: string | undefined): string {
  if (!value) return ''
  return value.replace(/\/$/, '')
}

export function createApiClient(options: ApiClientOptions = {}): StylistTgClient {
  const baseUrl = resolveApiBaseUrl(options.baseUrl)
  const fetchWithAuth = createFetchWithAuth(options.fetch ?? globalThis.fetch.bind(globalThis), options.getAccessToken)
  return {
    baseUrl,
    openapi: createClient<paths>({
      baseUrl,
      fetch: fetchWithAuth,
    }),
    request: async <T>(path: string, init?: RequestInit) => {
      const response = await fetchWithAuth(buildUrl(baseUrl, path), init)
      return readResponse<T>(response)
    },
    buildUrl: (path: string) => buildUrl(baseUrl, path),
  }
}

export const createStylistTgClient = createApiClient

function createFetchWithAuth(baseFetch: typeof fetch, getAccessToken: ApiClientOptions['getAccessToken']): typeof fetch {
  return async (input, init) => {
    const headers = new Headers(init?.headers)
    const token = await getAccessToken?.()
    if (token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`)
    }
    if (typeof init?.body === 'string' && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    return baseFetch(input, { ...init, headers })
  }
}

function buildUrl(baseUrl: string, path: string): string {
  if (/^https?:\/\//i.test(path)) return path
  return `${baseUrl}${path.startsWith('/') ? path : `/${path}`}`
}

async function readResponse<T>(response: Response): Promise<T> {
  const isJson = response.headers.get('content-type')?.includes('application/json')
  const payload = isJson && response.status !== 204 && response.status !== 205 ? await response.json() : null
  if (!response.ok) {
    throw normalizeClientError(payload, response.status)
  }
  return payload as T
}

export function normalizeClientError(error: unknown, status?: number): ApiClientError {
  if (typeof error === 'object' && error !== null) {
    const record = error as Record<string, unknown>
    return {
      status,
      code: typeof record.error_code === 'string' ? record.error_code : undefined,
      message: typeof record.message === 'string' ? record.message : `request failed${status ? ` with status ${status}` : ''}`,
      details: record.details ?? error,
    }
  }
  return {
    status,
    message: error instanceof Error ? error.message : `request failed${status ? ` with status ${status}` : ''}`,
  }
}

async function unwrap<T>(promise: Promise<{ data?: T; error?: unknown; response: Response }>, label: string): Promise<T> {
  const { data, error, response } = await promise
  if (error) {
    const normalized = normalizeClientError(error, response.status)
    throw { ...normalized, message: normalized.message || `${label} request failed` }
  }
  if (!response.ok || data === undefined) {
    const normalized = normalizeClientError(null, response.status)
    throw { ...normalized, message: `${label} request failed with status ${response.status}` }
  }
  return data
}

function accountHeader(accountId: string): { 'X-Account-Id': string } {
  return { 'X-Account-Id': accountId }
}

export async function fetchHealth(client: StylistTgClient): Promise<{ status: string }> {
  return client.request<{ status: string }>('/health')
}

export async function fetchReady(client: StylistTgClient): Promise<DiagnosticsRead> {
  return client.request<DiagnosticsRead>('/ready')
}

export async function fetchRuntimeDiagnostics(client: StylistTgClient): Promise<RuntimeDiagnostics> {
  return unwrap(client.openapi.GET('/diagnostics/runtime'), 'diagnostics')
}

export async function fetchLivePreflight(client: StylistTgClient): Promise<LivePreflight> {
  return unwrap(client.openapi.GET('/diagnostics/live-preflight'), 'live preflight')
}

export async function fetchFrontendDiagnosticsSummary(client: StylistTgClient): Promise<FrontendDiagnosticsSummary> {
  return unwrap(client.openapi.GET('/diagnostics/frontend-summary'), 'frontend diagnostics')
}

export async function fetchAccounts(client: StylistTgClient): Promise<AccountListItem[]> {
  return unwrap(client.openapi.GET('/api/accounts'), 'accounts')
}

export async function fetchDashboard(client: StylistTgClient, accountId: string): Promise<DashboardProfile> {
  return unwrap(
    client.openapi.GET('/api/dashboard/profile', {
      params: { header: accountHeader(accountId) },
    }),
    'dashboard profile',
  )
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
    client.openapi.GET('/api/accounts/jobs', {
      params: { header: accountHeader(accountId), query: { limit } },
    }),
    'jobs',
  )
}

export async function fetchLatestJob(client: StylistTgClient, accountId: string): Promise<JobSummary> {
  return unwrap(
    client.openapi.GET('/api/accounts/jobs/latest', {
      params: { header: accountHeader(accountId) },
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

export async function refreshRuntime(client: StylistTgClient, accountId: string, init?: RequestInit): Promise<RuntimeRefresh> {
  return client.request<RuntimeRefresh>('/api/accounts/refresh-runtime', {
    ...init,
    method: 'POST',
    headers: { ...headersToObject(init?.headers), ...accountHeader(accountId) },
  })
}

export async function fetchAuthRuntimeMode(client: StylistTgClient): Promise<AuthRuntimeMode> {
  return unwrap(client.openapi.GET('/api/auth/runtime-mode'), 'auth runtime mode')
}

export async function updateAuthRuntimeMode(client: StylistTgClient, payload: AuthRuntimeModeUpdate): Promise<AuthRuntimeMode> {
  return unwrap(client.openapi.PATCH('/api/auth/runtime-mode', { body: payload }), 'update auth runtime mode')
}

export async function startOtp(client: StylistTgClient, phoneNumber: string): Promise<AuthState> {
  return unwrap(client.openapi.POST('/api/auth/otp/start', { body: { phone_number: phoneNumber } }), 'start otp')
}

export async function confirmOtp(client: StylistTgClient, accountId: string, code: string): Promise<AuthState> {
  return unwrap(client.openapi.POST('/api/auth/otp/confirm', { body: { account_id: accountId, code } }), 'confirm otp')
}

export async function submitPassword(client: StylistTgClient, accountId: string, password: string): Promise<AuthState> {
  return unwrap(client.openapi.POST('/api/auth/password', { body: { account_id: accountId, password } }), 'submit password')
}

export async function fetchAuthState(client: StylistTgClient, accountId: string): Promise<AuthState> {
  return unwrap(
    client.openapi.GET('/api/accounts/{account_id}/auth-state', {
      params: { path: { account_id: accountId } },
    }),
    'auth state',
  )
}

export async function validateAuthBatchPhones(
  client: StylistTgClient,
  items: AuthBatchPhoneInput[],
): Promise<AuthBatchValidate> {
  return unwrap(client.openapi.POST('/api/auth-batches/validate-phones', { body: { items } }), 'auth batch validation')
}

export async function createAuthBatch(client: StylistTgClient, payload: AuthBatchCreate): Promise<AuthBatchSnapshot> {
  return unwrap(client.openapi.POST('/api/auth-batches', { body: payload }), 'create auth batch')
}

export async function fetchAuthBatches(client: StylistTgClient): Promise<AuthBatchRead[]> {
  return unwrap(client.openapi.GET('/api/auth-batches'), 'auth batches')
}

export async function fetchAuthBatch(client: StylistTgClient, batchId: string): Promise<AuthBatchSnapshot> {
  return unwrap(
    client.openapi.GET('/api/auth-batches/{batch_id}', {
      params: { path: { batch_id: batchId } },
    }),
    'auth batch',
  )
}

export async function pollAuthBatch(client: StylistTgClient, batchId: string, sinceEventId?: string): Promise<AuthBatchPoll> {
  return unwrap(
    client.openapi.GET('/api/auth-batches/{batch_id}/poll', {
      params: { path: { batch_id: batchId }, query: sinceEventId ? { updated_since: sinceEventId } : undefined },
    }),
    'auth batch poll',
  )
}

export async function startAuthBatch(client: StylistTgClient, batchId: string): Promise<AuthBatchSnapshot> {
  return unwrap(
    client.openapi.POST('/api/auth-batches/{batch_id}/start', {
      params: { path: { batch_id: batchId } },
    }),
    'start auth batch',
  )
}

export async function pauseAuthBatch(client: StylistTgClient, batchId: string): Promise<AuthBatchSnapshot> {
  return unwrap(
    client.openapi.POST('/api/auth-batches/{batch_id}/pause', {
      params: { path: { batch_id: batchId } },
    }),
    'pause auth batch',
  )
}

export async function resumeAuthBatch(client: StylistTgClient, batchId: string): Promise<AuthBatchSnapshot> {
  return unwrap(
    client.openapi.POST('/api/auth-batches/{batch_id}/resume', {
      params: { path: { batch_id: batchId } },
    }),
    'resume auth batch',
  )
}

export async function cancelAuthBatch(client: StylistTgClient, batchId: string): Promise<AuthBatchSnapshot> {
  return unwrap(
    client.openapi.POST('/api/auth-batches/{batch_id}/cancel', {
      params: { path: { batch_id: batchId } },
    }),
    'cancel auth batch',
  )
}

export async function submitAuthBatchCode(
  client: StylistTgClient,
  batchId: string,
  itemId: string,
  code: string,
  idempotencyKey = newIdempotencyKey(),
): Promise<AuthBatchItem> {
  return unwrap(
    client.openapi.POST('/api/auth-batches/{batch_id}/items/{item_id}/submit-code', {
      params: { path: { batch_id: batchId, item_id: itemId } },
      body: { code, idempotency_key: idempotencyKey },
    }),
    'submit auth batch code',
  )
}

export async function submitAuthBatchPassword(
  client: StylistTgClient,
  batchId: string,
  itemId: string,
  password: string,
  idempotencyKey = newIdempotencyKey(),
): Promise<AuthBatchItem> {
  return unwrap(
    client.openapi.POST('/api/auth-batches/{batch_id}/items/{item_id}/submit-2fa', {
      params: { path: { batch_id: batchId, item_id: itemId } },
      body: { password, idempotency_key: idempotencyKey },
    }),
    'submit auth batch password',
  )
}

export async function retryAuthBatchItem(client: StylistTgClient, batchId: string, itemId: string): Promise<AuthBatchItem> {
  return unwrap(
    client.openapi.POST('/api/auth-batches/{batch_id}/items/{item_id}/retry', {
      params: { path: { batch_id: batchId, item_id: itemId } },
    }),
    'retry auth batch item',
  )
}

export async function requestNewAuthBatchCode(
  client: StylistTgClient,
  batchId: string,
  itemId: string,
): Promise<AuthBatchItem> {
  return unwrap(
    client.openapi.POST('/api/auth-batches/{batch_id}/items/{item_id}/request-new-code', {
      params: { path: { batch_id: batchId, item_id: itemId } },
    }),
    'request new auth batch code',
  )
}

export async function cancelAuthBatchItem(client: StylistTgClient, batchId: string, itemId: string): Promise<AuthBatchItem> {
  return unwrap(
    client.openapi.POST('/api/auth-batches/{batch_id}/items/{item_id}/cancel', {
      params: { path: { batch_id: batchId, item_id: itemId } },
    }),
    'cancel auth batch item',
  )
}

export async function fetchAuthBatchEvents(client: StylistTgClient, batchId: string, sinceEventId?: string): Promise<AuthBatchEvent[]> {
  void sinceEventId
  return unwrap(
    client.openapi.GET('/api/auth-batches/{batch_id}/events', {
      params: { path: { batch_id: batchId } },
    }),
    'auth batch events',
  )
}

export async function fetchAccountRuntimeDiagnostics(
  client: StylistTgClient,
  accountId: string,
): Promise<AccountRuntimeDiagnostics> {
  return unwrap(
    client.openapi.GET('/api/accounts/runtime-diagnostics', {
      params: { header: accountHeader(accountId) },
    }),
    'account runtime diagnostics',
  )
}

export async function fetchExecutionPolicy(client: StylistTgClient): Promise<ExecutionPolicy> {
  return unwrap(client.openapi.GET('/api/settings/execution-policy'), 'execution policy')
}

export async function updateExecutionPolicy(
  client: StylistTgClient,
  update: ExecutionPolicyUpdate,
): Promise<ExecutionPolicy> {
  return unwrap(
    client.openapi.PATCH('/api/settings/execution-policy', {
      body: update,
    }),
    'update execution policy',
  )
}

export async function fetchStoryDrafts(client: StylistTgClient, accountId: string): Promise<StoryDraftRead[]> {
  return unwrap(
    client.openapi.GET('/api/story-drafts', {
      params: { header: accountHeader(accountId) },
    }),
    'story drafts',
  )
}

export async function fetchStoryCapabilities(client: StylistTgClient, accountId: string): Promise<StoryCapabilities> {
  return unwrap(
    client.openapi.GET('/api/story-capabilities', {
      params: { header: accountHeader(accountId) },
    }),
    'story capabilities',
  )
}

export async function createStoryDraft(
  client: StylistTgClient,
  draft: StoryDraftCreate,
): Promise<StoryDraftRead> {
  return unwrap(client.openapi.POST('/api/story-drafts', { body: draft }), 'create story draft')
}

export async function updateStoryDraft(
  client: StylistTgClient,
  draftId: string,
  patch: StoryDraftUpdate,
): Promise<StoryDraftRead> {
  return unwrap(
    client.openapi.PATCH('/api/story-drafts/{draft_id}', {
      params: { path: { draft_id: draftId } },
      body: patch,
    }),
    'update story draft',
  )
}

export async function deleteStoryDraft(client: StylistTgClient, draftId: string): Promise<void> {
  await client.request<void>(`/api/story-drafts/${encodeURIComponent(draftId)}`, { method: 'DELETE' })
}

export async function deleteStoryPost(
  client: StylistTgClient,
  accountId: string,
  postId: string,
  init?: RequestInit,
): Promise<void> {
  await client.request<void>(`/api/story-posts/${encodeURIComponent(postId)}`, {
    ...init,
    method: 'DELETE',
    headers: { ...headersToObject(init?.headers), ...accountHeader(accountId) },
  })
}

export function buildAssetContentUrl(client: StylistTgClient, assetId: string): string {
  return client.buildUrl(`/api/assets/${encodeURIComponent(assetId)}/content`)
}

export async function uploadAsset(client: StylistTgClient, path: string, file: File): Promise<{ id: string }> {
  const body = new FormData()
  body.append('file', file)
  return client.request<{ id: string }>(path, { method: 'POST', body })
}

export async function previewProfileJob(
  client: StylistTgClient,
  payload: Schema<'ProfilePreviewRequest'>,
): Promise<ProfilePreview> {
  return unwrap(client.openapi.POST('/api/jobs/profile/preview', { body: payload }), 'profile preview')
}

export async function previewAccountUpdateJob(
  client: StylistTgClient,
  payload: Schema<'AccountUpdateCreate'>,
  init?: RequestInit,
): Promise<ProfilePreview> {
  return client.request<ProfilePreview>('/api/account-update/preview', {
    ...init,
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function createProfileJob(
  client: StylistTgClient,
  payload: Schema<'ProfileJobCreate'>,
): Promise<JobSummary> {
  return unwrap(client.openapi.POST('/api/jobs/profile', { body: payload }), 'profile job')
}

export async function createAccountUpdateJob(
  client: StylistTgClient,
  payload: Schema<'AccountUpdateCreate'>,
): Promise<JobSummary> {
  return client.request<JobSummary>('/api/account-update/jobs', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

function headersToObject(headers: RequestInit['headers']): Record<string, string> {
  if (!headers) return {}
  if (headers instanceof Headers) return Object.fromEntries(headers.entries())
  if (Array.isArray(headers)) return Object.fromEntries(headers)
  return Object.fromEntries(Object.entries(headers).filter((entry): entry is [string, string] => typeof entry[1] === 'string'))
}

function newIdempotencyKey(): string {
  return globalThis.crypto?.randomUUID?.() ?? `request-${Date.now()}-${Math.random().toString(16).slice(2)}`
}
