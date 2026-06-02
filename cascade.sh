#!/bin/bash
set -e
cascade() {
  local br=$1
  local upstream=$2
  echo "=== $br onto $upstream ==="
  git checkout "$br" 2>&1 | tail -1
  git rebase "$upstream" 2>&1 | tail -3 || true
  while [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; do
    local conflicts
    conflicts=$(git status --porcelain | grep -E '^(UU|AA|DU|UD|UA|AU)' | awk '{print $2}' || true)
    if [ -z "$conflicts" ]; then
      break
    fi
    for f in $conflicts; do
      if [[ "$f" == docs/architecture/* || "$f" == "docs/quality/QUALITY_GATES.md" ]]; then
        git checkout --theirs "$f" 2>&1 | tail -1
        git add "$f"
      else
        echo "UNHANDLED CONFLICT in $br: $f"
        return 1
      fi
    done
    git rebase --continue 2>&1 | tail -2 || true
  done
  (cd backend && uv run python scripts/structure_audit.py >/dev/null 2>&1)
  if ! git diff --quiet docs/architecture/; then
    git add docs/architecture/
    git commit --amend --no-edit >/dev/null 2>&1
  fi
  git push --force-with-lease origin "$br" 2>&1 | tail -1
}

for pair in "issue-271-flakiness issue-270-analyzer-ast" \
            "issue-267-mutation-allowlist issue-271-flakiness" \
            "issue-272-branch-protection issue-267-mutation-allowlist" \
            "issue-273-docs issue-272-branch-protection" \
            "issue-275-dashboard issue-273-docs"; do
  br=$(echo "$pair" | cut -d' ' -f1)
  upstream=$(echo "$pair" | cut -d' ' -f2)
  cascade "$br" "$upstream"
done
