"""Dependabot 用の Dockerfile のバージョンを上げる Dependabot の PR に、管理場所の変更を積む。

することは「決まった場所の値を、決まった場所に写す」ことだけ。
新しいバージョンを探すこと、cooldown を判断すること、PR を作ることは Dependabot に任せる。

3 つの段に分かれている。鍵を持つのは push だけで、push は PR の中身を取り出さない。

  prepare  対象の PR を 1 本選び、その head を pr/ に取り出して、Dependabot 用の Dockerfile のバージョンを .python-version などへ写す（鍵なし）
  collect  変わったファイルを確かめて集め、次の job に渡す（鍵なし）
  push     渡されたファイルを、App のトークンで PR のブランチにコミットする（鍵あり）

積んだあとの PR はコミットが 2 つになるので、自動マージの対象から外れ、人のレビューに回る。
"""

from __future__ import annotations

import base64
import gzip
import json
import os
import subprocess
import sys
from pathlib import Path

import versions
from dependabot_merge import DEPENDABOT_COMMITTER, app_token, fetch_pull_requests, gh, load_policy

WORKTREE = Path("pr")

# 積んでよいファイル。これ以外が変わっていたら、何もせずに失敗させる。
ALLOWED = frozenset(versions.SOURCES[name] for name in versions.IMAGES)
COMMIT_MESSAGE = (
    "バージョンの管理場所を dependabot/Dockerfile に合わせる\n\n"
    "Dependabot が上げた Dependabot 用の Dockerfile のバージョンを、.python-version などへ写した。"
)


class SyncError(Exception):
    pass


def is_candidate(pr: dict) -> bool:
    """Dependabot が push した、Dependabot 用の Dockerfile だけを変える PR かどうか。"""
    commits = pr["commits"]
    return (
        len(commits) == 1
        and commits[0]["author"] == DEPENDABOT_COMMITTER
        and commits[0]["signed_by_github"]
        and set(pr["head_pushers"]) == {DEPENDABOT_COMMITTER}
        and not pr["files_truncated"]
        and pr["files"] == [versions.SENTINEL]
    )


def changed_files(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=all"],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    return sorted(line[3:] for line in out.splitlines())


def validate_paths(paths: list[str]) -> None:
    extra = sorted(set(paths) - ALLOWED)
    if extra:
        raise SyncError("積んでよいファイル以外が変わっています: " + ", ".join(extra))


def encode(payload: dict) -> str:
    return base64.b64encode(gzip.compress(json.dumps(payload).encode())).decode()


def decode(text: str) -> dict:
    return json.loads(gzip.decompress(base64.b64decode(text)))


def write_output(**values: str) -> None:
    with open(os.environ["GITHUB_OUTPUT"], "a") as output:
        output.writelines(f"{key}={value}\n" for key, value in values.items())


def prepare(repo: str) -> None:
    candidates = [pr for pr in fetch_pull_requests(repo, load_policy()) if is_candidate(pr)]
    if not candidates:
        print("Dependabot 用の Dockerfile だけを変える Dependabot の PR はありません")
        write_output(number="")
        return
    pr = candidates[0]
    subprocess.run(["git", "fetch", "--quiet", "--depth", "1", "origin", pr["head"]], check=True)
    subprocess.run(["git", "worktree", "add", "--quiet", "--detach", str(WORKTREE), pr["head"]], check=True)
    try:
        changed = versions.sync(WORKTREE)
    except versions.VersionError as error:
        report_failure(repo, str(pr["number"]), error)
        raise
    print(f"#{pr['number']}: .python-version などへ写したファイル: {changed or 'なし'}")
    write_output(number=str(pr["number"]) if changed else "", head=pr["head"])


def collect(number: str, head: str) -> None:
    paths = changed_files(WORKTREE)
    validate_paths(paths)
    errors = versions.check(WORKTREE)
    if errors:
        raise SyncError("写したあとも揃っていません: " + " / ".join(errors))
    files = {path: (WORKTREE / path).read_text() for path in paths}
    print(f"#{number}: 積むファイル: {paths}")
    write_output(payload=encode({"number": int(number), "head": head, "files": files}))


def push(repo: str, payload: dict) -> None:
    """渡されたファイルを、PR のブランチにコミットする。PR の中身は取り出さない。"""
    number, head, files = payload["number"], payload["head"], payload["files"]
    validate_paths(list(files))
    if not files:
        raise SyncError("積むファイルがありません")
    # 計算のあとで PR が変わっていないことを、もう一度確かめる。
    current = [pr for pr in fetch_pull_requests(repo, load_policy()) if pr["number"] == number]
    if not current or not is_candidate(current[0]) or current[0]["head"] != head:
        raise SyncError(f"#{number} は、計算したときの状態から変わっています")
    branch = json.loads(gh("api", f"repos/{repo}/pulls/{number}"))["head"]["ref"]

    token = app_token(repo, os.environ["AUTOMERGE_APP_ID"], os.environ["AUTOMERGE_APP_PRIVATE_KEY"])
    commit = create_commit(repo, token, head, files, COMMIT_MESSAGE)
    # force を付けない。ブランチが進んでいたら失敗する。
    app_api(repo, token, f"git/refs/heads/{branch}", {"sha": commit, "force": False}, method="PATCH")
    print(f"#{number}: {commit[:7]} を積みました（{sorted(files)}）")


def app_api(repo: str, token: str, path: str, body: dict, method: str = "POST") -> dict:
    """App のトークンで GitHub の API を呼ぶ。"""
    result = subprocess.run(
        ["gh", "api", "-X", method, f"repos/{repo}/{path}", "--input", "-"],
        input=json.dumps(body), capture_output=True, text=True, check=False,
        env={**os.environ, "GH_TOKEN": token},
    )  # fmt: skip
    if result.returncode != 0:
        raise SyncError(f"{method} {path}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def create_commit(repo: str, token: str, parent: str, files: dict[str, str], message: str) -> str:
    """parent の上に、files の内容のコミットを作る。ブランチは動かさない。"""
    tree = [
        {
            "path": path,
            "mode": "100644",
            "type": "blob",
            "sha": app_api(repo, token, "git/blobs", {"content": content})["sha"],
        }
        for path, content in sorted(files.items())
    ]
    base_tree = json.loads(gh("api", f"repos/{repo}/git/commits/{parent}"))["tree"]["sha"]
    new_tree = app_api(repo, token, "git/trees", {"base_tree": base_tree, "tree": tree})["sha"]
    return app_api(repo, token, "git/commits", {"message": message, "tree": new_tree, "parents": [parent]})["sha"]


def report_failure(repo: str, number: str, error: Exception) -> None:
    """失敗を PR に残す。人が何を直せばよいかを書く。"""
    body = (
        "バージョンの同期に失敗しました。この PR は、Dependabot 用の Dockerfile（`dependabot/Dockerfile`）と管理場所が食い違ったままです。\n\n"
        f"- 理由: {error}\n"
        "- 直し方: この PR のブランチで `uv run just sync` を動かし、結果をコミットしてください。"
        "スクリプトがバージョンの記述を見つけられない場合は、理由に出ているファイルを確かめてください"
    )
    try:
        gh("pr", "comment", number, "--repo", repo, "--body", body)
    except RuntimeError as comment_error:
        print(f"::warning::#{number} にコメントできませんでした: {comment_error}")


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    repo = os.environ["GITHUB_REPOSITORY"]
    number = ""
    try:
        if mode == "prepare":
            prepare(repo)
        elif mode == "collect":
            number = os.environ["PR_NUMBER"]
            collect(number, os.environ["PR_HEAD"])
        elif mode == "push":
            payload = decode(os.environ["PAYLOAD"])
            number = str(payload["number"])
            push(repo, payload)
        else:
            print("usage: version_sync.py [prepare|collect|push]")
            return 2
    except (SyncError, versions.VersionError, RuntimeError) as error:
        print(f"::error::{error}")
        if number:
            report_failure(repo, number, error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
