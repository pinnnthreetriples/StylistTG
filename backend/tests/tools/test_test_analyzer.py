"""Unit tests for tools.test_analyzer package."""

# test-analyzer: disable-file=STG001 reason="test samples intentionally contain dependency_overrides patterns"
# test-analyzer: disable-file=STG002 reason="test samples intentionally contain TestClient(app) + dependency_overrides patterns"
# test-analyzer: disable-file=STG003 reason="test samples intentionally contain 4xx-without-body snippets for rule verification"
# test-analyzer: disable-file=TQA020 reason="test samples intentionally contain Mock() literal strings for rule verification"
# test-analyzer: disable-file=STG006 reason="test samples intentionally contain Stubber literal strings for rule verification"
# test-analyzer: disable-file=META001 reason="test fixture literal contains disable=RULE without reason= to verify META001 rule fires"
# test-analyzer: disable-file=META003 reason="test fixture literals contain expired/malformed expires= dates to verify META003 rule fires"
# test-analyzer: disable-file=TQA030 reason="rule-verification tests share textwrap.dedent(...) + _analyze_source(...) pattern by design"
from __future__ import annotations

import json
import tempfile
import textwrap
from pathlib import Path

import pytest

from tools.test_analyzer import cli as analyzer_cli
from tools.test_analyzer import (
    Analyzer,
    AnalyzerConfig,
    FileContext,
    Issue,
    JsonReporter,
    Rule,
    SarifReporter,
    Severity,
    filter_by_baseline,
    load_baseline,
    main,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _analyze_source(
    source: str,
    config: AnalyzerConfig | None = None,
    relative_path: str = "test_sample.py",
) -> list[Issue]:
    """Analyze a source string and return issues."""
    cfg = config or AnalyzerConfig()
    analyzer = Analyzer(cfg)

    with tempfile.TemporaryDirectory() as tmp:
        base_dir = Path(tmp)
        path = base_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        issues = analyzer.analyze_file(path, base_dir)

    return issues


class BrokenRule(Rule):
    id = "BROKEN001"
    type = "meta"
    default_severity = Severity.CRITICAL

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        raise RuntimeError("broken rule")


def test_analyzer_reports_rule_crashes_as_critical(tmp_path: Path) -> None:
    test_file = tmp_path / "test_sample.py"
    test_file.write_text("def test_example():\n    assert 1 == 1\n", encoding="utf-8")
    analyzer = Analyzer(AnalyzerConfig(), rules=[BrokenRule()])

    issues = analyzer.analyze_file(test_file, tmp_path)

    assert [issue.rule_id for issue in issues] == ["META002"]
    assert issues[0].severity == Severity.CRITICAL
    assert "BROKEN001" in issues[0].message


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
# TQA007: pytest.raises without match= in focused tests
# ---------------------------------------------------------------------------


def test_tqa007_pytest_raises_without_match_in_security_path() -> None:
    source = textwrap.dedent("""\
        import pytest

        def test_rejects_bad_token():
            with pytest.raises(ValueError):
                validate_token("bad")
    """)
    issues = _analyze_source(source, relative_path="tests/security/test_tokens.py")
    rule_ids = [i.rule_id for i in issues]
    assert "TQA007" in rule_ids


def test_tqa007_pytest_raises_with_match_no_issue() -> None:
    source = textwrap.dedent("""\
        import pytest

        def test_rejects_bad_token():
            with pytest.raises(ValueError, match="invalid token"):
                validate_token("bad")
    """)
    issues = _analyze_source(source, relative_path="tests/security/test_tokens.py")
    tqa007 = [i for i in issues if i.rule_id == "TQA007"]
    assert tqa007 == []


def test_tqa007_pytest_raises_without_match_outside_focused_tests_no_issue() -> None:
    source = textwrap.dedent("""\
        import pytest

        def test_legacy_error():
            with pytest.raises(ValueError):
                parse_legacy_value("bad")
    """)
    issues = _analyze_source(source, relative_path="tests/integration/test_legacy.py")
    tqa007 = [i for i in issues if i.rule_id == "TQA007"]
    assert tqa007 == []


def test_tqa007_pytest_raises_without_match_with_security_marker() -> None:
    source = textwrap.dedent("""\
        import pytest

        @pytest.mark.security
        def test_rejects_bad_token():
            with pytest.raises(ValueError):
                validate_token("bad")
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "TQA007" in rule_ids


def test_tqa007_pytest_raises_without_match_with_unit_marker() -> None:
    source = textwrap.dedent("""\
        import pytest

        @pytest.mark.unit
        def test_rejects_bad_token():
            with pytest.raises(ValueError):
                validate_token("bad")
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "TQA007" in rule_ids


def test_tqa007_pytest_raises_without_match_with_module_unit_pytestmark() -> None:
    source = textwrap.dedent("""\
        import pytest

        pytestmark = pytest.mark.unit

        def test_rejects_bad_token():
            with pytest.raises(ValueError):
                validate_token("bad")
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "TQA007" in rule_ids


def test_tqa007_pytest_raises_without_match_with_module_security_pytestmark() -> None:
    source = textwrap.dedent("""\
        import pytest

        pytestmark = pytest.mark.security

        def test_rejects_bad_token():
            with pytest.raises(ValueError):
                validate_token("bad")
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "TQA007" in rule_ids


def test_tqa007_pytest_raises_without_match_with_module_security_pytestmark_list() -> None:
    source = textwrap.dedent("""\
        import pytest

        pytestmark = [pytest.mark.slow, pytest.mark.security]

        def test_rejects_bad_token():
            with pytest.raises(ValueError):
                validate_token("bad")
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "TQA007" in rule_ids


def test_tqa007_pytest_raises_without_match_with_module_unit_pytestmark_tuple() -> None:
    source = textwrap.dedent("""\
        import pytest

        pytestmark = (pytest.mark.unit, pytest.mark.slow)

        def test_rejects_bad_token():
            with pytest.raises(ValueError):
                validate_token("bad")
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "TQA007" in rule_ids


def test_tqa007_pytest_raises_without_match_with_class_unit_marker() -> None:
    source = textwrap.dedent("""\
        import pytest

        @pytest.mark.unit
        class TestTokens:
            def test_rejects_bad_token(self):
                with pytest.raises(ValueError):
                    validate_token("bad")
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "TQA007" in rule_ids


def test_tqa007_pytest_raises_without_match_with_class_security_marker() -> None:
    source = textwrap.dedent("""\
        import pytest

        @pytest.mark.security
        class TestTokens:
            def test_rejects_bad_token(self):
                with pytest.raises(ValueError):
                    validate_token("bad")
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "TQA007" in rule_ids


def test_tqa007_pytest_raises_with_match_in_module_scope_no_issue() -> None:
    source = textwrap.dedent("""\
        import pytest

        pytestmark = pytest.mark.security

        def test_rejects_bad_token():
            with pytest.raises(ValueError, match="invalid token"):
                validate_token("bad")
    """)
    issues = _analyze_source(source)
    tqa007 = [i for i in issues if i.rule_id == "TQA007"]
    assert tqa007 == []


def test_tqa007_pytest_raises_with_match_in_class_scope_no_issue() -> None:
    source = textwrap.dedent("""\
        import pytest

        @pytest.mark.security
        class TestTokens:
            def test_rejects_bad_token(self):
                with pytest.raises(ValueError, match="invalid token"):
                    validate_token("bad")
    """)
    issues = _analyze_source(source)
    tqa007 = [i for i in issues if i.rule_id == "TQA007"]
    assert tqa007 == []


# ---------------------------------------------------------------------------
# TQA008: broad/bare except
# ---------------------------------------------------------------------------


def test_tqa008_bare_except() -> None:
    source = textwrap.dedent("""\
        def test_fallback():
            try:
                load_config()
            except:
                result = "fallback"
            assert result == "fallback"
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "TQA008" in rule_ids


def test_tqa008_broad_exception_except() -> None:
    source = textwrap.dedent("""\
        def test_fallback():
            try:
                load_config()
            except Exception:
                result = "fallback"
            assert result == "fallback"
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "TQA008" in rule_ids


def test_tqa008_specific_except_no_issue() -> None:
    source = textwrap.dedent("""\
        def test_fallback():
            try:
                load_config()
            except ValueError:
                result = "fallback"
            assert result == "fallback"
    """)
    issues = _analyze_source(source)
    tqa008 = [i for i in issues if i.rule_id == "TQA008"]
    assert tqa008 == []


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
# STG003: 4xx status assertions need error body checks
# ---------------------------------------------------------------------------


def test_stg003_status_code_with_diagnostic_text_message_still_flags() -> None:
    source = textwrap.dedent("""\
        def test_unauthorized():
            response = client.patch("/settings")
            assert response.status_code == 401, response.text
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "STG003" in rule_ids


def test_stg003_status_code_with_json_detail_no_issue() -> None:
    source = textwrap.dedent("""\
        def test_unauthorized():
            response = client.patch("/settings")
            assert response.status_code == 401
            assert response.json() == {"detail": "operator token is required"}
    """)
    issues = _analyze_source(source)
    stg003 = [i for i in issues if i.rule_id == "STG003"]
    assert stg003 == []


# ---------------------------------------------------------------------------
# STG004: ambiguous status code
# ---------------------------------------------------------------------------


def test_stg004_status_code_tuple_without_contract() -> None:
    source = textwrap.dedent("""\
        def test_create_or_conflict():
            response = client.post("/items")
            assert response.status_code in (201, 409)
    """)
    issues = _analyze_source(source)
    rule_ids = [i.rule_id for i in issues]
    assert "STG004" in rule_ids


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


def test_suppression_with_future_expiry_does_not_emit_meta003() -> None:
    """A suppression with a non-expired `expires=` value passes the gate."""
    source = textwrap.dedent("""\
        # test-analyzer: disable=TQA001 reason="placeholder" issue="#999" expires="2099-12-31"
        def test_smoke():
            run_app()
    """)
    issues = _analyze_source(source)
    assert [i for i in issues if i.rule_id == "META003"] == []


def test_suppression_with_past_expiry_emits_meta003_critical() -> None:
    """An expired suppression fires META003 with CRITICAL severity."""
    source = textwrap.dedent("""\
        # test-analyzer: disable=TQA001 reason="placeholder" issue="#999" expires="2020-01-01"
        def test_smoke():
            run_app()
    """)
    issues = _analyze_source(source)
    meta = [i for i in issues if i.rule_id == "META003"]
    assert len(meta) == 1
    assert "expired on 2020-01-01" in meta[0].message
    assert meta[0].severity.name == "CRITICAL"


def test_suppression_with_malformed_expiry_emits_meta003() -> None:
    source = textwrap.dedent("""\
        # test-analyzer: disable=TQA001 reason="placeholder" expires="not-a-date"
        def test_smoke():
            run_app()
    """)
    # Regex requires \\d{4}-\\d{2}-\\d{2}, so a non-matching value is silently
    # dropped — but a structurally-valid-but-impossible date (e.g. month 99)
    # exercises the date.fromisoformat ValueError path inside the parser.
    issues = _analyze_source(source)
    assert [i for i in issues if i.rule_id == "META003"] == []

    source_bad = textwrap.dedent("""\
        # test-analyzer: disable=TQA001 reason="placeholder" expires="2026-99-99"
        def test_smoke():
            run_app()
    """)
    issues_bad = _analyze_source(source_bad)
    meta = [i for i in issues_bad if i.rule_id == "META003"]
    assert len(meta) == 1
    assert "malformed" in meta[0].message


# ---------------------------------------------------------------------------
# CLI exit codes
# ---------------------------------------------------------------------------


def test_cli_exit_code_0_no_critical(tmp_path: Path) -> None:
    test_file = tmp_path / "test_ok.py"
    test_file.write_text("def test_fine():\n    assert len([1, 2]) == 2\n")
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
    issues = analyzer.coverage_branch_warnings()
    assert len(issues) == 1
    assert issues[0].rule_id == "TQA040"
    assert issues[0].file == "app/services/auth.py"
    assert "6 of 20 branches" in issues[0].message


def test_cli_coverage_flag_accepted(tmp_path: Path) -> None:
    """CLI --coverage flag is parsed and does not crash."""
    test_file = tmp_path / "test_ok.py"
    test_file.write_text("def test_fine():\n    assert len([1, 2]) == 2\n")
    coverage_file = tmp_path / "coverage.json"
    coverage_file.write_text(
        json.dumps(
            {"files": {"app/example.py": {"summary": {"num_branches": 4, "covered_branches": 4}}}}
        )
    )
    code = main(
        [
            "--path",
            str(test_file),
            "--coverage",
            str(coverage_file),
        ]
    )
    assert code == 0


def test_cli_coverage_does_not_fail_on_source_branch_hints(tmp_path: Path) -> None:
    test_file = tmp_path / "test_ok.py"
    test_file.write_text("def test_fine():\n    assert len([1, 2]) == 2\n")
    coverage_file = tmp_path / "coverage.json"
    coverage_file.write_text(
        json.dumps(
            {"files": {"app/example.py": {"summary": {"num_branches": 8, "covered_branches": 2}}}}
        )
    )
    code = main(
        [
            "--path",
            str(test_file),
            "--coverage",
            str(coverage_file),
            "--severity",
            "INFO",
        ]
    )
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
        rule_id="TQA001",
        rule_type="assertions",
        severity=Severity.CRITICAL,
        file="test.py",
        line=10,
        message="zero assertions",
        recommendation="add assert",
    )
    issue_b = Issue(
        rule_id="TQA001",
        rule_type="assertions",
        severity=Severity.CRITICAL,
        file="test.py",
        line=15,
        message="zero assertions",
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


def test_changed_mode_fails_when_ref_cannot_be_resolved(tmp_path: Path) -> None:
    """--changed mode fails closed when git cannot resolve the base ref."""
    test_file = tmp_path / "test_ok.py"
    test_file.write_text("def test_fine():\n    assert 1 == 1\n")

    code = main(
        [
            "--path",
            str(tmp_path),
            "--changed",
            "refs/remotes/origin/__missing_changed_test_base__",
        ]
    )
    assert code == 2


def test_changed_mode_analyzes_changed_test_file(
    tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
) -> None:
    """--changed mode finds and analyzes changed test files (positive case)."""
    test_file = tmp_path / "test_bad.py"
    test_file.write_text("def test_nothing():\n    x = 1\n")

    monkeypatch.setattr(
        "tools.test_analyzer.cli._get_changed_files",
        lambda ref: [test_file],
    )

    code = main(["--path", str(tmp_path), "--changed", "origin/main"])
    assert code == 1  # TQA001 (zero assertions) is CRITICAL


def test_changed_file_paths_strip_current_directory_prefix(
    tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
) -> None:
    """Git reports repo-root paths even when CI runs from backend/."""

    backend = tmp_path / "backend"
    test_file = backend / "tests" / "test_changed.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("def test_fine():\n    assert True\n", encoding="utf-8")

    class Result:
        stdout = "backend/tests/test_changed.py\n"

    monkeypatch.chdir(backend)
    monkeypatch.setattr(
        "tools.test_analyzer.cli.subprocess.run",
        lambda *args, **kwargs: Result(),
    )

    assert analyzer_cli._get_changed_files("origin/main") == [Path("tests/test_changed.py")]
