# Strict Test Quality Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the test and quality gates stricter by fixing contract fuzz regressions, raising mutation confidence, making the analyzer fail closed, and improving frontend coverage.

**Architecture:** Keep PR gates fast and deterministic, while promoting proven nightly signals to hard gates only after their current failures are fixed. Changes stay test-only or validation-only unless a failing test exposes a real API validation bug that must be fixed in request parsing/error handling.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, pytest, pytest-cov, Schemathesis, mutmut, Vitest, React Testing Library, GitHub Actions.

---

## File Structure

- Modify `backend/app/api/account_update.py` and related routers only where invalid UUID strings currently leak into SQLAlchemy queries.
- Modify `backend/app/modules/warmup/router.py` or its service boundary only where invalid UUID path/body inputs currently reach database queries.
- Add focused regression tests under `backend/tests/api/` for malformed UUID request bodies and path params.
- Keep contract fuzz tests in `backend/tests/contract/test_openapi_fuzz.py`.
- Modify `backend/tools/test_analyzer/analyzer.py` so analyzer rule crashes are reported as hard analyzer failures.
- Add analyzer regression tests in `backend/tests/tools/test_test_analyzer.py`.
- Add mutation-killing tests in:
  - `backend/tests/security/test_property_security_helpers.py`
  - `backend/tests/storage/test_storage_layer.py`
  - `backend/tests/domain/test_step_policy.py`
  - `backend/tests/modules/account_editing/test_policies.py`
  - `backend/tests/modules/warmup/test_warmup_legacy_compatibility.py` or a new focused warmup policy test file.
- Add frontend tests in existing nearby `*.test.ts(x)` files under `apps/dashboard/src/`, `packages/ui/src/`, and `packages/api-client/src/`.
- Modify coverage thresholds only after the new tests pass locally.
- Modify `.github/workflows/nightly-test-reliability.yml` only after contract fuzz and mutation signals are stable enough to harden.

---

### Task 1: Fix Contract Fuzz UUID Validation

**Files:**
- Modify: `backend/app/api/account_update.py`
- Modify: `backend/app/modules/warmup/router.py`
- Test: `backend/tests/api/test_contract_uuid_validation.py`

- [ ] **Step 1: Add failing API tests for invalid UUID bodies and paths**

Create `backend/tests/api/test_contract_uuid_validation.py` with focused tests for the failures found in nightly run `26025546638`:

```python
from __future__ import annotations


def test_account_update_preview_rejects_empty_account_id(client) -> None:
    response = client.post(
        "/api/account-update/preview",
        json={"account_id": "", "stories": [{"action": "post_image", "asset_id": "", "protect_content": 0}]},
    )

    assert response.status_code in {400, 422}
    assert "sqlalchemy" not in response.text.lower()


def test_warmup_validate_rejects_empty_account_id(client) -> None:
    response = client.post("/api/warmup/validate", json={"account_id": "", "strategy_id": ""})

    assert response.status_code in {400, 422}
    assert "sqlalchemy" not in response.text.lower()


def test_warmup_session_path_rejects_non_uuid(client) -> None:
    response = client.get("/api/warmup/sessions/0")

    assert response.status_code in {400, 422}
    assert "sqlalchemy" not in response.text.lower()
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
cd backend
python -m pytest tests/api/test_contract_uuid_validation.py -q
```

Expected: at least one test fails with current SQLAlchemy `DataError` or a `500` response.

- [ ] **Step 3: Change request schemas/path params to validate UUID before service calls**

Use `uuid.UUID` or Pydantic UUID types at the FastAPI/schema boundary. Preserve existing response shape where possible. Do not catch broad database exceptions to hide validation bugs.

Example pattern for path params:

```python
from uuid import UUID


@router.get("/sessions/{session_id}")
def get_session(session_id: UUID, ...):
    return service.get_session(str(session_id), ...)
```

Example pattern for request schemas:

```python
from uuid import UUID

from pydantic import BaseModel


class WarmupValidateRequest(BaseModel):
    account_id: UUID
    strategy_id: UUID
```

- [ ] **Step 4: Re-run focused tests**

Run:

```powershell
cd backend
python -m pytest tests/api/test_contract_uuid_validation.py -q
```

Expected: all tests pass and invalid UUIDs return `400` or `422`, not `500`.

- [ ] **Step 5: Re-run contract fuzz locally**

Run:

```powershell
cd backend
python -m pytest tests/contract/ -m contract -q
```

Expected: UUID-related SQLAlchemy `DataError` failures are gone. Any remaining failures should be listed and grouped by root cause before more fixes.

---

### Task 2: Make Contract Fuzz a Candidate Hard Gate

**Files:**
- Modify: `.github/workflows/nightly-test-reliability.yml`
- Modify: `docs/quality/QUALITY_GATES.md`
- Modify: `docs/quality/TEST_STRATEGY.md`

- [ ] **Step 1: Keep the job soft until local contract fuzz is clean**

Do not change the workflow before Task 1 is green.

- [ ] **Step 2: If contract fuzz is clean, remove the soft failure wrapper**

In `.github/workflows/nightly-test-reliability.yml`, change the contract fuzz step from a command that records `returncode` and continues to a normal failing command:

```bash
uv run python -m pytest tests/contract/ -m contract \
  --schemathesis-max-examples=25 \
  --junitxml=reports/schemathesis-nightly-junit.xml \
  | tee reports/schemathesis-nightly.log
```

- [ ] **Step 3: Document hard-gate promotion**

Update docs to say contract fuzz is now hard only after the backlog is fixed.

- [ ] **Step 4: Run validation**

Run:

```powershell
cd backend
python -m pytest tests/contract/ -m contract -q
python scripts/check.py --fast
```

Expected: both pass.

---

### Task 3: Raise Mutation Score on Critical Modules

**Files:**
- Modify tests near the mutated modules:
  - `backend/tests/security/test_property_security_helpers.py`
  - `backend/tests/storage/test_storage_layer.py`
  - `backend/tests/domain/test_step_policy.py`
  - `backend/tests/modules/account_editing/test_policies.py`
  - `backend/tests/modules/warmup/test_warmup_legacy_compatibility.py`

- [ ] **Step 1: Use mutmut report as the backlog**

Download or inspect `mutation-testing-reports/reports/mutmut-results.txt` from nightly run `26025546638`. Start with survived mutants in:

```text
app.services.secret_redaction
app.services.phone_hints
app.storage.paths
app.services.step_policy
```

- [ ] **Step 2: Add redaction tests for survived redaction mutants**

Add assertions that prove exact redaction behavior:

```python
def test_redact_text_masks_multiple_secret_spellings() -> None:
    text = "api_hash=not-a-real-api-hash password: hunter2hunter2 token=abc.def.ghi"

    redacted = redact_text(text)

    assert "not-a-real-api-hash" not in redacted
    assert "hunter2hunter2" not in redacted
    assert "abc.def.ghi" not in redacted
    assert redacted.count("[REDACTED]") >= 3
```

- [ ] **Step 3: Add storage path tests for exact traversal and normalization behavior**

Add assertions that distinguish safe names, traversal, absolute paths, Windows drive paths, and tilde expansion:

```python
def test_normalize_storage_key_rejects_windows_drive_and_tilde() -> None:
    for value in ["C:/Users/user/session", "C:\\Users\\user\\session", "~/session"]:
        with pytest.raises(ValueError):
            normalize_storage_key(value)
```

- [ ] **Step 4: Add step policy tests for hard-stop and partial outcome boundaries**

Add tests for similar-looking errors that must not classify as hard stop:

```python
def test_hard_stop_error_does_not_match_safe_substrings() -> None:
    assert not is_hard_stop_error("not frozen, retry later")
    assert not is_hard_stop_error("phone code accepted after flood warning")
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
cd backend
python -m pytest tests/security/test_property_security_helpers.py tests/storage/test_storage_layer.py tests/domain/test_step_policy.py -q
```

Expected: pass.

- [ ] **Step 6: Run mutation on Linux**

Run on GitHub nightly or WSL/Linux:

```powershell
cd backend
python scripts/check.py --only mutation
```

Expected: mutation score improves from `51%`. First target: `70%+`; next target: `80%+`.

---

### Task 4: Make Analyzer Fail Closed

**Files:**
- Modify: `backend/tools/test_analyzer/analyzer.py`
- Test: `backend/tests/tools/test_test_analyzer.py`

- [ ] **Step 1: Add failing analyzer test for rule crash visibility**

Add a test that injects a broken rule and expects a reported issue:

```python
class BrokenRule(Rule):
    id = "BROKEN001"
    type = "meta"
    default_severity = Severity.CRITICAL

    def check(self, ctx: FileContext, config: AnalyzerConfig) -> list[Issue]:
        raise RuntimeError("broken rule")


def test_analyzer_reports_rule_crashes_as_critical() -> None:
    source = "def test_example():\n    assert 1 == 1\n"
    tree = ast.parse(source)
    ctx_path = Path("tests/test_sample.py")
    analyzer = Analyzer(AnalyzerConfig(), rules=[BrokenRule()])

    issues = analyzer.analyze_file(ctx_path, ctx_path.parent)

    assert [issue.rule_id for issue in issues] == ["META002"]
    assert issues[0].severity == Severity.CRITICAL
    assert "BROKEN001" in issues[0].message
```

- [ ] **Step 2: Implement fail-closed behavior**

In `backend/tools/test_analyzer/analyzer.py`, replace silent `continue` on rule exception with a critical issue:

```python
except Exception as exc:
    all_issues.append(
        Issue(
            rule_id="META002",
            rule_type="analyzer",
            severity=Severity.CRITICAL,
            file=relative_path,
            line=1,
            message=f"Analyzer rule {rule.id} crashed: {type(exc).__name__}: {exc}",
            recommendation="Fix the analyzer rule before trusting this test-quality gate.",
        )
    )
    continue
```

- [ ] **Step 3: Run analyzer tests**

Run:

```powershell
cd backend
python -m pytest tests/tools/test_test_analyzer.py -q
python -m tools.test_analyzer --path tests --coverage reports/coverage.json --severity INFO
```

Expected: tests pass and current suite still reports zero issues.

---

### Task 5: Raise Frontend Coverage With User-Flow Tests

**Files:**
- Modify or add tests under:
  - `apps/dashboard/src/features/auth/`
  - `apps/dashboard/src/features/account-import/`
  - `apps/dashboard/src/modules/warmup/`
  - `apps/dashboard/src/components/dashboard/accountWorkspace/`
  - `packages/ui/src/`

- [ ] **Step 1: Add tests for UI states that currently show 0% coverage**

Start with components listed as 0% in `npm run coverage`, especially:

```text
apps/dashboard/src/app/AppShell.tsx
apps/dashboard/src/components/dashboard/accounts/AccountList.tsx
apps/dashboard/src/components/dashboard/jobs/JobPanels.tsx
apps/dashboard/src/modules/warmup/hooks.ts
packages/ui/src/Dialog.tsx
packages/ui/src/Tabs.tsx
packages/ui/src/Tooltip.tsx
```

- [ ] **Step 2: Prefer behavior tests over snapshot tests**

Example pattern:

```tsx
it("shows disabled action when account is not execution-ready", () => {
  render(<AccountRiskTab summary={blockedSummary} />);

  expect(screen.getByText(/manual intervention/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /start/i })).toBeDisabled();
});
```

- [ ] **Step 3: Run frontend tests and coverage**

Run:

```powershell
npm test -- --force
npm run coverage -- --force
```

Expected: pass and coverage increases materially.

- [ ] **Step 4: Raise thresholds conservatively**

Only after coverage is higher, raise thresholds in:

```text
apps/dashboard/vite.config.ts
packages/api-client/vitest.config.ts
packages/ui/vitest.config.ts
```

Do not set aspirational thresholds that immediately create flaky local development.

---

### Task 6: Final Hardening Validation

**Files:**
- Modify docs only if gate policy changes:
  - `docs/quality/QUALITY_GATES.md`
  - `docs/quality/TEST_STRATEGY.md`
  - `README.md`

- [ ] **Step 1: Run backend gate**

Run:

```powershell
cd backend
python scripts/check.py --fast
python -m pyright app/api app/services app/schemas.py app/config.py app/workers
```

Expected: pass.

- [ ] **Step 2: Run frontend gate**

Run:

```powershell
npm test -- --force
npm run coverage -- --force
npm run build -- --force
npm run check:api
```

Expected: pass.

- [ ] **Step 3: Run repo-level checks**

Run:

```powershell
npm run memory:check
git diff --check
```

Expected: no new errors. Existing unrelated memory warnings may be reported separately.

- [ ] **Step 4: Trigger GitHub nightly**

Run:

```powershell
gh workflow run "Nightly Test Reliability" --ref main
gh run watch <run-id> --interval 20 --exit-status
```

Expected: all jobs pass; contract fuzz should be hard only if Task 2 was completed; mutation should at least report improved score and artifacts.

---

## Promotion Policy

- Contract fuzz becomes hard only after its current failure backlog is fixed.
- Mutation remains soft until score is consistently `70%+`; promote to hard minimum at `70%`, then raise toward `80%`.
- Flaky detection remains success-with-warning until a tracking process exists; then rerun-only tests should require an issue link.
- Frontend coverage thresholds should rise only after real behavior tests are added.
- Live TDLib/Telegram/S3 must stay out of PR/nightly CI unless a separate explicitly approved live workflow is created.

## Self-Review

- Spec coverage: plan covers contract fuzz, mutation score, analyzer strictness, frontend coverage, validation, and gate promotion.
- Placeholder scan: no implementation step depends on "TBD" or unspecified work.
- Type consistency: UUID validation uses `uuid.UUID` at FastAPI/Pydantic boundaries and passes `str(uuid)` into existing service APIs where needed.
