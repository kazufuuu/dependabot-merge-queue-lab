"""Python と Node のセキュリティの修正を含むバージョンを見つけ、待たずに PR を出す。

コンテナのイメージには、Dependabot のセキュリティ更新が無い。Dependabot は、公式イメージの
新しいバージョンを、通常の更新として、cooldown のあとに出す。セキュリティの修正を含むバージョンだけは、
この処理が、待たずに見張り役と正本を上げる PR を出す。

見分け方は、公開されている情報を機械的に読むだけ。

- Node: https://nodejs.org/dist/index.json の、バージョンごとの security の値
- Python: 今のバージョンに効く脆弱性を OSV（https://osv.dev）に聞き、その修正のコミットが
  新しいバージョンに入っているかを、GitHub の python/cpython で確かめる

uv は PyPI のパッケージなので、Dependabot のセキュリティ更新が届く。ここでは扱わない。

2 つの段に分かれている。鍵を持つのは open だけで、open は main のファイルしか読まない。

  find  上げるバージョンを決める（鍵なし）。公式イメージがまだ公開されていないバージョンは、次の回に回す
  open  渡されたバージョンごとに、main のファイルを書き換えたブランチと PR を作る（鍵あり）。Python と Node は別の PR

PR は App が出すので、自動マージの対象にならない。所有者のレビューが要る。
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import versions
from dependabot_merge import app_token, gh
from version_sync import SyncError, app_api, create_commit, decode, encode, write_output

NODE_INDEX = "https://nodejs.org/dist/index.json"
OSV_QUERY = "https://api.osv.dev/v1/query"
CPYTHON = "python/cpython"
CPYTHON_URL = f"https://github.com/{CPYTHON}"
HUB_TAG = "https://hub.docker.com/v2/repositories/{repository}/tags/{tag}"

BRANCH_PREFIX = "security-release/"
LABELS = ("dependencies", "needs-review")
NAMES = ("python", "node")
# 見張り役に -slim の付いたタグで書くイメージ。
SLIM = ("python", "node")
PLAIN = re.compile(r"\d+\.\d+\.\d+")
ADVISORY = re.compile(r"[A-Za-z0-9-]{1,40}")

Version = tuple[int, int, int]


def parse(version: str) -> Version:
    if not PLAIN.fullmatch(version):
        raise ValueError(f"バージョンの形が違います: {version}")
    major, minor, patch = (int(part) for part in version.split("."))
    return major, minor, patch


def show(version: Version) -> str:
    return ".".join(str(part) for part in version)


def fetch_json(url: str, body: dict | None = None) -> object:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"User-Agent": "security-release-check", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


# ここから、バージョンを決める処理。外から取った値は、形を確かめてから使う。


def node_security_release(current: Version, index: list[dict]) -> Version | None:
    """同じ major の中で、今より新しく、security が true のバージョンのうち、いちばん新しいものを返す。"""
    found: list[Version] = []
    for release in index:
        name = str(release.get("version", ""))
        if not name.startswith("v") or not PLAIN.fullmatch(name[1:]):
            continue
        version = parse(name[1:])
        if version[0] == current[0] and version > current and release.get("security") is True:
            found.append(version)
    return max(found, default=None)


def python_candidates(current: Version, tags: list[str]) -> list[Version]:
    """同じ minor の中で、今より新しいバージョンを、古い順に返す。"""
    found = {parse(tag[1:]) for tag in tags if tag.startswith("v") and PLAIN.fullmatch(tag[1:])}
    return sorted(version for version in found if version[:2] == current[:2] and version > current)


def fixed_commits(vulnerability: dict) -> set[str]:
    """勧告に書かれた、python/cpython の修正のコミットを返す。"""
    return {
        event["fixed"]
        for affected in vulnerability.get("affected", [])
        for span in affected.get("ranges", [])
        if span.get("type") == "GIT" and str(span.get("repo", "")).rstrip("/") == CPYTHON_URL
        for event in span.get("events", [])
        if "fixed" in event
    }


def python_security_release(
    candidates: list[Version], vulnerabilities: list[dict], new_commits: dict[Version, set[str]]
) -> tuple[Version, list[str]] | None:
    """今のバージョンに効く脆弱性の修正が、初めて入ったバージョンのうち、いちばん新しいものを返す。

    new_commits は、バージョンごとの、1 つ前のバージョンには無いコミット。
    """
    result: tuple[Version, list[str]] | None = None
    for version in candidates:
        fixed = sorted(
            str(vulnerability.get("id", ""))
            for vulnerability in vulnerabilities
            if fixed_commits(vulnerability) & new_commits.get(version, set())
        )
        if fixed:
            result = (version, fixed)
    return result


def cpython_commit(tag: str) -> str:
    return gh("api", f"repos/{CPYTHON}/commits/{tag}", "--jq", ".sha").strip()


def cpython_tags(minor: str) -> list[str]:
    out = gh("api", "--paginate", f"repos/{CPYTHON}/git/matching-refs/tags/v{minor}.", "--jq", ".[].ref")
    return [ref.removeprefix("refs/tags/") for ref in out.split()]


def cpython_new_commits(older: str, newer: str) -> set[str]:
    """newer にあって older に無いコミットを返す。"""
    path = f"repos/{CPYTHON}/compare/{older}...{newer}?per_page=250"
    return set(gh("api", "--paginate", path, "--jq", ".commits[].sha").split())


def osv_affecting(commit: str) -> list[dict]:
    """そのコミットに効く脆弱性を、OSV に聞く。"""
    found: list[dict] = []
    token = None
    while True:
        body = {"commit": commit} | ({"page_token": token} if token else {})
        page = fetch_json(OSV_QUERY, body)
        found += page.get("vulns", [])
        token = page.get("next_page_token")
        if not token:
            return found


def image_published(name: str, version: Version) -> bool:
    """Docker Hub に、見張り役に書くタグのイメージがあるかを返す。"""
    image = versions.IMAGES[name]
    repository = image if "/" in image else f"library/{image}"
    tag = show(version) + ("-slim" if name in SLIM else "")
    try:
        fetch_json(HUB_TAG.format(repository=repository, tag=tag))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False
        raise
    return True


def find_python(current: Version) -> tuple[Version, list[str]] | None:
    candidates = python_candidates(current, cpython_tags(f"{current[0]}.{current[1]}"))
    if not candidates:
        return None
    vulnerabilities = osv_affecting(cpython_commit(f"v{show(current)}"))
    new_commits: dict[Version, set[str]] = {}
    older = current
    for version in candidates:
        new_commits[version] = cpython_new_commits(f"v{show(older)}", f"v{show(version)}")
        older = version
    return python_security_release(candidates, vulnerabilities, new_commits)


def find_node(current: Version) -> tuple[Version, list[str]] | None:
    version = node_security_release(current, fetch_json(NODE_INDEX))
    return (version, ["nodejs.org の一覧で security が true"]) if version else None


def branch_part(name: str, version: Version) -> str:
    return f"{name}-{show(version)}"


def proposed_parts(repo: str) -> set[str]:
    """これまでに出した PR のブランチ名から、名前とバージョンの組を集める。閉じられた PR も数える。"""
    out = gh("api", "--paginate", f"repos/{repo}/pulls?state=all&per_page=100", "--jq", ".[].head.ref")
    return {
        part
        for ref in out.split()
        if ref.startswith(BRANCH_PREFIX)
        for part in ref.removeprefix(BRANCH_PREFIX).split("_")
    }


def find(repo: str, root: Path) -> None:
    current = versions.read_sources(root)
    targets: list[dict] = []
    proposed = proposed_parts(repo)
    for name, finder in (("python", find_python), ("node", find_node)):
        now = parse(current[name])
        found = finder(now)
        if found is None:
            print(f"{name}: {show(now)} より新しい、セキュリティの修正を含むバージョンはありません")
            continue
        version, reasons = found
        if branch_part(name, version) in proposed:
            print(f"{name}: {show(version)} の PR は、すでに出しています")
        elif not image_published(name, version):
            print(f"::notice::{name}: {show(version)} の公式イメージが、まだ公開されていません。次の回に確かめます")
        else:
            print(f"{name}: {show(now)} から {show(version)} へ上げる PR を出します（{', '.join(reasons)}）")
            targets.append({"name": name, "version": show(version), "reasons": reasons})
    write_output(payload=encode({"targets": targets}) if targets else "")


# ここから、PR を出す処理。main のファイルと、渡されたバージョンだけを使う。


def validate_target(target: dict, current: dict[str, str]) -> tuple[str, Version, list[str]]:
    """渡されたバージョンを確かめる。同じ系列の中の、今より新しいバージョンだけを受け付ける。"""
    name = target.get("name")
    if name not in NAMES:
        raise SyncError(f"対象にしない名前です: {name}")
    version = parse(str(target.get("version")))
    now = parse(current[name])
    # Python は同じ minor の中、Node は同じ major の中だけを受け付ける。
    same_line = version[:2] == now[:2] if name == "python" else version[0] == now[0]
    if not same_line or version <= now:
        raise SyncError(f"{name}: {show(now)} から {show(version)} へは上げません")
    reasons = [str(reason) for reason in target.get("reasons", [])]
    if name != "node" and not all(ADVISORY.fullmatch(reason) for reason in reasons):
        raise SyncError("勧告の番号の形が違います")
    return name, version, reasons


def pull_request_body(name: str, old: str, new: str, reasons: list[str]) -> str:
    if name == "python":
        basis = "今のバージョンに効く次の脆弱性の修正が、このバージョンに入っています。\n\n" + "\n".join(
            f"- [{reason}](https://osv.dev/vulnerability/{reason})" for reason in reasons
        )
    else:
        basis = f"[Node.js のバージョンの一覧]({NODE_INDEX})で、このバージョンの `security` が `true` です。"
    return (
        f"{name} を {old} から {new} に上げます。セキュリティの修正を含むバージョンなので、cooldown を置かずに出しています。\n\n"
        f"{basis}\n\n"
        "`automation/security_release.py` が出しました。自動ではマージされません。レビューをお願いします。"
    )


def changed_files(root: Path, name: str, version: Version) -> dict[str, str]:
    """そのバージョンに上げたときに変わるファイルと、その中身を返す。手元のファイルは元に戻す。"""
    touched = [versions.SOURCES[name], versions.SENTINEL]
    before = {path: (root / path).read_text() for path in touched}
    try:
        paths = versions.set_version(root, name, show(version))
        errors = versions.check(root)
        if errors:
            raise SyncError("書き換えたあとに揃っていません: " + " / ".join(errors))
        return {path: (root / path).read_text() for path in sorted(paths)}
    finally:
        for path, text in before.items():
            (root / path).write_text(text)


def open_pull_requests(repo: str, root: Path, targets: list[dict]) -> None:
    """渡されたバージョンごとに、1 本ずつ PR を出す。どれも main から枝を切る。"""
    current = versions.read_sources(root)
    changes = [validate_target(target, current) for target in targets]
    if not changes or len({name for name, _, _ in changes}) != len(changes):
        raise SyncError("渡されたバージョンの組が正しくありません")
    base = gh("api", f"repos/{repo}/git/ref/heads/main", "--jq", ".object.sha").strip()
    token = app_token(repo, os.environ["AUTOMERGE_APP_ID"], os.environ["AUTOMERGE_APP_PRIVATE_KEY"])
    for name, version, reasons in changes:
        files = changed_files(root, name, version)
        title = f"deps: bump {name} from {current[name]} to {show(version)}（セキュリティの修正）"
        body = pull_request_body(name, current[name], show(version), reasons)
        branch = BRANCH_PREFIX + branch_part(name, version)
        commit = create_commit(repo, token, base, files, title)
        app_api(repo, token, "git/refs", {"ref": f"refs/heads/{branch}", "sha": commit})
        created = app_api(repo, token, "pulls", {"title": title, "head": branch, "base": "main", "body": body})
        app_api(repo, token, f"issues/{created['number']}/labels", {"labels": list(LABELS)})
        print(f"#{created['number']} を出しました: {title}")


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    repo = os.environ["GITHUB_REPOSITORY"]
    root = Path(__file__).resolve().parent.parent
    try:
        if mode == "find":
            find(repo, root)
        elif mode == "open":
            open_pull_requests(repo, root, decode(os.environ["PAYLOAD"])["targets"])
        else:
            print("usage: security_release.py [find|open]")
            return 2
    except (SyncError, versions.VersionError, RuntimeError, ValueError, urllib.error.URLError) as error:
        print(f"::error::{error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
