from __future__ import annotations

from app.db import SessionLocal as _SessionLocal
from app.modules.neuro_commenting.ai_comment_generator import (
    build_ai_comment_generator as _build_ai_comment_generator,
)
from app.modules.neuro_commenting.discussion_resolver import (
    build_discussion_message_resolver as _build_discussion_message_resolver,
)
from app.modules.neuro_commenting.job_generate import *  # noqa: F403
from app.modules.neuro_commenting.job_observe import *  # noqa: F403
from app.modules.neuro_commenting.job_observe_common import *  # noqa: F403
from app.modules.neuro_commenting.job_observe_target import *  # noqa: F403
from app.modules.neuro_commenting.job_send import *  # noqa: F403

build_ai_comment_generator = _build_ai_comment_generator
build_discussion_message_resolver = _build_discussion_message_resolver
SessionLocal = _SessionLocal
