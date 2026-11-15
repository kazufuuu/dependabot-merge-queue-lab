#!/usr/bin/env python3
"""所有者のレビューを求める ruleset を 2 つ作って、JSON で出す。

使い方: .github/settings/owner_rulesets.py <owner>/<repo> <出力先のディレクトリ>

すべてのファイルに、team のレビューを求める。求め方を、ファイルで 2 つに分ける。

- owners-lockfiles: ロックファイルを変える PR に求める。自動マージの App だけを対象から外す
- owners-others: ロックファイル以外を変える PR に求める。対象から外す主体はいない

App が所有者のレビューなしで通せるのは、ロックファイルだけを変える PR に限られる。
ロックファイルの名前、team、App は、.github/scripts/policy.json から読む。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

POLICY = Path(__file__).resolve().parent.parent / "scripts" / "policy.json"


def gh_id(path: str) -> int | None:
    """ID を返す。見つからなければ None。"""
    result = subprocess.run(["gh", "api", path, "--jq", ".id"], capture_output=True, text=True, check=False)
    return int(result.stdout) if result.returncode == 0 else None


def ruleset(name: str, team_id: int, patterns: list[str], exempt_app: int | None) -> dict:
    actors = [{"actor_id": exempt_app, "actor_type": "Integration", "bypass_mode": "exempt"}] if exempt_app else []
    return {
        "name": name,
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": actors,
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": [
            {
                "type": "pull_request",
                "parameters": {
                    "required_approving_review_count": 0,
                    "require_code_owner_review": False,
                    "require_last_push_approval": False,
                    "dismiss_stale_reviews_on_push": False,
                    "required_review_thread_resolution": False,
                    "allowed_merge_methods": ["squash"],
                    "required_reviewers": [
                        {
                            "minimum_approvals": 1,
                            "file_patterns": patterns,
                            "reviewer": {"id": team_id, "type": "Team"},
                        }
                    ],
                },
            }
        ],
    }


def lockfile_patterns(names: list[str]) -> list[str]:
    """リポジトリの直下と、その下のどのディレクトリにあっても当てはまる形にする。"""
    return [pattern for name in names for pattern in (name, f"**/{name}")]


def main() -> int:
    repo, out = sys.argv[1], Path(sys.argv[2])
    policy = json.loads(POLICY.read_text())
    owner = repo.split("/")[0]
    team_id = gh_id(f"orgs/{owner}/teams/{policy['review_team']}")
    if team_id is None:
        print(f"team {policy['review_team']} が見つかりません", file=sys.stderr)
        return 1
    app = policy["app"]
    app_id = gh_id(f"apps/{app}")
    if app_id is None:
        # App を作る前でも、保護は先に入れる。作ったあとで、もう一度動かす。
        print(f"App {app} がまだありません。対象から外す主体なしで作ります", file=sys.stderr)
    locks = lockfile_patterns(policy["lockfiles"])
    files = {
        "ruleset-owners-lockfiles.json": ruleset("owners-lockfiles", team_id, locks, app_id),
        "ruleset-owners-others.json": ruleset("owners-others", team_id, ["**/*"] + ["!" + p for p in locks], None),
    }
    for name, body in files.items():
        (out / name).write_text(json.dumps(body, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
