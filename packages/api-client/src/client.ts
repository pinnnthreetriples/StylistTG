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
export type Readiness = Schema<'ReadinessRead'>
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
export type TdlibRuntimeStatus = Schema<'TdlibRuntimeStatusRead'>
export type TelegramAuthSession = Schema<'TelegramAuthSessionRead'>
export type TelegramAuthSessionCreate = Schema<'TelegramAuthSessionCreate'>
export type TelegramAuthCodeSubmit = Schema<'TelegramAuthCodeSubmit'>
export type TelegramAuthPasswordSubmit = Schema<'TelegramAuthPasswordSubmit'>
export type AccountImportBatch = Schema<'AccountImportBatchRead'>
export type AccountImportBatchCreate = Schema<'AccountImportBatchCreate'>
export type AccountImportBatchValidate = Schema<'AccountImportBatchValidate'>
export type AccountImportBatchConfirm = Schema<'AccountImportBatchConfirm'>
export type CurrentUser = Schema<'CurrentUserRead'>
export type NeuroCampaign = Schema<'NeuroCampaignRead'>
export type NeuroCampaignCreate = Schema<'NeuroCampaignCreate'>
export type NeuroCampaignUpdate = Schema<'NeuroCampaignUpdate'>
export type NeuroCampaignPage = Schema<'NeuroCampaignPageRead'>
export type NeuroCampaignAccount = Schema<'NeuroCampaignAccountRead'>
export type NeuroCampaignAccountCreate = Schema<'NeuroCampaignAccountCreate'>
export type NeuroCampaignAccountPage = Schema<'NeuroCampaignAccountPageRead'>
export type NeuroTarget = Schema<'NeuroTargetRead'>
export type NeuroTargetCreate = Schema<'NeuroTargetCreate'>
export type NeuroTargetPage = Schema<'NeuroTargetPageRead'>
export type NeuroGeneratedComment = Schema<'NeuroGeneratedCommentRead'>
export type NeuroGeneratedCommentPage = Schema<'NeuroGeneratedCommentPageRead'>
export type NeuroGeneratedCommentUpdate = Schema<'NeuroGeneratedCommentUpdate'>
export type NeuroGeneratedCommentReject = Schema<'NeuroGeneratedCommentRejectRequest'>
export type NeuroEvent = Schema<'NeuroEventRead'>
export type NeuroEventPage = Schema<'NeuroEventPageRead'>

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
    const headers = new Headers(init?.headers ?? (input instanceof Request ? input.headers : undefined))
    const token = await getAccessToken?.()
    if (token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`)
    }
    const body = init?.body ?? (input instanceof Request ? input.body : undefined)
    if (shouldDefaultJsonContentType(body) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    return baseFetch(input, { ...init, headers })
  }
}

function shouldDefaultJsonContentType(body: unknown): boolean {
  if (body === undefined || body === null) return false
  if (typeof FormData !== 'undefined' && body instanceof FormData) return false
  if (typeof URLSearchParams !== 'undefined' && body instanceof URLSearchParams) return false
  if (typeof Blob !== 'undefined' && body instanceof Blob) return false
  if (body instanceof ArrayBuffer) return false
  if (ArrayBuffer.isView(body)) return false
  return true
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

export async function fetchReady(client: StylistTgClient): Promise<Readiness> {
  return client.request<Readiness>('/ready')
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

export async function fetchCurrentUser(client: StylistTgClient): Promise<CurrentUser> {
  return client.request<CurrentUser>('/api/me')
}

export async function fetchNeuroCampaigns(
  client: StylistTgClient,
  params?: { page?: number; limit?: number },
): Promise<NeuroCampaignPage> {
  return unwrap(
    client.openapi.GET('/api/neuro-commenting/campaigns', {
      params: { query: params },
    }),
    'neuro campaigns',
  )
}

export async function createNeuroCampaign(
  client: StylistTgClient,
  payload: NeuroCampaignCreate,
): Promise<NeuroCampaign> {
  return unwrap(client.openapi.POST('/api/neuro-commenting/campaigns', { body: payload }), 'create neuro campaign')
}

export async function fetchNeuroCampaign(client: StylistTgClient, campaignId: string): Promise<NeuroCampaign> {
  return unwrap(
    client.openapi.GET('/api/neuro-commenting/campaigns/{campaign_id}', {
      params: { path: { campaign_id: campaignId } },
    }),
    'neuro campaign',
  )
}

export async function updateNeuroCampaign(
  client: StylistTgClient,
  campaignId: string,
  payload: NeuroCampaignUpdate,
): Promise<NeuroCampaign> {
  return unwrap(
    client.openapi.PATCH('/api/neuro-commenting/campaigns/{campaign_id}', {
      params: { path: { campaign_id: campaignId } },
      body: payload,
    }),
    'update neuro campaign',
  )
}

export async function startNeuroCampaign(client: StylistTgClient, campaignId: string): Promise<NeuroCampaign> {
  return unwrap(
    client.openapi.POST('/api/neuro-commenting/campaigns/{campaign_id}/start', {
      params: { path: { campaign_id: campaignId } },
    }),
    'start neuro campaign',
  )
}

export async function pauseNeuroCampaign(client: StylistTgClient, campaignId: string): Promise<NeuroCampaign> {
  return unwrap(
    client.openapi.POST('/api/neuro-commenting/campaigns/{campaign_id}/pause', {
      params: { path: { campaign_id: campaignId } },
    }),
    'pause neuro campaign',
  )
}

export async function stopNeuroCampaign(client: StylistTgClient, campaignId: string): Promise<NeuroCampaign> {
  return unwrap(
    client.openapi.POST('/api/neuro-commenting/campaigns/{campaign_id}/stop', {
      params: { path: { campaign_id: campaignId } },
    }),
    'stop neuro campaign',
  )
}

export async function fetchNeuroCampaignAccounts(
  client: StylistTgClient,
  campaignId: string,
  params?: { page?: number; limit?: number },
): Promise<NeuroCampaignAccountPage> {
  return unwrap(
    client.openapi.GET('/api/neuro-commenting/campaigns/{campaign_id}/accounts', {
      params: { path: { campaign_id: campaignId }, query: params },
    }),
    'neuro campaign accounts',
  )
}

export async function addNeuroCampaignAccount(
  client: StylistTgClient,
  campaignId: string,
  payload: NeuroCampaignAccountCreate,
): Promise<NeuroCampaignAccount> {
  return unwrap(
    client.openapi.POST('/api/neuro-commenting/campaigns/{campaign_id}/accounts', {
      params: { path: { campaign_id: campaignId } },
      body: payload,
    }),
    'add neuro campaign account',
  )
}

export async function deleteNeuroCampaignAccount(
  client: StylistTgClient,
  campaignId: string,
  accountId: string,
): Promise<void> {
  await client.request<void>(
    `/api/neuro-commenting/campaigns/${encodeURIComponent(campaignId)}/accounts/${encodeURIComponent(accountId)}`,
    { method: 'DELETE' },
  )
}

export async function fetchNeuroCampaignTargets(
  client: StylistTgClient,
  campaignId: string,
  params?: { page?: number; limit?: number },
): Promise<NeuroTargetPage> {
  return unwrap(
    client.openapi.GET('/api/neuro-commenting/campaigns/{campaign_id}/targets', {
      params: { path: { campaign_id: campaignId }, query: params },
    }),
    'neuro campaign targets',
  )
}

export async function addNeuroCampaignTarget(
  client: StylistTgClient,
  campaignId: string,
  payload: NeuroTargetCreate,
): Promise<NeuroTarget> {
  return unwrap(
    client.openapi.POST('/api/neuro-commenting/campaigns/{campaign_id}/targets', {
      params: { path: { campaign_id: campaignId } },
      body: payload,
    }),
    'add neuro campaign target',
  )
}

export async function deleteNeuroCampaignTarget(
  client: StylistTgClient,
  campaignId: string,
  targetId: string,
): Promise<void> {
  await client.request<void>(
    `/api/neuro-commenting/campaigns/${encodeURIComponent(campaignId)}/targets/${encodeURIComponent(targetId)}`,
    { method: 'DELETE' },
  )
}

export async function fetchNeuroGeneratedComments(
  client: StylistTgClient,
  params?: { campaign_id?: string; page?: number; limit?: number },
): Promise<NeuroGeneratedCommentPage> {
  return unwrap(
    client.openapi.GET('/api/neuro-commenting/generated-comments', {
      params: { query: params },
    }),
    'neuro generated comments',
  )
}

export async function fetchNeuroGeneratedComment(
  client: StylistTgClient,
  commentId: string,
): Promise<NeuroGeneratedComment> {
  return unwrap(
    client.openapi.GET('/api/neuro-commenting/generated-comments/{comment_id}', {
      params: { path: { comment_id: commentId } },
    }),
    'neuro generated comment',
  )
}

export async function editNeuroGeneratedComment(
  client: StylistTgClient,
  commentId: string,
  payload: NeuroGeneratedCommentUpdate,
): Promise<NeuroGeneratedComment> {
  return unwrap(
    client.openapi.PATCH('/api/neuro-commenting/generated-comments/{comment_id}', {
      params: { path: { comment_id: commentId } },
      body: payload,
    }),
    'edit neuro generated comment',
  )
}

export async function approveNeuroGeneratedComment(
  client: StylistTgClient,
  commentId: string,
): Promise<NeuroGeneratedComment> {
  return unwrap(
    client.openapi.POST('/api/neuro-commenting/generated-comments/{comment_id}/approve', {
      params: { path: { comment_id: commentId } },
    }),
    'approve neuro generated comment',
  )
}

export async function rejectNeuroGeneratedComment(
  client: StylistTgClient,
  commentId: string,
  payload: NeuroGeneratedCommentReject,
): Promise<NeuroGeneratedComment> {
  return unwrap(
    client.openapi.POST('/api/neuro-commenting/generated-comments/{comment_id}/reject', {
      params: { path: { comment_id: commentId } },
      body: payload,
    }),
    'reject neuro generated comment',
  )
}

export async function fetchNeuroEvents(
  client: StylistTgClient,
  params?: { campaign_id?: string; page?: number; limit?: number },
): Promise<NeuroEventPage> {
  return unwrap(
    client.openapi.GET('/api/neuro-commenting/events', {
      params: { query: params },
    }),
    'neuro events',
  )
}

export async function fetchDashboard(client: StylistTgClient, accountId: string): Promise<DashboardProfile> {
  return unwrap(
    client.openapi.GET('/api/dashboard/profile/{account_id}', {
      params: { path: { account_id: accountId } },
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
    client.openapi.GET('/api/story-drafts/{account_id}', {
      params: { path: { account_id: accountId } },
    }),
    'story drafts',
  )
}

export async function fetchStoryCapabilities(client: StylistTgClient, accountId: string): Promise<StoryCapabilities> {
  return unwrap(
    client.openapi.GET('/api/story-capabilities/{account_id}', {
      params: { path: { account_id: accountId } },
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

export async function fetchTdlibRuntimeStatus(client: StylistTgClient): Promise<TdlibRuntimeStatus> {
  return unwrap(client.openapi.GET('/api/tdlib/runtime'), 'TDLib runtime')
}

export async function createTelegramAuthSession(
  client: StylistTgClient,
  payload: TelegramAuthSessionCreate,
): Promise<TelegramAuthSession> {
  return unwrap(client.openapi.POST('/api/accounts/auth-sessions', { body: payload }), 'create Telegram auth session')
}

export async function fetchTelegramAuthSessions(client: StylistTgClient): Promise<TelegramAuthSession[]> {
  return unwrap(client.openapi.GET('/api/accounts/auth-sessions'), 'Telegram auth sessions')
}

export async function fetchTelegramAuthSession(client: StylistTgClient, authSessionId: string): Promise<TelegramAuthSession> {
  return unwrap(
    client.openapi.GET('/api/accounts/auth-sessions/{auth_session_id}', {
      params: { path: { auth_session_id: authSessionId } },
    }),
    'Telegram auth session',
  )
}

export async function submitTelegramAuthCode(
  client: StylistTgClient,
  authSessionId: string,
  payload: TelegramAuthCodeSubmit,
): Promise<TelegramAuthSession> {
  return unwrap(
    client.openapi.POST('/api/accounts/auth-sessions/{auth_session_id}/code', {
      params: { path: { auth_session_id: authSessionId } },
      body: payload,
    }),
    'submit Telegram auth code',
  )
}

export async function submitTelegramAuthPassword(
  client: StylistTgClient,
  authSessionId: string,
  payload: TelegramAuthPasswordSubmit,
): Promise<TelegramAuthSession> {
  return unwrap(
    client.openapi.POST('/api/accounts/auth-sessions/{auth_session_id}/password', {
      params: { path: { auth_session_id: authSessionId } },
      body: payload,
    }),
    'submit Telegram auth password',
  )
}

export async function cancelTelegramAuthSession(client: StylistTgClient, authSessionId: string): Promise<TelegramAuthSession> {
  return unwrap(
    client.openapi.POST('/api/accounts/auth-sessions/{auth_session_id}/cancel', {
      params: { path: { auth_session_id: authSessionId } },
    }),
    'cancel Telegram auth session',
  )
}

export async function createReauthSession(
  client: StylistTgClient,
  accountId: string,
  payload: TelegramAuthSessionCreate,
): Promise<TelegramAuthSession> {
  return unwrap(
    client.openapi.POST('/api/accounts/{account_id}/reauth-sessions', {
      params: { path: { account_id: accountId } },
      body: payload,
    }),
    'create Telegram reauth session',
  )
}

export async function createAccountImportBatch(
  client: StylistTgClient,
  payload: AccountImportBatchCreate,
): Promise<AccountImportBatch> {
  return unwrap(client.openapi.POST('/api/account-import-batches', { body: payload }), 'create account import batch')
}

export async function fetchAccountImportBatches(client: StylistTgClient): Promise<AccountImportBatch[]> {
  return unwrap(client.openapi.GET('/api/account-import-batches'), 'account import batches')
}

export async function fetchAccountImportBatch(client: StylistTgClient, batchId: string): Promise<AccountImportBatch> {
  return unwrap(
    client.openapi.GET('/api/account-import-batches/{batch_id}', {
      params: { path: { batch_id: batchId } },
    }),
    'account import batch',
  )
}

export async function validateAccountImportBatch(
  client: StylistTgClient,
  batchId: string,
  payload: AccountImportBatchValidate,
): Promise<AccountImportBatch> {
  return unwrap(
    client.openapi.POST('/api/account-import-batches/{batch_id}/validate', {
      params: { path: { batch_id: batchId } },
      body: payload,
    }),
    'validate account import batch',
  )
}

export async function confirmAccountImportBatch(
  client: StylistTgClient,
  batchId: string,
  payload: AccountImportBatchConfirm,
): Promise<AccountImportBatch> {
  return unwrap(
    client.openapi.POST('/api/account-import-batches/{batch_id}/confirm', {
      params: { path: { batch_id: batchId } },
      body: payload,
    }),
    'confirm account import batch',
  )
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
