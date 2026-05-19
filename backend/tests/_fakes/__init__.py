"""Shared test doubles for the neuro-commenting safety pipeline.

The production code already ships several fakes (FakeAICommentProvider,
FakeTelegramPostObserver, FakeTelegramCommentSender). This package collects
them under a single namespace and adds error-injection helpers used by the
Phase 0 Task 5 end-to-end pipeline test.
"""

from tests._fakes.fake_tdlib_runtime import (
    FakeTdlibRuntime,
    InjectableSender,
    SeededObserver,
)

__all__ = ["FakeTdlibRuntime", "InjectableSender", "SeededObserver"]
