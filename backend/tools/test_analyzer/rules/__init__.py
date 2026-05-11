"""Rule registry — aggregates all rules into ALL_RULES."""
from __future__ import annotations

from ..models import Rule
from .assertions import (
    AssertSelfEquality,
    AssertTrue,
    ManualExceptionCatch,
    TooManyAssertions,
    UnittestAssertTrue,
    ZeroAssertions,
)
from .duplicates import DuplicateAssertionPattern, DuplicateSetup
from .edge_cases import MissingEdgeCase
from .flaky import (
    DatetimeNow,
    ExternalHTTPWithoutMarker,
    FilesystemWriteOutsideTmp,
    RandomWithoutSeed,
    TimeSleep,
)
from .mocks import MockWithoutAssert, MonkeypatchAfterCall, PatchStartWithoutStop
from .stylisttg import (
    AmbiguousStatusCode,
    API4xxWithoutErrorCode,
    DependencyOverridesWithoutFinally,
    LiveMarkerWithoutEnvSkip,
    LiveTestWithoutEnvGuard,
    RateLimitWithoutExceededCase,
    RBACRouteNotInMatrix,
    RuntimeRandomSecret,
    S3StubberWithoutContext,
    TestClientWithoutAppClient,
)

ALL_RULES: list[Rule] = [
    # Assertions
    ZeroAssertions(),
    AssertTrue(),
    AssertSelfEquality(),
    TooManyAssertions(),
    UnittestAssertTrue(),
    ManualExceptionCatch(),
    # Flaky
    TimeSleep(),
    RandomWithoutSeed(),
    DatetimeNow(),
    ExternalHTTPWithoutMarker(),
    FilesystemWriteOutsideTmp(),
    # Mocks
    MockWithoutAssert(),
    PatchStartWithoutStop(),
    MonkeypatchAfterCall(),
    # Duplicates
    DuplicateSetup(),
    DuplicateAssertionPattern(),
    # Edge cases
    MissingEdgeCase(),
    # Project-specific
    DependencyOverridesWithoutFinally(),
    TestClientWithoutAppClient(),
    API4xxWithoutErrorCode(),
    AmbiguousStatusCode(),
    LiveTestWithoutEnvGuard(),
    S3StubberWithoutContext(),
    RateLimitWithoutExceededCase(),
    RBACRouteNotInMatrix(),
    RuntimeRandomSecret(),
    LiveMarkerWithoutEnvSkip(),
]
