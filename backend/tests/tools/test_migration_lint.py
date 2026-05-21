from __future__ import annotations

import subprocess
from pathlib import Path

from tools import migration_lint


def _write_migration(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "20260520_9999_test.py"
    path.write_text(body, encoding="utf-8")
    return path


def test_main_fails_for_unsafe_nullable_false_alter(tmp_path: Path) -> None:
    path = _write_migration(
        tmp_path,
        'def upgrade():\n    op.alter_column("accounts", "name", nullable=False)\n',
    )

    exit_code = migration_lint.main(["--paths", str(path)])

    assert exit_code == 1


def test_drop_column_without_two_deploy_comment_fails(tmp_path: Path) -> None:
    path = _write_migration(tmp_path, 'def upgrade():\n    op.drop_column("accounts", "old")\n')

    report = migration_lint.lint_paths([path])

    assert report.has_errors


def test_downgrade_drop_column_is_not_linted(tmp_path: Path) -> None:
    path = _write_migration(
        tmp_path,
        (
            "def upgrade():\n"
            '    op.add_column("accounts", sa.Column("note", sa.Text(), nullable=True))\n'
            "\n"
            "def downgrade():\n"
            '    op.drop_column("accounts", "note")\n'
        ),
    )

    report = migration_lint.lint_paths([path])

    assert not report.has_errors


def test_upgrade_helper_operations_are_linted(tmp_path: Path) -> None:
    path = _write_migration(
        tmp_path,
        (
            "def add_required_column():\n"
            '    op.add_column("accounts", sa.Column("flag", sa.Boolean(), nullable=False))\n'
            "\n"
            "def upgrade():\n"
            "    add_required_column()\n"
        ),
    )

    report = migration_lint.lint_paths([path])

    assert report.has_errors


def test_add_not_null_column_without_server_default_fails(tmp_path: Path) -> None:
    path = _write_migration(
        tmp_path,
        'def upgrade():\n    op.add_column("accounts", sa.Column("flag", sa.Boolean(), nullable=False))\n',
    )

    report = migration_lint.lint_paths([path])

    assert report.has_errors


def test_batch_add_not_null_column_without_server_default_fails(tmp_path: Path) -> None:
    path = _write_migration(
        tmp_path,
        (
            "def upgrade():\n"
            '    with op.batch_alter_table("accounts") as batch_op:\n'
            '        batch_op.add_column(sa.Column("flag", sa.Boolean(), nullable=False))\n'
        ),
    )

    report = migration_lint.lint_paths([path])

    assert report.has_errors


def test_batch_drop_column_without_two_deploy_comment_fails(tmp_path: Path) -> None:
    path = _write_migration(
        tmp_path,
        (
            "def upgrade():\n"
            '    with op.batch_alter_table("accounts") as batch_op:\n'
            '        batch_op.drop_column("old")\n'
        ),
    )

    report = migration_lint.lint_paths([path])

    assert report.has_errors


def test_add_not_null_column_with_none_server_default_fails(tmp_path: Path) -> None:
    path = _write_migration(
        tmp_path,
        (
            "def upgrade():\n"
            '    op.add_column("accounts", sa.Column("flag", sa.Boolean(), '
            "nullable=False, server_default=None))\n"
        ),
    )

    report = migration_lint.lint_paths([path])

    assert report.has_errors


def test_not_null_column_with_server_default_passes(tmp_path: Path) -> None:
    path = _write_migration(
        tmp_path,
        (
            "def upgrade():\n"
            "    op.add_column(\n"
            '        "accounts",\n'
            '        sa.Column("flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),\n'
            "    )\n"
        ),
    )

    report = migration_lint.lint_paths([path])

    assert not report.has_errors


def test_drop_column_with_two_deploy_comment_passes(tmp_path: Path) -> None:
    path = _write_migration(
        tmp_path,
        (
            "def upgrade():\n"
            "    # safe: column unused in code since release 2.5\n"
            '    op.drop_column("accounts", "old")\n'
        ),
    )

    report = migration_lint.lint_paths([path])

    assert not report.has_errors


def test_large_table_operation_without_online_schema_comment_warns(tmp_path: Path) -> None:
    path = _write_migration(
        tmp_path,
        'def upgrade():\n    op.create_index("ix_accounts_name", "accounts", ["name"])\n',
    )

    report = migration_lint.lint_paths([path])

    assert report.has_warnings and not report.has_errors


def test_changed_migration_paths_are_resolved_from_repo_root(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], Path | None]] = []

    def fake_run(
        cmd: list[str],
        *,
        capture_output: bool,
        check: bool,
        text: bool,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del capture_output, check, text
        calls.append((cmd, cwd))
        if cmd[:3] == ["git", "rev-parse", "--show-toplevel"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=f"{tmp_path}\n", stderr="")
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout="backend/migrations/versions/20260520_9999_test.py\n",
            stderr="",
        )

    monkeypatch.setattr(migration_lint.subprocess, "run", fake_run)

    paths = migration_lint.changed_migration_paths("origin/main")

    assert paths == [tmp_path / "backend/migrations/versions/20260520_9999_test.py"]
    assert calls[-1][1] == tmp_path
