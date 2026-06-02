from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.contracts.types import UuidString
from app.db import get_session
from app.modules.account_onboarding import service
from app.modules.account_onboarding.contracts import (
    AccountOnboardingArtifactCreate, AccountOnboardingArtifactRead, AccountOnboardingBatchCreate, AccountOnboardingBatchRead,
    AccountOnboardingCodeRequest, AccountOnboardingConfirmRequest, AccountOnboardingItemRead, AccountOnboardingMutationRequest,
    AccountOnboardingPasswordRequest, AccountOnboardingSnapshotRead, AccountOnboardingValidateRequest,
)
from app.modules.account_onboarding.errors import OnboardingError, to_app_error
from app.modules.auth.dependencies import AuthContext, require_authenticated, require_mutation_permission

router = APIRouter(tags=["account-onboarding"])


@router.post("/api/account-onboarding-batches", response_model=AccountOnboardingSnapshotRead, status_code=status.HTTP_201_CREATED)
def create_account_onboarding_batch(payload: AccountOnboardingBatchCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_mutation_permission)):
    try:
        response, _created = service.create_batch(session, workspace_id=auth.workspace_id, user_id=auth.user_id, payload=payload)
        return response
    except OnboardingError as exc:
        raise to_app_error(exc) from exc


@router.get("/api/account-onboarding-batches", response_model=list[AccountOnboardingBatchRead])
def list_account_onboarding_batches(session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)):
    return service.list_batches(session, workspace_id=auth.workspace_id)


@router.get("/api/account-onboarding-batches/{batch_id}", response_model=AccountOnboardingSnapshotRead)
def get_account_onboarding_batch(batch_id: UuidString, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)):
    try:
        return service.get_snapshot(session, workspace_id=auth.workspace_id, batch_id=batch_id)
    except OnboardingError as exc:
        raise to_app_error(exc) from exc


@router.post("/api/account-onboarding-batches/{batch_id}/validate", response_model=AccountOnboardingSnapshotRead)
def validate_account_onboarding_batch(batch_id: UuidString, payload: AccountOnboardingValidateRequest, session: Session = Depends(get_session), auth: AuthContext = Depends(require_mutation_permission)):
    try:
        return service.validate_batch(session, workspace_id=auth.workspace_id, user_id=auth.user_id, batch_id=batch_id, payload=payload)
    except OnboardingError as exc:
        raise to_app_error(exc) from exc


@router.post("/api/account-onboarding-batches/{batch_id}/confirm", response_model=AccountOnboardingSnapshotRead)
def confirm_account_onboarding_batch(batch_id: UuidString, payload: AccountOnboardingConfirmRequest, session: Session = Depends(get_session), auth: AuthContext = Depends(require_mutation_permission)):
    try:
        return service.confirm_batch(session, workspace_id=auth.workspace_id, user_id=auth.user_id, batch_id=batch_id, payload=payload)
    except OnboardingError as exc:
        raise to_app_error(exc) from exc


@router.post("/api/account-onboarding-batches/{batch_id}/cancel", response_model=AccountOnboardingSnapshotRead)
def cancel_account_onboarding_batch(batch_id: UuidString, payload: AccountOnboardingMutationRequest, session: Session = Depends(get_session), auth: AuthContext = Depends(require_mutation_permission)):
    try:
        return service.cancel_batch(session, workspace_id=auth.workspace_id, user_id=auth.user_id, batch_id=batch_id, payload=payload)
    except OnboardingError as exc:
        raise to_app_error(exc) from exc


@router.post("/api/account-onboarding-batches/{batch_id}/items/{item_id}/retry", response_model=AccountOnboardingItemRead)
def retry_account_onboarding_item(batch_id: UuidString, item_id: UuidString, payload: AccountOnboardingMutationRequest, session: Session = Depends(get_session), auth: AuthContext = Depends(require_mutation_permission)):
    try:
        return service.retry_item(session, workspace_id=auth.workspace_id, user_id=auth.user_id, batch_id=batch_id, item_id=item_id, payload=payload)
    except OnboardingError as exc:
        raise to_app_error(exc) from exc


@router.post("/api/account-onboarding-batches/{batch_id}/items/{item_id}/code", response_model=AccountOnboardingItemRead)
def submit_account_onboarding_code(batch_id: UuidString, item_id: UuidString, payload: AccountOnboardingCodeRequest, session: Session = Depends(get_session), auth: AuthContext = Depends(require_mutation_permission)):
    try:
        return service.submit_code(session, workspace_id=auth.workspace_id, user_id=auth.user_id, batch_id=batch_id, item_id=item_id, payload=payload)
    except OnboardingError as exc:
        raise to_app_error(exc) from exc


@router.post("/api/account-onboarding-batches/{batch_id}/items/{item_id}/password", response_model=AccountOnboardingItemRead)
def submit_account_onboarding_password(batch_id: UuidString, item_id: UuidString, payload: AccountOnboardingPasswordRequest, session: Session = Depends(get_session), auth: AuthContext = Depends(require_mutation_permission)):
    try:
        return service.submit_password(session, workspace_id=auth.workspace_id, user_id=auth.user_id, batch_id=batch_id, item_id=item_id, payload=payload)
    except OnboardingError as exc:
        raise to_app_error(exc) from exc


@router.post("/api/account-onboarding-artifacts", response_model=AccountOnboardingArtifactRead, status_code=status.HTTP_201_CREATED)
def upload_account_onboarding_artifact(payload: AccountOnboardingArtifactCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_mutation_permission)):
    try:
        response, _created = service.upload_artifact(session, workspace_id=auth.workspace_id, user_id=auth.user_id, payload=payload)
        return response
    except OnboardingError as exc:
        raise to_app_error(exc) from exc


__all__ = ["router"]

