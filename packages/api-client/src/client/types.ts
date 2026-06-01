import type { Client } from 'openapi-fetch'

import type { components, paths } from '../generated/schema'

export type Schema<K extends keyof components['schemas']> = components['schemas'][K]

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
export type SafetyGateVerdict = Schema<'SafetyGateVerdict'>
export type SafetyGateIntent = SafetyGateVerdict['intent']
export type AccountValidityCheck = Schema<'AccountValidityCheckRead'>
export type AccountOperationCooldown = Schema<'AccountOperationCooldownRead'>
export type AccountProxy = Schema<'AccountProxyRead'>
export type AccountProxySummary = Schema<'AccountProxySummaryRead'>
export type AccountRuntimeDiagnostics = Schema<'AccountRuntimeDiagnosticsRead'>
export type AccountBatchSafetyPreview = Schema<'AccountBatchSafetyPreviewRead'>
export type AccountSafetyOverride = Schema<'AccountSafetyOverrideRead'>
export type AccountOperationLogPage = Schema<'AccountOperationLogPageRead'>
export type AccountProxyInput = Schema<'AccountProxyUpsert'>
export type ProfileCompletenessReport = Schema<'ProfileCompletenessReport'>
export type DashboardProfile = Schema<'DashboardProfileRead'>
export type DisasterState = Schema<'DisasterState'>
export type DiagnosticsRead = Schema<'DiagnosticsRead'>
export type Readiness = Schema<'ReadinessRead'>
export type FrontendDiagnosticsSummary = Schema<'FrontendDiagnosticsSummaryRead'>
export type ExecutionPolicy = Schema<'ExecutionPolicyRead'>
export type ExecutionPolicyUpdate = Schema<'ExecutionPolicyUpdate'>
export type WorkspaceSafetyMode = 'conservative' | 'balanced' | 'aggressive'
export type WorkspaceSafetyPolicy = Schema<'WorkspaceSafetyPolicyRead'>
export type WorkspaceSafetyPolicyUpdate = Schema<'WorkspaceSafetyPolicyUpdate'>
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
export type NeuroAcceptedJob = Schema<'NeuroAcceptedJobRead'>
export type NeuroAttempt = Schema<'NeuroAttemptRead'>
export type NeuroAttemptPage = Schema<'NeuroAttemptPageRead'>
export type NeuroGenerateObservedPostRequest = Schema<'NeuroGenerateObservedPostRequest'>
export type NeuroManualSend = Schema<'NeuroManualSendRead'>
export type NeuroManualSendRequest = Schema<'NeuroManualSendRequest'>
export type NeuroObservedPost = Schema<'NeuroObservedPostRead'>
export type NeuroObservedPostPage = Schema<'NeuroObservedPostPageRead'>
export type NeuroObserveCampaignRequest = Schema<'NeuroObserveCampaignRequest'>
export type NeuroObserveTargetRequest = Schema<'NeuroObserveTargetRequest'>
export type NeuroEvent = Schema<'NeuroEventRead'>
export type NeuroEventPage = Schema<'NeuroEventPageRead'>
export type NeuroCampaignStats = Schema<'NeuroCampaignStatsRead'>
export type NeuroLiveReadiness = Schema<'NeuroLiveReadinessRead'>
export type NeuroPage<T> = { items: T[]; total: number; page: number; limit: number }
export type NeuroAccountStats = Schema<'NeuroAccountStatsRead'>
export type NeuroChannelStats = Schema<'NeuroChannelStatsRead'>
export type NeuroFailureReason = Schema<'NeuroFailureReasonRead'>
export type NeuroChannelRule = Schema<'NeuroChannelRuleRead'>
export type NeuroChannelRuleCreate = Schema<'NeuroChannelRuleCreate'>
export type NeuroPromptPreset = Schema<'NeuroPromptPresetRead'>
export type NeuroPromptPresetList = Schema<'NeuroPromptPresetListRead'>
