from __future__ import annotations

from importlib import import_module
from typing import Any

from app import config as _config
from app.modules.neuro_commenting import enqueue as _enqueue

from .router_base import router

settings = _config.settings


def enqueue_neuro_generate_comment(*args: Any, **kwargs: Any) -> Any:
    return _enqueue.enqueue_neuro_generate_comment(*args, **kwargs)


def enqueue_neuro_observe_campaign(*args: Any, **kwargs: Any) -> Any:
    return _enqueue.enqueue_neuro_observe_campaign(*args, **kwargs)


def enqueue_neuro_observe_target(*args: Any, **kwargs: Any) -> Any:
    return _enqueue.enqueue_neuro_observe_target(*args, **kwargs)


def enqueue_neuro_refresh_target_metadata(*args: Any, **kwargs: Any) -> Any:
    return _enqueue.enqueue_neuro_refresh_target_metadata(*args, **kwargs)


def enqueue_neuro_send_attempt(*args: Any, **kwargs: Any) -> Any:
    return _enqueue.enqueue_neuro_send_attempt(*args, **kwargs)


def neuro_generate_comment_job_id(*args: Any, **kwargs: Any) -> Any:
    return _enqueue.neuro_generate_comment_job_id(*args, **kwargs)


_ROUTE_MODULES = (
    "router_campaigns",
    "router_campaign_accounts",
    "router_targets",
    "router_limits_rules",
    "router_lifecycle",
    "router_comments",
    "router_observe",
    "router_attempts_events",
)

for _module_name in _ROUTE_MODULES:
    import_module(f"{__package__}.{_module_name}")

__all__ = [
    "enqueue_neuro_generate_comment",
    "enqueue_neuro_observe_campaign",
    "enqueue_neuro_observe_target",
    "enqueue_neuro_refresh_target_metadata",
    "enqueue_neuro_send_attempt",
    "neuro_generate_comment_job_id",
    "router",
    "settings",
]
