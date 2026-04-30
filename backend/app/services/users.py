from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import User, UserStatus, utc_now


def get_or_create_external_user(
    session: Session,
    *,
    provider: str,
    external_user_id: str,
    email: str,
    display_name: str | None = None,
) -> User:
    user = (
        session.query(User)
        .filter_by(external_auth_provider=provider, external_auth_user_id=external_user_id)
        .one_or_none()
    )
    if user is None:
        user = User(
            email=email,
            display_name=display_name,
            external_auth_provider=provider,
            external_auth_user_id=external_user_id,
            status=UserStatus.ACTIVE,
        )
        session.add(user)
    else:
        user.email = email or user.email
        user.display_name = display_name or user.display_name
        user.updated_at = utc_now()
    session.flush()
    return user
