"""ランタイムと道具のバージョンを、管理場所から読む。Dependabot 用の Dockerfile と揃える。

バージョンの管理場所は、それぞれの道具が自分で読む場所に置く。

- Python: .python-version（uv が読む。api/ からも、親のディレクトリのこのファイルが読まれる）
- Node: .node-version（手元では fnm や nodenv などが読む。CI では setup-node が読む）
- Terraform: infra/versions.tf の required_version（terraform が読む）

uv は、ここでは管理場所を持たない。ライブラリと同じく、pyproject.toml の開発用の依存に範囲で書き、
バージョンは uv.lock が決める。CI と本番のイメージは、uv.lock のバージョンを使う（show が uv.lock から読んで出す）。
手元の uv は、[tool.uv] required-version の下限より新しければよい。
just（タスクランナー）も同じ。PyPI の rust-just を開発用の依存に書き、CI は uv.lock のバージョンを使う。

1 点に固定できない場所が 2 つある。どちらも、Dependabot の uv の更新が失敗するため。
- requires-python: Dependabot は自分の Python（別の patch）で uv lock を動かす
- [tool.uv] required-version（uv.toml でも同じ）: Dependabot は自分の uv で uv lock を動かす

どの管理場所も、Dependabot は書き換えられない。書き換えられるのは Dockerfile の
FROM なので、dependabot/Dockerfile を Dependabot 用の Dockerfile として置き、Dependabot にはそこを上げさせる。
このスクリプトの sync は、Dependabot 用の Dockerfile のバージョンを .python-version などへ写すだけを行う。新しいバージョンは探さない。

使い方:
  versions.py show          管理場所のバージョンと、uv.lock の uv と just のバージョンを key=value で出す
  versions.py check         管理場所と Dependabot 用の Dockerfile が揃っていることを確かめる
  versions.py sync          Dependabot 用の Dockerfile のバージョンを .python-version などへ写す（Dependabot の PR に対して、workflow が動かす）
  versions.py align         管理場所のバージョンを Dependabot 用の Dockerfile へ写す（人が管理場所を書き換えたあとに動かす）
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SENTINEL = "dependabot/Dockerfile"
PYTHON_VERSION_FILE = ".python-version"
NODE_VERSION_FILE = ".node-version"
TERRAFORM_FILE = "infra/versions.tf"
UV_LOCK = "uv.lock"
DOCKERFILES = (SENTINEL, "api/Dockerfile")

# Dependabot 用の Dockerfile の FROM に書くイメージ。段の名前が、バージョンの名前になる。
IMAGES = {
    "python": "python",
    "node": "node",
    "terraform": "hashicorp/terraform",
}

VERSION = r"\d+\.\d+\.\d+"


class VersionError(Exception):
    """バージョンを読めない、または食い違っている。"""


def one(pattern: str, text: str, where: str) -> re.Match[str]:
    """ちょうど 1 か所に一致することを確かめて返す。0 か所でも 2 か所以上でも失敗させる。"""
    matches = list(re.finditer(pattern, text, re.MULTILINE))
    if len(matches) != 1:
        raise VersionError(f"{where}: バージョンの記述が {len(matches)} か所あります（1 か所のはず）")
    return matches[0]


PATTERNS = {
    "python": rf"^({VERSION})\s*$",
    "node": rf"^({VERSION})\s*$",
    "terraform": rf'^\s*required_version\s*=\s*"=\s*({VERSION})"\s*$',
}


SOURCES = {
    "python": PYTHON_VERSION_FILE,
    "node": NODE_VERSION_FILE,
    "terraform": TERRAFORM_FILE,
}


def read_sources(root: Path) -> dict[str, str]:
    """管理場所からバージョンを読む。"""
    return {
        name: one(pattern, (root / SOURCES[name]).read_text(), SOURCES[name]).group(1)
        for name, pattern in PATTERNS.items()
    }


# uv.lock からバージョンを読む道具。左が show で出す名前、右が PyPI のパッケージの名前。
LOCKED = {
    "uv": "uv",
    "just": "rust-just",
}


def locked(root: Path, name: str) -> str:
    """uv.lock に入っている道具のバージョンを返す。CI と本番のイメージが、このバージョンを使う。"""
    pattern = rf'^name = "{re.escape(LOCKED[name])}"\nversion = "({VERSION})"$'
    return one(pattern, (root / UV_LOCK).read_text(), f"{UV_LOCK} の {LOCKED[name]}").group(1)


def read_sentinel(root: Path) -> dict[str, str]:
    """Dependabot 用の Dockerfile からバージョンを読む。"""
    text = (root / SENTINEL).read_text()
    versions: dict[str, str] = {}
    for name, image in IMAGES.items():
        pattern = rf"^FROM\s+{re.escape(image)}:({VERSION})(?:-slim)?\s+AS\s+{name}\s*$"
        versions[name] = one(pattern, text, f"{SENTINEL} の {name}").group(1)
    return versions


def images_outside_docker_hub(text: str) -> list[str]:
    """Docker Hub 以外から取るイメージを返す。

    Dependabot の cooldown は、Docker Hub のイメージにしか効かない。
    ほかのレジストリでは公開日を取れず、公開直後のバージョンがそのまま提案される。
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
            errors.append(
                f"{name}: 管理場所（{SOURCES[name]}）は {actual[name]}、{SENTINEL} は {version}。"
                "管理場所を直したのなら uv run just align を、Dependabot 用の Dockerfile を直したのなら uv run just sync を動かしてください"
            )
    for path in DOCKERFILES:
        for image in images_outside_docker_hub((root / path).read_text()):
            errors.append(f"{path} の {image} は Docker Hub のイメージではありません。cooldown が効きません")
    return errors


def sync(root: Path) -> list[str]:
    """Dependabot 用の Dockerfile のバージョンを .python-version などへ写す。書き換えたファイルを返す。"""
    wanted = read_sentinel(root)
    changed: list[str] = []
    for name, version in wanted.items():
        path = SOURCES[name]
        file = root / path
        text = file.read_text()
        match = one(PATTERNS[name], text, path)
        if match.group(1) == version:
            continue
        file.write_text(text[: match.start(1)] + version + text[match.end(1) :])
        if path not in changed:
            changed.append(path)
    return changed


def align(root: Path) -> list[str]:
    """管理場所のバージョンを Dependabot 用の Dockerfile へ写す。人が意図してバージョンを変えるときに使う。"""
    actual = read_sources(root)
    file = root / SENTINEL
    text = file.read_text()
    changed: list[str] = []
    for name, image in IMAGES.items():
        pattern = rf"^FROM\s+{re.escape(image)}:({VERSION})(?:-slim)?\s+AS\s+{name}\s*$"
        match = one(pattern, text, f"{SENTINEL} の {name}")
        if match.group(1) != actual[name]:
            text = text[: match.start(1)] + actual[name] + text[match.end(1) :]
            changed.append(name)
    if changed:
        file.write_text(text)
    return changed


def set_version(root: Path, name: str, version: str) -> list[str]:
    """管理場所と Dependabot 用の Dockerfile の両方を、指定のバージョンにする。書き換えたファイルを返す。"""
    if not re.fullmatch(VERSION, version):
        raise VersionError(f"{name}: バージョンの形が違います: {version}")
    path = SOURCES[name]
    file = root / path
    text = file.read_text()
    match = one(PATTERNS[name], text, path)
    changed: list[str] = []
    if match.group(1) != version:
        file.write_text(text[: match.start(1)] + version + text[match.end(1) :])
        changed.append(path)
    if name in IMAGES and align(root):
        changed.append(SENTINEL)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("show", "check", "sync", "align"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    try:
        if args.command == "show":
            for name, version in read_sources(args.root).items():
                print(f"{name}={version}")
            for name in LOCKED:
                print(f"{name}={locked(args.root, name)}")
        elif args.command == "sync":
            for path in sync(args.root):
                print(path)
        elif args.command == "align":
            for name in align(args.root):
                print(f"{SENTINEL}: {name}")
        else:
            errors = check(args.root)
            for message in errors:
                print(f"NG: {message}")
            if errors:
                return 1
            print("OK: バージョンの管理場所と Dependabot 用の Dockerfile は揃っています")
    except (VersionError, OSError) as error:
        print(f"NG: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
