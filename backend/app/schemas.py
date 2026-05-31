from __future__ import annotations

# pyright: reportUnusedFunction=false, reportUnusedImport=false

from datetime import UTC, datetime
from typing import Annotated, Any, Literal, cast  # noqa: F401

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_serializer, field_validator  # noqa: F401

from app.contracts import accounts as _account_contracts
from app.contracts import jobs as _job_contracts
from app.contracts import neuro_commenting as _neuro_commenting_contracts
from app.modules.account_ggr import contracts as _ggr_contracts
from app.modules.account_lifecycle import contracts as _account_lifecycle_contracts
from app.modules.account_safety import gate_contracts as _safety_gate_contracts
from app.modules.account_safety import read_contracts as _safety_contracts
from app.modules.bought_onboarding import contracts as _bought_onboarding_contracts
from app.modules.human_behavior import contracts as _human_behavior_contracts
from app.modules.warmup import contracts as _warmup_contracts

_SCHEMA_COMMON_EXPORTS = (
    BaseModel,
    ConfigDict,
    StrictBool,
    field_serializer,
    field_validator,
    cast,
)

TerminalStatus = Literal["none", "banned", "deleted", "suspended"]

ProfileAudioAction = _account_contracts.ProfileAudioAction
ProfilePreviewRead = _account_contracts.ProfilePreviewRead
ProfilePreviewStepRead = _account_contracts.ProfilePreviewStepRead
JobSummaryRead = _job_contracts.JobSummaryRead
AccountCapabilityRead = _safety_contracts.AccountCapabilityRead
AccountOperationCooldownRead = _safety_contracts.AccountOperationCooldownRead
AccountOperationSafetyRead = _safety_contracts.AccountOperationSafetyRead
AccountRiskRead = _safety_contracts.AccountRiskRead
AccountSafetyRead = _safety_contracts.AccountSafetyRead
AccountSafetyReasonRead = _safety_contracts.AccountSafetyReasonRead
AccountSafetySummaryRead = _safety_contracts.AccountSafetySummaryRead
AccountValidityCheckRead = _safety_contracts.AccountValidityCheckRead
WorkspaceSafetyPolicyRead = _safety_gate_contracts.WorkspaceSafetyPolicyRead
WorkspaceSafetyPolicyUpdate = _safety_gate_contracts.WorkspaceSafetyPolicyUpdate
AccountDeletionPlannedActionRead = _account_lifecycle_contracts.AccountDeletionPlannedActionRead
AccountDeletionPreviewRead = _account_lifecycle_contracts.AccountDeletionPreviewRead
AccountDeletionRequestCreate = _account_lifecycle_contracts.AccountDeletionRequestCreate
AccountDeletionRequestRead = _account_lifecycle_contracts.AccountDeletionRequestRead
AccountExportRequestRead = _account_lifecycle_contracts.AccountExportRequestRead
GgrBreakdownRead = _ggr_contracts.GgrBreakdownRead
GgrScoreRead = _ggr_contracts.GgrScoreRead
BehaviorProfileRead = _human_behavior_contracts.BehaviorProfileRead
BoughtOnboardingStatusRead = _bought_onboarding_contracts.BoughtOnboardingStatusRead
NeuroAccountStatsPageRead = _neuro_commenting_contracts.NeuroAccountStatsPageRead
NeuroAccountStatsRead = _neuro_commenting_contracts.NeuroAccountStatsRead
NeuroAttemptPageRead = _neuro_commenting_contracts.NeuroAttemptPageRead
NeuroAttemptRead = _neuro_commenting_contracts.NeuroAttemptRead
NeuroCampaignStatsRead = _neuro_commenting_contracts.NeuroCampaignStatsRead
NeuroChannelStatsPageRead = _neuro_commenting_contracts.NeuroChannelStatsPageRead
NeuroChannelStatsRead = _neuro_commenting_contracts.NeuroChannelStatsRead
NeuroChannelRuleCreate = _neuro_commenting_contracts.NeuroChannelRuleCreate
NeuroChannelRulePageRead = _neuro_commenting_contracts.NeuroChannelRulePageRead
NeuroChannelRuleRead = _neuro_commenting_contracts.NeuroChannelRuleRead
NeuroFailureReasonPageRead = _neuro_commenting_contracts.NeuroFailureReasonPageRead
NeuroFailureReasonRead = _neuro_commenting_contracts.NeuroFailureReasonRead
NeuroCampaignAccountCreate = _neuro_commenting_contracts.NeuroCampaignAccountCreate
NeuroCampaignAccountPageRead = _neuro_commenting_contracts.NeuroCampaignAccountPageRead
NeuroCampaignAccountRead = _neuro_commenting_contracts.NeuroCampaignAccountRead
NeuroCampaignCreate = _neuro_commenting_contracts.NeuroCampaignCreate
NeuroCampaignPageRead = _neuro_commenting_contracts.NeuroCampaignPageRead
NeuroCampaignRead = _neuro_commenting_contracts.NeuroCampaignRead
NeuroCampaignUpdate = _neuro_commenting_contracts.NeuroCampaignUpdate
NeuroEventPageRead = _neuro_commenting_contracts.NeuroEventPageRead
NeuroEventRead = _neuro_commenting_contracts.NeuroEventRead
NeuroGeneratedCommentPageRead = _neuro_commenting_contracts.NeuroGeneratedCommentPageRead
NeuroGeneratedCommentRead = _neuro_commenting_contracts.NeuroGeneratedCommentRead
NeuroGeneratedCommentRejectRequest = _neuro_commenting_contracts.NeuroGeneratedCommentRejectRequest
NeuroGeneratedCommentUpdate = _neuro_commenting_contracts.NeuroGeneratedCommentUpdate
NeuroAcceptedJobRead = _neuro_commenting_contracts.NeuroAcceptedJobRead
NeuroGenerateObservedPostRequest = _neuro_commenting_contracts.NeuroGenerateObservedPostRequest
NeuroLimitCreate = _neuro_commenting_contracts.NeuroLimitCreate
NeuroLimitPageRead = _neuro_commenting_contracts.NeuroLimitPageRead
NeuroLimitRead = _neuro_commenting_contracts.NeuroLimitRead
NeuroLimitUpdate = _neuro_commenting_contracts.NeuroLimitUpdate
NeuroManualSendRead = _neuro_commenting_contracts.NeuroManualSendRead
NeuroManualSendRequest = _neuro_commenting_contracts.NeuroManualSendRequest
NeuroLiveReadinessCheckRead = _neuro_commenting_contracts.NeuroLiveReadinessCheckRead
NeuroLiveReadinessRead = _neuro_commenting_contracts.NeuroLiveReadinessRead
NeuroObservedPostPageRead = _neuro_commenting_contracts.NeuroObservedPostPageRead
NeuroObservedPostRead = _neuro_commenting_contracts.NeuroObservedPostRead
NeuroPromptPresetListRead = _neuro_commenting_contracts.NeuroPromptPresetListRead
NeuroPromptPresetRead = _neuro_commenting_contracts.NeuroPromptPresetRead
NeuroObserveCampaignRequest = _neuro_commenting_contracts.NeuroObserveCampaignRequest
NeuroObserveTargetRequest = _neuro_commenting_contracts.NeuroObserveTargetRequest
NeuroTargetBulkCreateItem = _neuro_commenting_contracts.NeuroTargetBulkCreateItem
NeuroTargetBulkCreateRead = _neuro_commenting_contracts.NeuroTargetBulkCreateRead
NeuroTargetBulkCreateRequest = _neuro_commenting_contracts.NeuroTargetBulkCreateRequest
NeuroTargetBulkSkippedItemRead = _neuro_commenting_contracts.NeuroTargetBulkSkippedItemRead
NeuroTargetCreate = _neuro_commenting_contracts.NeuroTargetCreate
NeuroTargetPageRead = _neuro_commenting_contracts.NeuroTargetPageRead
NeuroTargetRead = _neuro_commenting_contracts.NeuroTargetRead

WarmupCheckItemRead = _warmup_contracts.WarmupCheckItemRead
WarmupCheckSeverityRead = _warmup_contracts.WarmupCheckSeverityRead
WarmupEventPageRead = _warmup_contracts.WarmupEventPageRead
WarmupEventRead = _warmup_contracts.WarmupEventRead
WarmupExecutionModeRead = _warmup_contracts.WarmupExecutionModeRead
WarmupIsolationClaimRead = _warmup_contracts.WarmupIsolationClaimRead
WarmupIsolationStatusRead = _warmup_contracts.WarmupIsolationStatusRead
WarmupPauseRequest = _warmup_contracts.WarmupPauseRequest
WarmupPresetKindRead = _warmup_contracts.WarmupPresetKindRead
WarmupReadinessRead = _warmup_contracts.WarmupReadinessRead
WarmupSessionCreateRequest = _warmup_contracts.WarmupSessionCreateRequest
WarmupSessionPageRead = _warmup_contracts.WarmupSessionPageRead
WarmupSessionRead = _warmup_contracts.WarmupSessionRead
WarmupSessionStatusRead = _warmup_contracts.WarmupSessionStatusRead
WarmupSessionSummaryRead = _warmup_contracts.WarmupSessionSummaryRead
WarmupStatusRead = _warmup_contracts.WarmupStatusRead
WarmupStrategyRead = _warmup_contracts.WarmupStrategyRead
WarmupValidateRead = _warmup_contracts.WarmupValidateRead
WarmupValidateRequest = _warmup_contracts.WarmupValidateRequest

_ACCOUNT_EDITING_CONTRACT_NAMES = {
    "AccountUpdateCreate",
    "AccountUpdateJobSummaryRead",
    "AccountUpdatePreviewRead",
    "AccountUpdateProfileAudioDesiredState",
    "AccountUpdateProfileDesiredState",
    "AccountUpdateStoryDesiredState",
}

ProfileCooldownSeconds = Literal[0] | Annotated[int, Field(ge=30, le=600)]
OperationCooldownSeconds = Literal[0] | Annotated[int, Field(ge=30, le=86400)]


def __getattr__(name: str) -> object:
    if name not in _ACCOUNT_EDITING_CONTRACT_NAMES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from app.modules.account_editing import contracts as _account_editing_contracts

    value = getattr(_account_editing_contracts, name)
    globals()[name] = value
    return value


def _empty_readiness_risk_items() -> list[Any]:
    return []


def _empty_import_items() -> list[Any]:
    return []


def _serialize_utc_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat().replace("+00:00", "Z")


from app.schema_defs.accounts import (  # noqa: E402,F401
    AccountCreate,
    AccountListItemRead,
    AccountRead,
    AccountReadinessRiskRead,
    AccountReadinessRiskReasonRead,
    AccountReadinessRiskSummaryRead,
    AccountRuntimeDiagnosticsRead,
    AccountWarmupInfoRead,
    ActionGateRead,
    CurrentUserRead,
    QueueDescriptorRead,
    RuntimeRefreshRead,
    SensitiveAuditEventPageRead,
    SensitiveAuditEventRead,
    TdlibRuntimeStatusRead,
    WorkerDiagnosticsRead,
    WorkspaceFeatureFlagsUpdate,
    WorkspaceNotificationSettingsUpdate,
    WorkspaceRead,
)
from app.schema_defs.auth import (  # noqa: E402,F401
    AuthBatchCreate,
    AuthBatchEventRead,
    AuthBatchInvalidItemRead,
    AuthBatchItemRead,
    AuthBatchPhoneConflictRead,
    AuthBatchPhoneInput,
    AuthBatchPollRead,
    AuthBatchRead,
    AuthBatchSnapshotRead,
    AuthBatchSubmitCodeRequest,
    AuthBatchSubmitPasswordRequest,
    AuthBatchValidItemRead,
    AuthBatchValidatePhoneInput,
    AuthBatchValidateRead,
    AuthBatchValidateRequest,
    AuthRuntimeModeRead,
    AuthRuntimeModeUpdate,
    AuthStateRead,
    ExecutionPolicyRead,
    ExecutionPolicyUpdate,
    LivePreflightRead,
    OtpConfirmRequest,
    OtpStartRequest,
    PasswordSubmitRequest,
)
from app.schema_defs.dashboard_jobs import (  # noqa: E402,F401
    AssetRead,
    DashboardAccountRead,
    DashboardCurrentProfileRead,
    DashboardDiagnosticsRead,
    DashboardEditableFieldsRead,
    DashboardPipelineRead,
    DashboardProfileAudioRead,
    DashboardProfileRead,
    DashboardStoryPostRead,
    JobDetailRead,
    JobRead,
    JobStepListItemRead,
    JobStepResultRead,
    ProfileJobCreate,
    ProfilePreviewRequest,
    StoryCapabilitiesRead,
    StoryDraftCreate,
    StoryDraftRead,
    StoryDraftUpdate,
)
from app.schema_defs.operations import (  # noqa: E402,F401
    AccountBatchSafetyItemRead,
    AccountBatchSafetyPreviewRead,
    AccountBatchSafetyPreviewRequest,
    AccountImportBatchConfirm,
    AccountImportBatchCreate,
    AccountImportBatchRead,
    AccountImportBatchValidate,
    AccountImportItemRead,
    AccountOperationLogPageRead,
    AccountOperationLogRead,
    AccountProxyRead,
    AccountProxySummaryRead,
    AccountProxyUpsert,
    AccountSafetyOverrideCreate,
    AccountSafetyOverrideRead,
    AccountValidityCheckRequest,
    ApiErrorRead,
    DiagnosticsRead,
    FieldErrorRead,
    FrontendDiagnosticsDatabaseRead,
    FrontendDiagnosticsRedisRead,
    FrontendDiagnosticsStorageRead,
    FrontendDiagnosticsSummaryRead,
    FrontendDiagnosticsTdlibRead,
    FrontendDiagnosticsWorkersRead,
    ReadinessRead,
    RetryPolicyRead,
    TelegramAuthCodeSubmit,
    TelegramAuthPasswordSubmit,
    TelegramAuthSessionCreate,
    TelegramAuthSessionRead,
)
