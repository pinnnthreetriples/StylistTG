#!/usr/bin/env bash
set -euo pipefail
BRANCH="$1"
git checkout "$BRANCH"
sed -i 's/except TypeError, ValueError:/except (TypeError, ValueError):/g; s/except ZoneInfoNotFoundError, AttributeError:/except (ZoneInfoNotFoundError, AttributeError):/g' \
  backend/app/modules/warmup/adaptive_plan.py \
  backend/app/modules/warmup/channel_state/selector.py \
  backend/app/modules/warmup/cyclic.py \
  backend/app/modules/warmup/typing.py \
  backend/app/modules/warmup/pre_production.py 2>/dev/null || true
npm run generate:api 2>&1 | tail -3
(cd backend && python -m ruff format . 2>&1 | tail -2)
git add -A . ':(exclude)reports-pr427'
if git diff --cached --quiet; then
  echo "no changes on $BRANCH"
  exit 0
fi
git commit -m "Fix CI: Py2 except syntax, ruff format, regen api-client"
git push origin HEAD
