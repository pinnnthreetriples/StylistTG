from __future__ import annotations

import subprocess
from typing import Any

from scripts import check


def test_run_forces_utf8_subprocess_output(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run(*_args, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(args=kwargs.get("args", []), returncode=0, stdout="")

    monkeypatch.setattr(check.subprocess, "run", fake_run)

    ok, _elapsed = check._run(
        check.Check("sample", ["python", "-c", "print('ok')"], check.REPO_ROOT),
        verbose=False,
    )

    assert ok is True
    assert captured["env"]["PYTHONIOENCODING"] == "utf-8"
