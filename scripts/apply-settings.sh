#!/usr/bin/env bash
# リポジトリ設定と ruleset を反映する
set -euo pipefail
repo="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
cd "$(git rev-parse --show-toplevel)"

gh api -X PATCH "repos/$repo" --input settings/repo.json >/dev/null
gh api -X PUT "repos/$repo/vulnerability-alerts"
gh api -X PUT "repos/$repo/automated-security-fixes"
gh api -X PUT "repos/$repo/actions/permissions/workflow" \
  -f default_workflow_permissions=read -F can_approve_pull_request_reviews=true

id="$(gh api "repos/$repo/rulesets" --jq '.[] | select(.name == "protect-main") | .id')"
if [ -n "$id" ]; then
  gh api -X PUT "repos/$repo/rulesets/$id" --input settings/ruleset.json >/dev/null
else
  gh api -X POST "repos/$repo/rulesets" --input settings/ruleset.json >/dev/null
fi
echo "applied -> $repo"
