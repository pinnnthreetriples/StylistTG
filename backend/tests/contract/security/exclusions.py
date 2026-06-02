"""Documented narrow exclusions for the contract-security profile (issue #266).

Every excluded endpoint or path must include:

- a precise pattern (path + method) so the exclusion cannot accidentally
  catch unrelated endpoints,
- a ``reason`` explaining why the exclusion is acceptable,
- an ``owner`` GitHub handle responsible for revisiting it,
- a ``follow_up_issue`` linking to the tracking issue.

The exclusion list is consumed by ``test_contract_security_exclusions``
to make sure each entry is well-formed, and by the Schemathesis fuzz
job (when it is migrated to consume this registry).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContractExclusion:
    path_pattern: str  # e.g. "/api/health"
    method: str  # "GET" / "POST" / "*"
    reason: str
    owner: str
    follow_up_issue: str

    def __post_init__(self) -> None:
        if not self.path_pattern.startswith("/"):
            raise ValueError(
                f"contract-security exclusion path must start with '/', got {self.path_pattern!r}"
            )
        if self.method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "*"}:
            raise ValueError(
                f"contract-security exclusion method must be an HTTP verb or '*', "
                f"got {self.method!r}"
            )
        if not self.reason.strip():
            raise ValueError("contract-security exclusion requires a non-empty reason")
        if not self.owner.startswith("@"):
            raise ValueError(
                f"contract-security exclusion owner must be a GitHub handle (start with '@'), "
                f"got {self.owner!r}"
            )
        if not self.follow_up_issue.startswith("#"):
            raise ValueError(
                f"contract-security exclusion follow_up_issue must reference an issue (#NN), "
                f"got {self.follow_up_issue!r}"
            )


# Current intentional exclusions. The registry is empty by default — adding an
# entry requires the four documented fields and a passing regression test.
CONTRACT_SECURITY_EXCLUSIONS: tuple[ContractExclusion, ...] = ()
