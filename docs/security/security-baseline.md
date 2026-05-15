# Security Baseline

## Enabled Checks

- CI: backend, frontend, OpenAPI, Docker build, dependency audit, and tests.
- Test Quality: backend lint/format, coverage, test analyzer, pip-audit, soft
  Pyright/Schemathesis, and duplicate detection.
- Semgrep: static analysis with repository custom rules.
- CodeQL: Python and JavaScript/TypeScript code scanning.
- Secret Scan: Gitleaks with redacted output.
- SBOM: Syft SPDX JSON artifacts for backend, frontend/root workspace, and the
  backend container image.
- Container Scan: Trivy scan of the backend Docker image.

## Merge Blocking

CI, Test Quality hard gates, Semgrep, CodeQL failures, Secret Scan findings, and
Trivy CRITICAL image vulnerabilities should block merge. SBOM generation is an
artifact gate: generation failures block merge, but SBOM contents are triaged
separately unless another scanner flags a blocking issue.

Trivy HIGH findings are reported for triage but do not block during this
baseline phase. Promote HIGH to blocking only after the backlog is reviewed.

## Triage

1. Confirm the finding is in code or dependencies reachable by this repository.
2. Check whether it affects local-only tooling, test fixtures, or production
   runtime.
3. Fix by upgrading, removing, or isolating the dependency or code path.
4. Link the finding and remediation in the PR.
5. If a finding is accepted temporarily, document owner, expiry, and mitigation.

## Secret Handling

If a secret is leaked:

1. Revoke or rotate it immediately in the source system.
2. Remove it from code, logs, artifacts, and docs.
3. Re-run Gitleaks with redaction.
4. Treat historical exposure as compromised even if the repo is private.

Allowlist only stable test fixtures or placeholders that cannot authenticate to
real systems. Keep allowlists narrow by regex or path and include a comment.
Never allowlist real-looking cloud, Telegram, database, Redis, Supabase, or API
credentials.

## False Positives

Prefer changing fixture text to obviously fake values over allowlisting. If an
allowlist is required, include a short reason in `.gitleaks.toml` and keep it
specific enough that a real secret nearby would still be detected.

## Branch Protection Recommendation

Require these checks on `main` when GitHub branch protection is available:

- CI
- Test Quality
- Semgrep
- CodeQL
- Secret Scan
- SBOM
- Container Scan

This repository does not encode branch protection settings in code.

