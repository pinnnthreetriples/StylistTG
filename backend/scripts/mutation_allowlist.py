"""Allowlist loader for mutation testing (issue #267).

A mutmut survivor that maps to a genuinely equivalent mutation can be
allowlisted instead of failing the build. Each allowlist entry must
include the four mandatory fields below; the loader fails fast on
malformed entries so the gate cannot silently weaken.

Schema (backend/scripts/mutation_allowlist.json):

    {
      "entries": [
        {
          "module": "app/services/secret_redaction.py",
          "mutant_signature": "secret_redaction.py:42:replace_=_with_!=",
          "reason": "the mutant flips a debug-only branch with no observable behaviour",
          "owner": "@octocat",
          "follow_up_issue": "#NN",
          "expires_at": "2026-12-31"
        }
      ]
    }

Every entry has an explicit ``expires_at`` (ISO date). After expiry the
loader marks the entry as invalid and the mutation gate fails — that
forces the allowlist to be revisited rather than left rotting.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ALLOWLIST_PATH = REPO_ROOT / "scripts" / "mutation_allowlist.json"


@dataclass(frozen=True)
class MutationAllowlistEntry:
    module: str
    mutant_signature: str
    reason: str
    owner: str
    follow_up_issue: str
    expires_at: date

    def is_expired(self, today: date | None = None) -> bool:
        return (today or date.today()) > self.expires_at


def _parse_entry(raw: dict[str, object]) -> MutationAllowlistEntry:
    required = ("module", "mutant_signature", "reason", "owner", "follow_up_issue", "expires_at")
    missing = [k for k in required if k not in raw]
    if missing:
        raise ValueError(f"mutation allowlist entry missing fields: {missing}; got {raw!r}")

    module = str(raw["module"])
    mutant_signature = str(raw["mutant_signature"])
    reason = str(raw["reason"]).strip()
    owner = str(raw["owner"])
    follow_up_issue = str(raw["follow_up_issue"])
    expires_at_raw = str(raw["expires_at"])

    if not reason:
        raise ValueError(f"mutation allowlist entry has empty reason: {raw!r}")
    if not owner.startswith("@"):
        raise ValueError(f"owner must be a GitHub handle ('@…'), got {owner!r}")
    if not follow_up_issue.startswith("#"):
        raise ValueError(
            f"follow_up_issue must reference an issue ('#NN'), got {follow_up_issue!r}"
        )
    try:
        expires_at = date.fromisoformat(expires_at_raw)
    except ValueError as exc:
        raise ValueError(
            f"expires_at must be an ISO date (YYYY-MM-DD), got {expires_at_raw!r}: {exc}"
        ) from exc

    return MutationAllowlistEntry(
        module=module,
        mutant_signature=mutant_signature,
        reason=reason,
        owner=owner,
        follow_up_issue=follow_up_issue,
        expires_at=expires_at,
    )


def load_allowlist(
    path: Path | str = DEFAULT_ALLOWLIST_PATH,
) -> list[MutationAllowlistEntry]:
    """Parse the allowlist JSON; raise ``ValueError`` on any malformed entry."""
    path = Path(path)
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"mutation allowlist root must be an object, got {type(payload).__name__}")
    entries_raw = payload.get("entries", [])
    if not isinstance(entries_raw, list):
        raise ValueError(
            f"mutation allowlist 'entries' must be a list, got {type(entries_raw).__name__}"
        )
    return [_parse_entry(entry) for entry in entries_raw]


def active_entries(
    path: Path | str = DEFAULT_ALLOWLIST_PATH,
    *,
    today: date | None = None,
) -> list[MutationAllowlistEntry]:
    """Return non-expired allowlist entries; raise on malformed JSON."""
    return [e for e in load_allowlist(path) if not e.is_expired(today)]
