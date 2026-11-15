"""Dependabot の PR を数えて、自動マージの範囲を見直す材料を出す。

出た本数、自動でマージされた本数、人が触った本数と作業の種類を、更新の種類ごとに数える。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from collections import Counter
from datetime import UTC, datetime, timedelta

from dependabot_merge import DEV, LABEL_AUTO, MINOR, PATCH, parse_updated_dependencies

FIELDS = "number,title,state,createdAt,mergedAt,mergedBy,labels,reviews,commits,headRefName"


def kind_of(pr: dict) -> str:
    """PR を、更新の種類で分ける。"""
    deps: list[dict[str, str]] = []
    for commit in pr["commits"]:
        deps = deps or parse_updated_dependencies(commit["messageBody"])
    if not deps:
        return "不明"
    # セキュリティ更新のメタデータには、種別が書かれない。
    if any("update-type" not in dep for dep in deps):
        return "security"
    types = {dep.get("update-type") for dep in deps}
    if types == {PATCH}:
        return "patch"
    if types <= {PATCH, MINOR}:
        dev_only = all(dep.get("dependency-type") == DEV for dep in deps)
        return "minor（開発用）" if dev_only else "minor"
    return "major"


def is_bot(login: str, bots: set[str]) -> bool:
    return login.endswith("[bot]") or login in bots


def work_of(pr: dict, bots: set[str]) -> str:
    """PR がどう片づいたかを分ける。"""
    human_commits = any(not is_bot(author["login"], bots) for commit in pr["commits"] for author in commit["authors"])
    human_reviews = any(not is_bot(review["author"]["login"], bots) for review in pr["reviews"])
    merged_by_human = bool(pr["mergedBy"]) and not pr["mergedBy"].get("is_bot", False)
    labels = {label["name"] for label in pr["labels"]}
    if pr["state"] == "OPEN":
        return "開いたまま"
    if pr["state"] == "CLOSED":
        return "閉じた"
    if human_commits:
        return "人がファイルを直した"
    if human_reviews or merged_by_human:
        return "人が承認かマージだけした"
    return "自動マージ" if LABEL_AUTO in labels else "人の操作なし"


def bot_logins(prs: list[dict]) -> set[str]:
    """レビューやマージをした bot の名前を集める。レビューの作者名には [bot] が付かないため。"""
    bots = {"dependabot", "github-actions"}
    for pr in prs:
        if pr["mergedBy"] and pr["mergedBy"].get("is_bot"):
            bots.add(pr["mergedBy"]["login"].removeprefix("app/"))
    return bots


def collect(repo: str, days: int, now: datetime) -> list[dict]:
    since = now - timedelta(days=days)
    # 一度に取れる量に上限があるので、新しい順に 40 本までを数える。
    out = subprocess.run(
        ["gh", "pr", "list", "--repo", repo, "--author", "app/dependabot", "--state", "all",
         "--search", f"created:>={since:%Y-%m-%d}", "--limit", "40", "--json", FIELDS],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    return [pr for pr in json.loads(out) if datetime.fromisoformat(pr["createdAt"]) >= since]


def render(prs: list[dict], days: int) -> str:
    works = ["自動マージ", "人が承認かマージだけした", "人がファイルを直した", "人の操作なし", "閉じた", "開いたまま"]
    bots = bot_logins(prs)
    table: dict[str, Counter] = {}
    for pr in prs:
        table.setdefault(kind_of(pr), Counter())[work_of(pr, bots)] += 1
    lines = [
        f"## Dependabot の PR（直近 {days} 日、{len(prs)} 本）",
        "",
        "| 種類 | 出た本数 | " + " | ".join(works) + " |",
        "|---|---:|" + "---:|" * len(works),
    ]
    for kind in sorted(table):
        counts = table[kind]
        lines.append(f"| {kind} | {sum(counts.values())} | " + " | ".join(str(counts[w]) for w in works) + " |")
    total = Counter()
    for counts in table.values():
        total.update(counts)
    lines.append(f"| 合計 | {len(prs)} | " + " | ".join(str(total[w]) for w in works) + " |")
    touched = total["人が承認かマージだけした"] + total["人がファイルを直した"]
    lines += ["", f"人が触った本数は {touched} 本、自動マージは {total['自動マージ']} 本です。"]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    repo = os.environ.get("GITHUB_REPOSITORY") or subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()  # fmt: skip
    print(render(collect(repo, args.days, datetime.now(UTC)), args.days))


if __name__ == "__main__":
    main()
