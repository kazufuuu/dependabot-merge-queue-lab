"""ランタイムと道具の版を、正本から読む。見張り役の Dockerfile と揃える。

版の正本は、それぞれの道具が自分で読む場所に置く。

- Python: pyproject.toml の requires-python（uv が読む）
- uv: pyproject.toml の [tool.uv] required-version（uv が読む）
- Node: web/.node-version（setup-node や手元の版管理の道具が読む）
- Terraform: infra/versions.tf の required_version（terraform が読む）

Dependabot は、これらの場所を書き換えられない。書き換えられるのは Dockerfile の FROM なので、
versions/Dockerfile を見張り役として置き、Dependabot にはそこを上げさせる。
このスクリプトの sync は、見張り役の版を正本へ写すだけを行う。新しい版は探さない。

使い方:
  versions.py show          正本の版を key=value で出す
  versions.py check         正本、見張り役、ロックファイルが揃っていることを確かめる
  versions.py sync          見張り役の版を正本へ写す（ロックファイルは別に作り直す）
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SENTINEL = "versions/Dockerfile"
PYPROJECTS = ("pyproject.toml", "api/pyproject.toml")
LOCKFILES = ("uv.lock", "api/uv.lock")
NODE_VERSION_FILE = "web/.node-version"
TERRAFORM_FILE = "infra/versions.tf"
DOCKERFILES = (SENTINEL, "api/Dockerfile")

# 見張り役の FROM に書くイメージ。段の名前が、版の名前になる。
IMAGES = {
    "python": "python",
    "uv": "astral/uv",
    "node": "node",
    "terraform": "hashicorp/terraform",
}

VERSION = r"\d+\.\d+\.\d+"


class VersionError(Exception):
    """版を読めない、または食い違っている。"""


def one(pattern: str, text: str, where: str) -> re.Match[str]:
    """ちょうど 1 か所に一致することを確かめて返す。0 か所でも 2 か所以上でも失敗させる。"""
    matches = list(re.finditer(pattern, text, re.MULTILINE))
    if len(matches) != 1:
        raise VersionError(f"{where}: 版の記述が {len(matches)} か所あります（1 か所のはず）")
    return matches[0]


PATTERNS = {
    "python": rf'^requires-python\s*=\s*"==({VERSION})"\s*$',
    "uv": rf'^required-version\s*=\s*"==({VERSION})"\s*$',
    "node": rf"^({VERSION})\s*$",
    "terraform": rf'^\s*required_version\s*=\s*"=\s*({VERSION})"\s*$',
}


def sources(name: str) -> tuple[str, ...]:
    """その版の正本のファイル。Python と uv は、2 つのプロジェクトに同じ値を書く。"""
    return {"python": PYPROJECTS, "uv": PYPROJECTS, "node": (NODE_VERSION_FILE,), "terraform": (TERRAFORM_FILE,)}[name]


def read_sources(root: Path) -> dict[str, str]:
    """正本から版を読む。同じ版を書く場所どうしが食い違っていたら失敗させる。"""
    versions: dict[str, str] = {}
    for name, pattern in PATTERNS.items():
        found = {path: one(pattern, (root / path).read_text(), path).group(1) for path in sources(name)}
        if len(set(found.values())) != 1:
            raise VersionError(f"{name} の版が食い違っています: {found}")
        versions[name] = next(iter(found.values()))
    return versions


def read_sentinel(root: Path) -> dict[str, str]:
    """見張り役の Dockerfile から版を読む。"""
    text = (root / SENTINEL).read_text()
    versions: dict[str, str] = {}
    for name, image in IMAGES.items():
        pattern = rf"^FROM\s+{re.escape(image)}:({VERSION})(?:-slim)?\s+AS\s+{name}\s*$"
        versions[name] = one(pattern, text, f"{SENTINEL} の {name}").group(1)
    return versions


def images_outside_docker_hub(text: str) -> list[str]:
    """Docker Hub 以外から取るイメージを返す。

    Dependabot の待機（cooldown）は、Docker Hub のイメージにしか効かない。
    ほかのレジストリでは公開日を取れず、公開直後の版がそのまま提案される。
    """
    stages = set(re.findall(r"^FROM\s+\S+\s+AS\s+(\S+)", text, re.MULTILINE))
    outside = []
    for image in re.findall(r"^FROM\s+(?:--\S+\s+)*(\S+)", text, re.MULTILINE):
        if image in stages or image == "scratch":
            continue
        first = image.split("/")[0]
        if "/" in image and ("." in first or ":" in first or first == "localhost"):
            outside.append(image)
    return outside


def check(root: Path) -> list[str]:
    """揃っていない点を返す。空なら揃っている。"""
    errors: list[str] = []
    try:
        actual = read_sources(root)
        wanted = read_sentinel(root)
    except VersionError as error:
        return [str(error)]
    for name, version in wanted.items():
        if actual[name] != version:
            errors.append(f"{name}: 正本は {actual[name]}、{SENTINEL} は {version}。versions.py sync で揃えてください")
    for path in LOCKFILES:
        locked = one(r'^requires-python\s*=\s*"==([^"]+)"\s*$', (root / path).read_text(), path).group(1)
        if locked != actual["python"]:
            errors.append(f"{path} の requires-python は {locked}、正本は {actual['python']}。uv lock し直してください")
    for path in DOCKERFILES:
        for image in images_outside_docker_hub((root / path).read_text()):
            errors.append(f"{path} の {image} は Docker Hub のイメージではありません。待機が効きません")
    return errors


def sync(root: Path) -> list[str]:
    """見張り役の版を正本へ写す。書き換えたファイルを返す。"""
    wanted = read_sentinel(root)
    changed: list[str] = []
    for name, pattern in PATTERNS.items():
        for path in sources(name):
            file = root / path
            text = file.read_text()
            match = one(pattern, text, path)
            if match.group(1) == wanted[name]:
                continue
            file.write_text(text[: match.start(1)] + wanted[name] + text[match.end(1) :])
            if path not in changed:
                changed.append(path)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("show", "check", "sync"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    try:
        if args.command == "show":
            for name, version in read_sources(args.root).items():
                print(f"{name}={version}")
        elif args.command == "sync":
            for path in sync(args.root):
                print(path)
        else:
            errors = check(args.root)
            for message in errors:
                print(f"NG: {message}")
            if errors:
                return 1
            print("OK: 版の正本、見張り役、ロックファイルは揃っています")
    except (VersionError, OSError) as error:
        print(f"NG: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
