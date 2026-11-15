"""Dependabot の PR が、同時に開ける上限に近づいたら、Issue で知らせる。

上限（open-pull-requests-limit）は、.github/dependabot.yml の設定ごとに数える。
開いている PR が上限に達すると、Dependabot は新しい PR を作らない。エラーも出ない。
人の判断待ちの PR で埋まると、patch の PR も出なくなり、自動マージが止まる。

知らせは Issue 1 件にまとめる。近づいた設定が無くなったら、その Issue を閉じる。
セキュリティアップデートの PR は別枠だが、ブランチの名前では見分けられないので、一緒に数える。
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from dependabot_merge import gh

CONFIG = Path(__file__).resolve().parent.parent / ".github" / "dependabot.yml"
TITLE = "Dependabot の PR が上限に近づいています"
DEFAULT_LIMIT = 5
# 残りがこの本数以下になったら知らせる。
MARGIN = 2
# 設定の名前と、ブランチに使われる名前が違うもの。
BRANCH_NAMES = {"npm": "npm_and_yarn", "github-actions": "github_actions"}


def read_entries(text: str) -> list[dict]:
    """設定ごとの、エコシステム、ディレクトリ、上限を読む。"""
    entries: list[dict] = []
    for block in re.split(r"^  - package-ecosystem:", text, flags=re.MULTILINE)[1:]:
        ecosystem = block.splitlines()[0].strip().strip("\"'")
        directory = re.search(r"^    directory:\s*(\S+)", block, re.MULTILINE)
        limit = re.search(r"^    open-pull-requests-limit:\s*(\d+)", block, re.MULTILINE)
        entries.append(
            {
                "ecosystem": ecosystem,
                "directory": directory.group(1).strip("\"'") if directory else "/",
                "limit": int(limit.group(1)) if limit else DEFAULT_LIMIT,
            }
        )
    return entries


def branch_prefix(entry: dict) -> str:
    name = BRANCH_NAMES.get(entry["ecosystem"], entry["ecosystem"])
    return f"dependabot/{name}{entry['directory'].rstrip('/')}/"


def count_open(entries: list[dict], branches: list[str]) -> list[int]:
    """設定ごとの、開いている PR の本数を返す。ブランチは、いちばん長く一致する設定に数える。"""
    counts = [0] * len(entries)
    prefixes = [branch_prefix(entry) for entry in entries]
    for branch in branches:
        matches = [index for index, prefix in enumerate(prefixes) if branch.startswith(prefix)]
        if matches:
            counts[max(matches, key=lambda index: len(prefixes[index]))] += 1
    return counts


def near_limit(entries: list[dict], counts: list[int], margin: int = MARGIN) -> list[tuple[dict, int]]:
    return [(entry, count) for entry, count in zip(entries, counts, strict=True) if entry["limit"] - count <= margin]


def issue_body(near: list[tuple[dict, int]]) -> str:
    rows = "\n".join(
        f"| {entry['ecosystem']} | `{entry['directory']}` | {count} | {entry['limit']} |" for entry, count in near
    )
    return (
        "Dependabot の PR が、同時に開ける上限に近づいています。\n"
        "上限に達すると、新しい PR が作られなくなります。patch の PR も出なくなり、自動マージが止まります。エラーは出ません。\n\n"
        "| エコシステム | ディレクトリ | 開いている PR | 上限 |\n|---|---|---|---|\n"
        f"{rows}\n\n"
        "直し方: 人の判断待ちの PR（`needs-review` ラベル）を、マージするか閉じてください。\n"
        "本数が減ると、この Issue は自動で閉じます。"
    )


def main() -> int:
    repo = os.environ["GITHUB_REPOSITORY"]
    entries = read_entries(CONFIG.read_text())
    out = gh("pr", "list", "--repo", repo, "--author", "app/dependabot", "--state", "open",
             "--limit", "300", "--json", "headRefName")  # fmt: skip
    counts = count_open(entries, [pr["headRefName"] for pr in json.loads(out)])
    for entry, count in zip(entries, counts, strict=True):
        print(f"{entry['ecosystem']} {entry['directory']}: 開いている PR {count} 本、上限 {entry['limit']} 本")
    near = near_limit(entries, counts)

    found = json.loads(gh("issue", "list", "--repo", repo, "--state", "open", "--search", f'in:title "{TITLE}"',
                          "--json", "number,title,body"))  # fmt: skip
    issues = [issue for issue in found if issue["title"] == TITLE]
    if not near:
        for issue in issues:
            gh("issue", "close", str(issue["number"]), "--repo", repo, "--comment", "上限に近い設定が無くなりました。")
        return 0
    body = issue_body(near)
    print("::warning::" + TITLE)
    if not issues:
        gh("issue", "create", "--repo", repo, "--title", TITLE, "--body", body)
    elif issues[0]["body"].strip() != body.strip():
        gh("issue", "edit", str(issues[0]["number"]), "--repo", repo, "--body", body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
