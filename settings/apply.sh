#!/usr/bin/env bash
# リポジトリの設定と ruleset を、このディレクトリの内容に合わせる。
# 使い方: settings/apply.sh <owner>/<repo>
set -euo pipefail
repo="${1:?usage: settings/apply.sh <owner>/<repo>}"
dir="$(cd "$(dirname "$0")" && pwd)"

gh api -X PATCH "repos/$repo" \
  -F allow_auto_merge=true -F allow_squash_merge=true \
  -F allow_merge_commit=false -F allow_rebase_merge=false \
  -F delete_branch_on_merge=true >/dev/null

# 検査が通った patch の PR を、workflow が承認できるようにする。
gh api -X PUT "repos/$repo/actions/permissions/workflow" \
  -f default_workflow_permissions=read -F can_approve_pull_request_reviews=true

gh api -X PUT "repos/$repo/vulnerability-alerts"
gh api -X PUT "repos/$repo/automated-security-fixes"

id="$(gh api "repos/$repo/rulesets" --jq '.[] | select(.name == "main") | .id')"
if [ -n "$id" ]; then
  gh api -X PUT "repos/$repo/rulesets/$id" --input "$dir/ruleset.json" >/dev/null
else
  gh api -X POST "repos/$repo/rulesets" --input "$dir/ruleset.json" >/dev/null
fi
echo "applied to $repo"
