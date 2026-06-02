#!/bin/bash
set -e

cascade() {
  local br=$1
  local upstream=$2
  echo "=== $br onto $upstream ==="
  # Clean working tree + untracked files so cross-branch drift / pop'd
  # stashes do not contaminate the audit regen.
  git reset --hard HEAD >/dev/null 2>&1 || true
  rm -rf backend/app/model_defs/account_onboarding.py \
         backend/app/modules/account_onboarding \
         backend/migrations/versions/20260602_0058_account_onboarding.py \
         backend/tests/api/test_account_onboarding_api.py \
         apps/dashboard/src/features/accounts/accountOnboardingWizard.test.ts \
         apps/dashboard/src/features/accounts/accountOnboardingWizard.ts \
         packages/api-client/src/client/accountOnboarding.ts 2>/dev/null || true
  git checkout "$br" 2>&1 | tail -1
  git reset --hard "origin/$br" >/dev/null 2>&1 || true
  rm -rf backend/app/model_defs/account_onboarding.py \
         backend/app/modules/account_onboarding \
         backend/migrations/versions/20260602_0058_account_onboarding.py \
         backend/tests/api/test_account_onboarding_api.py \
         apps/dashboard/src/features/accounts/accountOnboardingWizard.test.ts \
         apps/dashboard/src/features/accounts/accountOnboardingWizard.ts \
         packages/api-client/src/client/accountOnboarding.ts 2>/dev/null || true
  git rebase "$upstream" 2>&1 | tail -3 || true
  while [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; do
    conflicts=$(git status --porcelain | grep -E '^(UU|AA|DU|UD|UA|AU)' | awk '{print $2}' || true)
    if [ -z "$conflicts" ]; then
      break
    fi
    for f in $conflicts; do
      case "$f" in
        docs/architecture/*)
          git checkout --theirs "$f" 2>&1 | tail -1
          git add "$f"
          ;;
        *)
          git checkout --ours "$f" 2>&1 | tail -1
          git add "$f"
          ;;
      esac
    done
    git rebase --continue 2>&1 | tail -2 || true
  done
  (cd backend && uv run python scripts/structure_audit.py >/dev/null 2>&1) || true
  if ! git diff --quiet docs/architecture/ 2>/dev/null; then
    git add docs/architecture/
    git commit --amend --no-edit >/dev/null 2>&1
  fi
  git push --force-with-lease origin "$br" 2>&1 | tail -1
}

for pair in \
  "issue-263-strict-assertions issue-262-strict-pytest" \
  "issue-264-profile-split issue-263-strict-assertions" \
  "issue-268-db-fixtures issue-264-profile-split" \
  "issue-265-coverage-gates issue-268-db-fixtures" \
  "issue-266-contract-security issue-265-coverage-gates" \
  "issue-269-rbac-matrix issue-266-contract-security" \
  "issue-270-analyzer-ast issue-269-rbac-matrix" \
  "issue-271-flakiness issue-270-analyzer-ast" \
  "issue-267-mutation-allowlist issue-271-flakiness" \
  "issue-272-branch-protection issue-267-mutation-allowlist" \
  "issue-273-docs issue-272-branch-protection" \
  "issue-275-dashboard issue-273-docs"; do
  br=$(echo "$pair" | cut -d' ' -f1)
  upstream=$(echo "$pair" | cut -d' ' -f2)
  cascade "$br" "$upstream"
done
