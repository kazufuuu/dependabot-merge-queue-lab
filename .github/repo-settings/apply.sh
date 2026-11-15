#!/usr/bin/env bash
# リポジトリの設定と ruleset を、このディレクトリの内容に合わせる。
# 使い方: .github/repo-settings/apply.sh <owner>/<repo>
set -euo pipefail
repo="${1:?usage: .github/repo-settings/apply.sh <owner>/<repo>}"
dir="$(cd "$(dirname "$0")" && pwd)"

gh api -X PATCH "repos/$repo" \
  -F allow_auto_merge=true -F allow_squash_merge=true \
  -F allow_merge_commit=false -F allow_rebase_merge=false \
  -F delete_branch_on_merge=true >/dev/null

# 承認は専用の GitHub App が行う。workflow の GITHUB_TOKEN には承認させない。
gh api -X PUT "repos/$repo/actions/permissions/workflow" \
  -f default_workflow_permissions=read -F can_approve_pull_request_reviews=false

# App の鍵は、main だけが使える environment に置く。
gh api -X PUT "repos/$repo/environments/automerge" --input - >/dev/null <<'JSON'
{"deployment_branch_policy": {"protected_branches": false, "custom_branch_policies": true}}
JSON
if ! gh api "repos/$repo/environments/automerge/deployment-branch-policies" \
  --jq '.branch_policies[].name' | grep -qx main; then
  gh api -X POST "repos/$repo/environments/automerge/deployment-branch-policies" \
    -f name=main -f type=branch >/dev/null
fi

gh api -X PUT "repos/$repo/vulnerability-alerts"
gh api -X PUT "repos/$repo/automated-security-fixes"

# main の保護と、タグの保護。タグは管理者だけが作れる。
# 所有者のレビューを求める ruleset は、team と App の ID が要るので、その場で作る。
generated="$(mktemp -d)"
trap 'rm -rf "$generated"' EXIT
python3 "$dir/owner_rulesets.py" "$repo" "$generated"
for file in "$dir/ruleset.json" "$dir/ruleset-tags.json" "$generated"/ruleset-owners-*.json; do
  name="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["name"])' "$file")"
  id="$(gh api "repos/$repo/rulesets" --jq ".[] | select(.name == \"$name\") | .id")"
  if [ -n "$id" ]; then
    gh api -X PUT "repos/$repo/rulesets/$id" --input "$file" >/dev/null
  else
    gh api -X POST "repos/$repo/rulesets" --input "$file" >/dev/null
  fi
done
# レビューの依頼を、team の中の決めた人数に割り振る。人数は .github/scripts/policy.json の review_count。
team="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["review_team"])' "$dir/../scripts/policy.json")"
count="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["review_count"])' "$dir/../scripts/policy.json")"
team_id="$(gh api graphql -f query='query($org: String!, $team: String!) { organization(login: $org) { team(slug: $team) { id } } }' \
  -f org="${repo%%/*}" -f team="$team" --jq '.data.organization.team.id')"
gh api graphql -f query='mutation($id: ID!, $count: Int!) {
  updateTeamReviewAssignment(input: {id: $id, enabled: true, algorithm: LOAD_BALANCE, teamMemberCount: $count, notifyTeam: false}) {
    team { reviewRequestDelegationMemberCount }
  }
}' -f id="$team_id" -F count="$count" >/dev/null

echo "applied to $repo"
