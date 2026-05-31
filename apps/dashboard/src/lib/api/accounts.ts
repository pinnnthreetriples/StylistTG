import {
  checkTypedAccountProxy,
  confirmTypedAccountImportBatch,
  cancelTypedTelegramAuthSession,
  createTypedAccountDeletionRequest,
  createTypedAccountExportRequest,
  createTypedAccountImportBatch,
  createTypedAccountSafetyOverride,
  createTypedReauthSession,
  createTypedTelegramAuthSession,
  deleteTypedAccount,
  deleteTypedAccountProxy,
  fetchTypedAccountAuditEvents,
  fetchTypedAccountCooldowns,
  fetchTypedAccountDeletionPreview,
  fetchTypedAccountDeletionRequests,
  fetchTypedAccountExportRequests,
  fetchTypedAccountImportBatch,
  fetchTypedAccountImportBatches,
  fetchTypedAccountOperationLogs,
  fetchTypedAccountProxy,
  fetchTypedAccountRisk,
  fetchTypedAccountRiskSummary,
  fetchTypedAccountSafety,
  fetchTypedAccountSafetyGate,
  fetchTypedAccountSafetySummary,
  fetchTypedAccountValidityChecks,
  fetchTypedAccounts,
  fetchTypedActionGate,
  fetchTypedAuditEvents,
  fetchTypedDashboard,
  fetchTypedDisasterState,
  fetchTypedGlobalOperationLogs,
  fetchTypedJobPolicies,
  fetchTypedProfileCompleteness,
  fetchTypedProxySummary,
  fetchTypedTdlibRuntimeStatus,
  fetchTypedTelegramAuthSession,
  fetchTypedTelegramAuthSessions,
  fetchTypedWorkerDiagnostics,
  fetchTypedWorkerQueues,
  previewTypedAccountBatchSafety,
  runTypedAccountValidityCheck,
  saveTypedAccountProxy,
  submitTypedTelegramAuthCode,
  submitTypedTelegramAuthPassword,
  typedClient,
  validateTypedAccountImportBatch,
  type AccountBatchSafetyPreview,
  type AccountDeletionPreview,
  type AccountDeletionRequest,
  type AccountDeletionRequestCreate,
  type AccountExportRequest,
  type AccountImportBatch,
  type AccountImportBatchConfirm,
  type AccountImportBatchCreate,
  type AccountImportBatchValidate,
  type AccountListItem,
  type AccountOperationCooldown,
  type AccountProxy,
  type AccountProxyInput,
  type AccountProxySummary,
  type AccountReadinessRisk,
  type AccountReadinessRiskSummary,
  type AccountSafety,
  type AccountSafetySummary,
  type AccountValidityCheck,
  type ActionGate,
  type DashboardResponse,
  type DisasterState,
  type OperationLogPage,
  type ProfileCompletenessReport,
  type QueueDescriptor,
  type RetryPolicy,
  type SafetyGateIntent,
  type SafetyGateVerdict,
  type SafetyOperation,
  type SafetyOverride,
  type SensitiveAuditEventPage,
  type TdlibRuntimeStatus,
  type TelegramAuthCodeSubmit,
  type TelegramAuthPasswordSubmit,
  type TelegramAuthSession,
  type TelegramAuthSessionCreate,
  type WorkerDiagnostics,
} from './core'

export function fetchDashboard(accountId: string): Promise<DashboardResponse> {
  return fetchTypedDashboard(typedClient, accountId)
}

export function fetchDisasterState(): Promise<DisasterState> {
  return fetchTypedDisasterState(typedClient)
}

export function fetchAccounts(): Promise<AccountListItem[]> {
  return fetchTypedAccounts(typedClient)
}

export function fetchAccountSafetySummary(): Promise<AccountSafetySummary[]> {
  return fetchTypedAccountSafetySummary(typedClient) as Promise<AccountSafetySummary[]>
}

export function fetchAccountSafety(accountId: string): Promise<AccountSafety> {
  return fetchTypedAccountSafety(typedClient, accountId) as Promise<AccountSafety>
}

export function fetchAccountSafetyGate(
  accountId: string,
  intent: SafetyGateIntent,
): Promise<SafetyGateVerdict> {
  return fetchTypedAccountSafetyGate(typedClient, accountId, intent)
}

export function fetchAccountRiskSummary(): Promise<AccountReadinessRiskSummary> {
  return fetchTypedAccountRiskSummary(typedClient)
}

export function fetchAccountRisk(accountId: string): Promise<AccountReadinessRisk> {
  return fetchTypedAccountRisk(typedClient, accountId)
}

export function fetchAccountDeletionPreview(accountId: string): Promise<AccountDeletionPreview> {
  return fetchTypedAccountDeletionPreview(typedClient, accountId)
}

export function createAccountDeletionRequest(
  accountId: string,
  payload: AccountDeletionRequestCreate,
): Promise<AccountDeletionRequest> {
  return createTypedAccountDeletionRequest(typedClient, accountId, payload)
}

export function fetchAccountDeletionRequests(accountId: string): Promise<AccountDeletionRequest[]> {
  return fetchTypedAccountDeletionRequests(typedClient, accountId)
}

export function createAccountExportRequest(accountId: string): Promise<AccountExportRequest> {
  return createTypedAccountExportRequest(typedClient, accountId)
}

export function fetchAccountExportRequests(accountId: string): Promise<AccountExportRequest[]> {
  return fetchTypedAccountExportRequests(typedClient, accountId)
}

export function fetchAccountAuditEvents(accountId: string, limit = 50): Promise<SensitiveAuditEventPage> {
  return fetchTypedAccountAuditEvents(typedClient, accountId, limit)
}

export function fetchAuditEvents(limit = 100): Promise<SensitiveAuditEventPage> {
  return fetchTypedAuditEvents(typedClient, limit)
}

export function fetchAccountCooldowns(accountId: string): Promise<AccountOperationCooldown[]> {
  return fetchTypedAccountCooldowns(typedClient, accountId)
}

export function fetchActionGate(accountId: string, actionType: string): Promise<ActionGate> {
  return fetchTypedActionGate(typedClient, accountId, actionType)
}

export function fetchWorkerDiagnostics(): Promise<WorkerDiagnostics> {
  return fetchTypedWorkerDiagnostics(typedClient)
}

export function fetchWorkerQueues(): Promise<QueueDescriptor[]> {
  return fetchTypedWorkerQueues(typedClient)
}

export function fetchJobPolicies(): Promise<Record<string, RetryPolicy>> {
  return fetchTypedJobPolicies(typedClient)
}

export function fetchTdlibRuntimeStatus(): Promise<TdlibRuntimeStatus> {
  return fetchTypedTdlibRuntimeStatus(typedClient)
}

export function createTelegramAuthSession(payload: TelegramAuthSessionCreate): Promise<TelegramAuthSession> {
  return createTypedTelegramAuthSession(typedClient, payload)
}

export function fetchTelegramAuthSessions(): Promise<TelegramAuthSession[]> {
  return fetchTypedTelegramAuthSessions(typedClient)
}

export function fetchTelegramAuthSession(authSessionId: string): Promise<TelegramAuthSession> {
  return fetchTypedTelegramAuthSession(typedClient, authSessionId)
}

export function submitTelegramAuthCode(
  authSessionId: string,
  payload: TelegramAuthCodeSubmit,
): Promise<TelegramAuthSession> {
  return submitTypedTelegramAuthCode(typedClient, authSessionId, payload)
}

export function submitTelegramAuthPassword(
  authSessionId: string,
  payload: TelegramAuthPasswordSubmit,
): Promise<TelegramAuthSession> {
  return submitTypedTelegramAuthPassword(typedClient, authSessionId, payload)
}

export function cancelTelegramAuthSession(authSessionId: string): Promise<TelegramAuthSession> {
  return cancelTypedTelegramAuthSession(typedClient, authSessionId)
}

export function createReauthSession(
  accountId: string,
  payload: TelegramAuthSessionCreate,
): Promise<TelegramAuthSession> {
  return createTypedReauthSession(typedClient, accountId, payload)
}

export function createAccountImportBatch(payload: AccountImportBatchCreate): Promise<AccountImportBatch> {
  return createTypedAccountImportBatch(typedClient, payload)
}

export function fetchAccountImportBatches(): Promise<AccountImportBatch[]> {
  return fetchTypedAccountImportBatches(typedClient)
}

export function fetchAccountImportBatch(batchId: string): Promise<AccountImportBatch> {
  return fetchTypedAccountImportBatch(typedClient, batchId)
}

export function validateAccountImportBatch(
  batchId: string,
  payload: AccountImportBatchValidate,
): Promise<AccountImportBatch> {
  return validateTypedAccountImportBatch(typedClient, batchId, payload)
}

export function confirmAccountImportBatch(
  batchId: string,
  payload: AccountImportBatchConfirm,
): Promise<AccountImportBatch> {
  return confirmTypedAccountImportBatch(typedClient, batchId, payload)
}

export function fetchProxySummary(): Promise<AccountProxySummary[]> {
  return fetchTypedProxySummary(typedClient) as Promise<AccountProxySummary[]>
}

export function fetchAccountProxy(accountId: string): Promise<AccountProxy | null> {
  return fetchTypedAccountProxy(typedClient, accountId) as Promise<AccountProxy | null>
}

export function fetchProfileCompleteness(accountId: string): Promise<ProfileCompletenessReport> {
  return fetchTypedProfileCompleteness(typedClient, accountId)
}

export function saveAccountProxy(accountId: string, payload: AccountProxyInput): Promise<AccountProxy> {
  return saveTypedAccountProxy(typedClient, accountId, payload) as Promise<AccountProxy>
}

export function deleteAccountProxy(accountId: string): Promise<void> {
  return deleteTypedAccountProxy(typedClient, accountId)
}

export function checkAccountProxy(accountId: string): Promise<AccountProxy> {
  return checkTypedAccountProxy(typedClient, accountId) as Promise<AccountProxy>
}

export function fetchAccountOperationLogs(accountId: string, limit = 50): Promise<OperationLogPage> {
  return fetchTypedAccountOperationLogs(typedClient, accountId, limit) as Promise<OperationLogPage>
}

export function fetchGlobalOperationLogs(limit = 100): Promise<OperationLogPage> {
  return fetchTypedGlobalOperationLogs(typedClient, limit) as Promise<OperationLogPage>
}

export function previewAccountBatchSafety(
  accountIds: string[],
  operation: SafetyOperation | string,
  allowWarningOverrides = false,
): Promise<AccountBatchSafetyPreview> {
  return previewTypedAccountBatchSafety(typedClient, accountIds, operation, allowWarningOverrides) as Promise<AccountBatchSafetyPreview>
}

export function runAccountValidityCheck(accountId: string, mode = 'db_snapshot'): Promise<AccountValidityCheck> {
  return runTypedAccountValidityCheck(typedClient, accountId, mode) as Promise<AccountValidityCheck>
}

export function fetchAccountValidityChecks(accountId: string): Promise<AccountValidityCheck[]> {
  return fetchTypedAccountValidityChecks(typedClient, accountId) as Promise<AccountValidityCheck[]>
}

export function createAccountSafetyOverride(
  accountId: string,
  payload: { operation: SafetyOperation | string; reason: string; requested_blockers: string[] },
): Promise<SafetyOverride> {
  return createTypedAccountSafetyOverride(typedClient, accountId, payload)
}

export function deleteAccount(accountId: string): Promise<void> {
  return deleteTypedAccount(typedClient, accountId)
}
