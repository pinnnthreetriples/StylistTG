# Regression Policy

Rules for preventing regression bugs in StylistTG.

## Rules

1. **Every production/staging bug is fixed together with a regression test.** The test must reproduce the original failure scenario. The PR must not be merged without it.

2. **Regression test must fail before the fix and pass after.** This is verified by running the test against the pre-fix code. If the test passes before the fix, it does not cover the bug.

3. **If a regression test is impossible, the PR must contain a documented exception.** The exception must explain why the test cannot be written (e.g., requires live external service, hardware-specific, timing-dependent) and what alternative verification was performed.

4. **Flaky tests cannot be ignored without an issue and an owner.** If a test becomes flaky, it must be tracked in a GitHub issue with an assigned owner. `@pytest.mark.skip` or `xfail` must reference the issue URL. Flaky tests left without tracking for more than one sprint must be fixed or replaced.

5. **Deleting a test is allowed only when replaced with equivalent coverage.** If a test is removed because the feature changed, the replacement test must cover the same invariants. The PR description must explain what coverage was removed and what replaced it.
