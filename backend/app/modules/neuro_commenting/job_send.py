from __future__ import annotations

from app.modules.neuro_commenting.job_generate import NeuroCommentJobNotImplementedError


def prepare_send(*args: object, **kwargs: object) -> None:
    raise NeuroCommentJobNotImplementedError("prepare_send is planned for a later phase")


def send_comment(*args: object, **kwargs: object) -> None:
    raise NeuroCommentJobNotImplementedError("send_comment is disabled in foundation skeleton")


def run_send_attempt(attempt_id: str, workspace_id: str) -> str:
    from app.modules.neuro_commenting import job_handlers
    from app.modules.neuro_commenting.sender_service import SenderService

    with job_handlers.SessionLocal() as session:
        attempt = SenderService().send_attempt(
            session,
            attempt_id=attempt_id,
            workspace_id=workspace_id,
        )
        session.commit()
        return attempt.id


def reconcile_attempt(*args: object, **kwargs: object) -> None:
    raise NeuroCommentJobNotImplementedError("reconcile_attempt is planned for a later phase")


def refresh_target_health(*args: object, **kwargs: object) -> None:
    raise NeuroCommentJobNotImplementedError("refresh_target_health is planned for a later phase")
