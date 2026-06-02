"""Tests for the mutation-allowlist loader (issue #267)."""

# test-analyzer: disable-file=TQA030 reason="schema-validation tests deliberately repeat similar JSON payloads"

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from scripts import mutation_allowlist

pytestmark = pytest.mark.unit


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_returns_empty_list_when_file_missing(tmp_path: Path) -> None:
    assert mutation_allowlist.load_allowlist(tmp_path / "missing.json") == []


def test_load_returns_empty_list_for_empty_entries(tmp_path: Path) -> None:
    path = tmp_path / "allow.json"
    _write(path, {"entries": []})
    assert mutation_allowlist.load_allowlist(path) == []


def test_load_parses_well_formed_entry(tmp_path: Path) -> None:
    path = tmp_path / "allow.json"
    _write(
        path,
        {
            "entries": [
                {
                    "module": "app/x.py",
                    "mutant_signature": "x.py:1:replace_=_with_!=",
                    "reason": "equivalent mutation",
                    "owner": "@octocat",
                    "follow_up_issue": "#1",
                    "expires_at": "2099-01-01",
                }
            ]
        },
    )
    entries = mutation_allowlist.load_allowlist(path)
    assert len(entries) == 1
    assert entries[0].owner == "@octocat"
    assert entries[0].expires_at == date(2099, 1, 1)


def test_load_rejects_missing_field(tmp_path: Path) -> None:
    path = tmp_path / "allow.json"
    _write(
        path,
        {
            "entries": [
                {
                    "module": "app/x.py",
                    "mutant_signature": "sig",
                    "reason": "r",
                    "owner": "@o",
                    # follow_up_issue missing
                    "expires_at": "2099-01-01",
                }
            ]
        },
    )
    with pytest.raises(ValueError, match="missing fields"):
        mutation_allowlist.load_allowlist(path)


def test_load_rejects_bad_owner_format(tmp_path: Path) -> None:
    path = tmp_path / "allow.json"
    _write(
        path,
        {
            "entries": [
                {
                    "module": "app/x.py",
                    "mutant_signature": "sig",
                    "reason": "r",
                    "owner": "octocat",
                    "follow_up_issue": "#1",
                    "expires_at": "2099-01-01",
                }
            ]
        },
    )
    with pytest.raises(ValueError, match="GitHub handle"):
        mutation_allowlist.load_allowlist(path)


def test_load_rejects_bad_expires_at(tmp_path: Path) -> None:
    path = tmp_path / "allow.json"
    _write(
        path,
        {
            "entries": [
                {
                    "module": "app/x.py",
                    "mutant_signature": "sig",
                    "reason": "r",
                    "owner": "@o",
                    "follow_up_issue": "#1",
                    "expires_at": "not-a-date",
                }
            ]
        },
    )
    with pytest.raises(ValueError, match="ISO date"):
        mutation_allowlist.load_allowlist(path)


def test_active_entries_filters_expired(tmp_path: Path) -> None:
    path = tmp_path / "allow.json"
    _write(
        path,
        {
            "entries": [
                {
                    "module": "app/x.py",
                    "mutant_signature": "active",
                    "reason": "r",
                    "owner": "@o",
                    "follow_up_issue": "#1",
                    "expires_at": "2099-01-01",
                },
                {
                    "module": "app/x.py",
                    "mutant_signature": "expired",
                    "reason": "r",
                    "owner": "@o",
                    "follow_up_issue": "#1",
                    "expires_at": "2020-01-01",
                },
            ]
        },
    )
    active = mutation_allowlist.active_entries(path, today=date(2026, 6, 2))
    assert [e.mutant_signature for e in active] == ["active"]


def test_default_allowlist_loads_without_error() -> None:
    # The shipped default lives at backend/scripts/mutation_allowlist.json.
    entries = mutation_allowlist.load_allowlist()
    assert isinstance(entries, list)
