"""Unit tests for tools/test_analyzer.py."""
from __future__ import annotations

import json
import sys
import tempfile
import textwrap
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from test_analyzer import (  # noqa: E402
    Analyzer,
    AnalyzerConfig,
    Issue,
    JsonReporter,
    SarifReporter,
    Severity,
    filter_by_baseline,
    load_baseline,
    main,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _analyze_source(source: str, config: AnalyzerConfig | None = None) -> list[Issue]:
    """Analyze a source string and return issues."""
    cfg = config or AnalyzerConfig()
    analyzer = Analyzer(cfg)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", prefix="test_", delete=False) as f:
        f.write(source)
        f.flush()
        path = Path(f.name)

    try:
        issues = analyzer.analyze_file(path, path.parent)
    finally:
        path.unlink(missing_ok=True)

    return issues


# ---------------------------------------------------------------------------
# TQA001: Zero assertions
# ---------------------------------------------------------------------------


def test_tqa001_zero_assertions() -> None:
    source = textwrap.dedent("""\
        def test_nothing():
            x = 1 + 1
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "TQA001" in rule_ids


def test_tqa001_pytest_raises_counts_as_assertion() -> None:
    source = textwrap.dedent("""\
        import pytest

        def test_raises():
            with pytest.raises(ValueError):
                int("abc")
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "TQA001" not in rule_ids


# ---------------------------------------------------------------------------
# TQA002: assert True
# ---------------------------------------------------------------------------


def test_tqa002_assert_true() -> None:
    source = textwrap.dedent("""\
        def test_trivial():
            assert True
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "TQA002" in rule_ids


def test_tqa002_normal_assert_no_issue() -> None:
    source = textwrap.dedent("""\
        def test_ok():
            assert 1 == 1
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "TQA002" not in rule_ids


# ---------------------------------------------------------------------------
# TQA003: assert x == x
# ---------------------------------------------------------------------------


def test_tqa003_self_equality() -> None:
    source = textwrap.dedent("""\
        def test_self_eq():
            x = 42
            assert x == x
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "TQA003" in rule_ids


# ---------------------------------------------------------------------------
# TQA004: Too many assertions
# ---------------------------------------------------------------------------


def test_tqa004_too_many_assertions() -> None:
    asserts = "\n".join(f"    assert {i} == {i}" for i in range(15))
    source = f"def test_many():\n{asserts}\n"
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "TQA004" in rule_ids


def test_tqa004_within_limit_no_issue() -> None:
    asserts = "\n".join(f"    assert {i} == {i}" for i in range(5))
    source = f"def test_few():\n{asserts}\n"
    issues = _analyze_source(source)
    # TQA003 will fire but TQA004 should not
    tqa004 = [i for i in issues if i.rule_id == "TQA004"]
    assert tqa004 == []


# ---------------------------------------------------------------------------
# TQA006: Manual exception catch
# ---------------------------------------------------------------------------


def test_tqa006_manual_exception_catch() -> None:
    source = textwrap.dedent("""\
        import pytest

        def test_manual_catch():
            try:
                do_something()
            except ValueError:
                pass
            else:
                assert False
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "TQA006" in rule_ids


# ---------------------------------------------------------------------------
# TQA020: Mock without assert_called
# ---------------------------------------------------------------------------


def test_tqa020_mock_without_assert() -> None:
    source = textwrap.dedent("""\
        from unittest.mock import MagicMock

        def test_mock_unused():
            mock = MagicMock()
            do_something(mock)
            assert True
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "TQA020" in rule_ids


def test_tqa020_mock_with_assert_called_no_issue() -> None:
    source = textwrap.dedent("""\
        from unittest.mock import MagicMock

        def test_mock_verified():
            mock = MagicMock()
            do_something(mock)
            mock.assert_called_once()
    """)
    issues = _analyze_source(source)
    tqa020 = [i for i in issues if i.rule_id == "TQA020"]
    assert tqa020 == []


# ---------------------------------------------------------------------------
# STG001: dependency_overrides without finally
# ---------------------------------------------------------------------------


def test_stg001_overrides_without_finally() -> None:
    source = textwrap.dedent("""\
        from app.main import app

        def test_no_cleanup():
            app.dependency_overrides[get_db] = lambda: db
            response = client.get("/")
            assert response.status_code == 200
            app.dependency_overrides.clear()
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "STG001" in rule_ids


def test_stg001_overrides_with_finally_no_issue() -> None:
    source = textwrap.dedent("""\
        from app.main import app

        def test_with_cleanup():
            app.dependency_overrides[get_db] = lambda: db
            try:
                response = client.get("/")
                assert response.status_code == 200
            finally:
                app.dependency_overrides.clear()
    """)
    issues = _analyze_source(source)
    stg001 = [i for i in issues if i.rule_id == "STG001"]
    assert stg001 == []


# ---------------------------------------------------------------------------
# STG006: S3 Stubber without context manager
# ---------------------------------------------------------------------------


def test_stg006_stubber_without_context() -> None:
    source = textwrap.dedent("""\
        from botocore.stub import Stubber

        def test_s3_no_context():
            stubber = Stubber(client)
            stubber.add_response("put_object", {}, {})
            stubber.activate()
            result = do_upload()
            assert result is not None
            stubber.deactivate()
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "STG006" in rule_ids


def test_stg006_stubber_with_context_no_issue() -> None:
    source = textwrap.dedent("""\
        from botocore.stub import Stubber

        def test_s3_with_context():
            stubber = Stubber(client)
            stubber.add_response("put_object", {}, {})
            with stubber:
                result = do_upload()
            assert result is not None
    """)
    issues = _analyze_source(source)
    stg006 = [i for i in issues if i.rule_id == "STG006"]
    assert stg006 == []


# ---------------------------------------------------------------------------
# STG005/STG010: Live test without env skip
# ---------------------------------------------------------------------------


def test_stg005_live_without_env_guard() -> None:
    source = textwrap.dedent("""\
        import pytest

        @pytest.mark.live
        def test_live_no_guard():
            adapter = build_adapter()
            assert adapter is not None
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "STG005" in rule_ids or "STG010" in rule_ids


# ---------------------------------------------------------------------------
# JSON Reporter
# ---------------------------------------------------------------------------


def test_json_reporter_output() -> None:
    issues = [
        Issue(
            rule_id="TQA001",
            rule_type="assertions",
            severity=Severity.CRITICAL,
            file="tests/test_foo.py",
            line=10,
            message="Test has zero assertions",
            recommendation="Add assertions",
        ),
    ]
    reporter = JsonReporter()
    output = reporter.report(issues)
    data = json.loads(output)
    assert data["summary"]["total"] == 1
    assert data["summary"]["by_severity"]["CRITICAL"] == 1
    assert len(data["issues"]) == 1
    assert data["issues"][0]["rule_id"] == "TQA001"
    assert "fingerprint" in data["issues"][0]


# ---------------------------------------------------------------------------
# SARIF Reporter
# ---------------------------------------------------------------------------


def test_sarif_reporter_output() -> None:
    issues = [
        Issue(
            rule_id="TQA002",
            rule_type="assertions",
            severity=Severity.CRITICAL,
            file="tests/test_bar.py",
            line=5,
            message="assert True is no-op",
            recommendation="Replace with meaningful assertion",
        ),
    ]
    reporter = SarifReporter()
    output = reporter.report(issues)
    data = json.loads(output)
    assert data["version"] == "2.1.0"
    assert len(data["runs"]) == 1
    run = data["runs"][0]
    assert run["tool"]["driver"]["name"] == "test-quality-analyzer"
    assert len(run["results"]) == 1
    result = run["results"][0]
    assert result["ruleId"] == "TQA002"
    assert result["level"] == "error"
    assert result["locations"][0]["physicalLocation"]["region"]["startLine"] == 5


# ---------------------------------------------------------------------------
# Baseline filtering
# ---------------------------------------------------------------------------


def test_baseline_filters_known_issues(tmp_path: Path) -> None:
    issue = Issue(
        rule_id="TQA001",
        rule_type="assertions",
        severity=Severity.CRITICAL,
        file="tests/test_x.py",
        line=1,
        message="zero",
        recommendation="fix",
    )
    baseline_data = {"issues": [{"fingerprint": issue.fingerprint()}]}
    baseline_file = tmp_path / "baseline.json"
    baseline_file.write_text(json.dumps(baseline_data))

    baseline = load_baseline(baseline_file)
    filtered = filter_by_baseline([issue], baseline)
    assert filtered == []


def test_baseline_passes_new_issues(tmp_path: Path) -> None:
    issue = Issue(
        rule_id="TQA002",
        rule_type="assertions",
        severity=Severity.CRITICAL,
        file="tests/test_y.py",
        line=5,
        message="assert True",
        recommendation="fix",
    )
    baseline_file = tmp_path / "baseline.json"
    baseline_file.write_text(json.dumps({"issues": []}))

    baseline = load_baseline(baseline_file)
    filtered = filter_by_baseline([issue], baseline)
    assert len(filtered) == 1


# ---------------------------------------------------------------------------
# Suppressions
# ---------------------------------------------------------------------------


def test_suppression_with_reason_hides_issue() -> None:
    source = textwrap.dedent("""\
        # test-analyzer: disable=TQA001 reason="intentional smoke test"
        def test_smoke():
            run_app()
    """)
    issues = _analyze_source(source)
    tqa001 = [i for i in issues if i.rule_id == "TQA001"]
    assert tqa001 == []


def test_suppression_without_reason_emits_warning() -> None:
    source = textwrap.dedent("""\
        # test-analyzer: disable=TQA001
        def test_smoke():
            run_app()
    """)
    issues = _analyze_source(source)
    meta = [i for i in issues if i.rule_id == "META001"]
    assert len(meta) == 1
    assert "without reason" in meta[0].message


# ---------------------------------------------------------------------------
# CLI exit codes
# ---------------------------------------------------------------------------


def test_cli_exit_code_0_no_critical(tmp_path: Path) -> None:
    test_file = tmp_path / "test_ok.py"
    test_file.write_text("def test_fine():\n    assert 1 == 1\n")
    code = main(["--path", str(test_file)])
    assert code == 0


def test_cli_exit_code_1_critical(tmp_path: Path) -> None:
    test_file = tmp_path / "test_bad.py"
    test_file.write_text("def test_nothing():\n    x = 1\n")
    code = main(["--path", str(test_file)])
    assert code == 1


def test_cli_exit_code_2_invalid_path() -> None:
    code = main(["--path", "/nonexistent/path/to/tests"])
    assert code == 2


# ---------------------------------------------------------------------------
# Coverage integration
# ---------------------------------------------------------------------------


def test_coverage_data_generates_branch_warnings() -> None:
    """Analyzer emits TQA040 for source files with uncovered branches."""
    coverage_data = {
        "files": {
            "app/services/auth.py": {
                "summary": {
                    "num_branches": 20,
                    "covered_branches": 14,
                }
            },
            "app/services/jobs.py": {
                "summary": {
                    "num_branches": 10,
                    "covered_branches": 10,
                }
            },
        }
    }
    analyzer = Analyzer(AnalyzerConfig(), coverage_data=coverage_data)
    issues = analyzer._coverage_branch_warnings()
    assert len(issues) == 1
    assert issues[0].rule_id == "TQA040"
    assert issues[0].file == "app/services/auth.py"
    assert "6 of 20 branches" in issues[0].message


def test_cli_coverage_flag_accepted(tmp_path: Path) -> None:
    """CLI --coverage flag is parsed and does not crash."""
    test_file = tmp_path / "test_ok.py"
    test_file.write_text("def test_fine():\n    assert 1 == 1\n")
    coverage_file = tmp_path / "coverage.json"
    coverage_file.write_text(json.dumps({
        "files": {
            "app/example.py": {
                "summary": {"num_branches": 4, "covered_branches": 2}
            }
        }
    }))
    code = main([
        "--path", str(test_file),
        "--coverage", str(coverage_file),
    ])
    assert code == 0


# ---------------------------------------------------------------------------
# Config: severity overrides, thresholds, project rule toggles
# ---------------------------------------------------------------------------


def test_config_max_assertions_per_test_applied() -> None:
    """max_assertions_per_test config actually changes threshold."""
    source = textwrap.dedent("""\
        def test_many():
            assert 1
            assert 2
            assert 3
            assert 4
            assert 5
    """)
    # Default (12) — should not fire
    issues_default = _analyze_source(source)
    tqa004 = [i for i in issues_default if i.rule_id == "TQA004"]
    assert len(tqa004) == 0

    # Override threshold to 3 — should fire
    cfg = AnalyzerConfig(max_assertions_per_test=3)
    issues_strict = _analyze_source(source, config=cfg)
    tqa004 = [i for i in issues_strict if i.rule_id == "TQA004"]
    assert len(tqa004) == 1


def test_severity_override_changes_issue_severity() -> None:
    """severity_overrides in config changes reported severity."""
    source = textwrap.dedent("""\
        def test_nothing():
            x = 1
    """)
    # Default: TQA001 is CRITICAL
    issues_default = _analyze_source(source)
    tqa001 = [i for i in issues_default if i.rule_id == "TQA001"]
    assert tqa001[0].severity == Severity.CRITICAL

    # Override to WARNING
    cfg = AnalyzerConfig(severity_overrides={"TQA001": Severity.WARNING})
    issues_override = _analyze_source(source, config=cfg)
    tqa001 = [i for i in issues_override if i.rule_id == "TQA001"]
    assert tqa001[0].severity == Severity.WARNING


def test_project_rules_disabled_skips_rule() -> None:
    """project_rules_enabled=False disables specified rule."""
    source = textwrap.dedent("""\
        from fastapi.testclient import TestClient
        from app.main import app

        def test_overrides():
            app.dependency_overrides[lambda: None] = lambda: None
            client = TestClient(app)
            resp = client.get("/")
            assert resp.status_code == 200
    """)
    # Default: STG001 fires
    issues_default = _analyze_source(source)
    stg001 = [i for i in issues_default if i.rule_id == "STG001"]
    assert len(stg001) >= 1

    # Disable STG001
    cfg = AnalyzerConfig(project_rules_enabled={"STG001": False})
    issues_disabled = _analyze_source(source, config=cfg)
    stg001 = [i for i in issues_disabled if i.rule_id == "STG001"]
    assert len(stg001) == 0


def test_sarif_has_partial_fingerprints_and_automation_details() -> None:
    """SARIF output includes partialFingerprints and automationDetails."""
    issues = [
        Issue(
            rule_id="TQA001",
            rule_type="assertions",
            severity=Severity.CRITICAL,
            file="test_x.py",
            line=5,
            message="zero assertions",
            recommendation="add assert",
        )
    ]
    output = SarifReporter().report(issues)
    data = json.loads(output)
    run = data["runs"][0]
    assert "automationDetails" in run
    assert run["automationDetails"]["id"] == "test-quality"
    result = run["results"][0]
    assert "partialFingerprints" in result
    assert "primaryLocationLineHash" in result["partialFingerprints"]


def test_fingerprint_stable_across_line_shifts() -> None:
    """Fingerprint does not change when line number shifts."""
    issue_a = Issue(
        rule_id="TQA001", rule_type="assertions",
        severity=Severity.CRITICAL, file="test.py",
        line=10, message="zero assertions",
        recommendation="add assert",
    )
    issue_b = Issue(
        rule_id="TQA001", rule_type="assertions",
        severity=Severity.CRITICAL, file="test.py",
        line=15, message="zero assertions",
        recommendation="add assert",
    )
    assert issue_a.fingerprint() == issue_b.fingerprint()


# ---------------------------------------------------------------------------
# --explain and --changed CLI modes
# ---------------------------------------------------------------------------


def test_explain_known_rule(capsys) -> None:
    """--explain prints rule explanation and exits 0."""
    code = main(["--explain", "TQA001"])
    assert code == 0
    out = capsys.readouterr().out
    assert "TQA001" in out
    assert "zero assertions" in out.lower()
    assert "Bad:" in out
    assert "Good:" in out


def test_explain_unknown_rule(capsys) -> None:
    """--explain with unknown rule exits 2."""
    code = main(["--explain", "ZZZZZ"])
    assert code == 2


def test_explain_rule_without_detailed_explanation(capsys) -> None:
    """--explain for rule in ALL_RULES but without RULE_EXPLANATIONS still exits 0."""
    code = main(["--explain", "STG003"])
    assert code == 0
    out = capsys.readouterr().out
    assert "STG003" in out


def test_changed_mode_no_crash(tmp_path: Path) -> None:
    """--changed mode with a ref doesn't crash (may find 0 files)."""
    test_file = tmp_path / "test_ok.py"
    test_file.write_text("def test_fine():\n    assert 1 == 1\n")
    # Use a non-existent ref — _get_changed_files will return []
    code = main(["--path", str(tmp_path), "--changed", "HEAD~999"])
    assert code == 0
