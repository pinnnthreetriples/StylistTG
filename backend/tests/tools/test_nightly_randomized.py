from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scripts import nightly_randomized


def test_run_seed_ignores_contract_tests_in_whole_tree_command(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], **_: object) -> SimpleNamespace:
        captured["cmd"] = cmd
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(nightly_randomized.subprocess, "run", fake_run)

    nightly_randomized._run_seed("101", tmp_path, "not live and not contract", [])

    assert "--ignore=tests/contract" in captured["cmd"]
