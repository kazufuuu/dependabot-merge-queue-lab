"""版の書かれた場所が、Dockerfile の FROM とそろっていることを確かめる。

ランタイムと道具の版は Dockerfile の FROM で決める。Dependabot が書き換えられるのは
FROM だけなので、ほかの場所は minor までにとどめ、ここで FROM とのずれを検出する。
"""

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def from_versions(dockerfile: str, image: str) -> list[str]:
    pattern = re.compile(rf"^FROM\s+{re.escape(image)}:(\d+(?:\.\d+)*)", re.MULTILINE)
    return pattern.findall((ROOT / dockerfile).read_text())


DOCKERFILES = ("Dockerfile", "api/Dockerfile", "web/Dockerfile", "tools/terraform/Dockerfile")


def images_outside_docker_hub(dockerfile: str) -> list[str]:
    """Docker Hub 以外から取るイメージを返す。

    Dependabot の待機（cooldown）は、Docker Hub のイメージにしか効かない。
    ほかのレジストリでは公開日を取れず、公開直後の版がそのまま提案される。
    """
    stages = set(re.findall(r"^FROM\s+\S+\s+AS\s+(\S+)", (ROOT / dockerfile).read_text(), re.MULTILINE))
    images = re.findall(r"^FROM\s+(?:--\S+\s+)*(\S+)", (ROOT / dockerfile).read_text(), re.MULTILINE)
    outside = []
    for image in images:
        if image in stages or image == "scratch":
            continue
        first = image.split("/")[0]
        if "/" in image and ("." in first or ":" in first or first == "localhost"):
            outside.append(image)
    return outside


def minor(version: str) -> str:
    return ".".join(version.split(".")[:2])


def main() -> int:
    errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    for dockerfile in DOCKERFILES:
        for image in images_outside_docker_hub(dockerfile):
            check(False, f"{dockerfile} の {image} は Docker Hub のイメージではありません。待機が効きません")

    python = {f: from_versions(f, "python") for f in ("Dockerfile", "api/Dockerfile")}
    all_python = {v for versions in python.values() for v in versions}
    check(len(all_python) == 1, f"python の FROM がそろっていません: {python}")
    uv = {f: from_versions(f, "astral/uv") for f in ("Dockerfile", "api/Dockerfile")}
    check(len({v for vs in uv.values() for v in vs}) == 1, f"uv の FROM がそろっていません: {uv}")

    for version in all_python:
        for path in (".python-version", "api/.python-version"):
            written = (ROOT / path).read_text().strip()
            check(written == minor(version), f"{path} は {written}、FROM は {version}")
        for path in ("pyproject.toml", "api/pyproject.toml"):
            requires = tomllib.loads((ROOT / path).read_text())["project"]["requires-python"]
            check(
                requires.startswith(f">={minor(version)},"),
                f"{path} の requires-python は {requires}、FROM は {version}",
            )

    for version in from_versions("web/Dockerfile", "node"):
        major = version.split(".")[0]
        written = (ROOT / "web/.node-version").read_text().strip()
        check(written == major, f"web/.node-version は {written}、FROM は {version}")

    for version in from_versions("tools/terraform/Dockerfile", "hashicorp/terraform"):
        text = (ROOT / "infra/versions.tf").read_text()
        required = re.search(r'required_version\s*=\s*">=\s*([\d.]+)"', text)
        check(required is not None, "infra/versions.tf に required_version がありません")
        if required:
            lower = tuple(int(n) for n in required.group(1).split("."))
            actual = tuple(int(n) for n in version.split("."))
            check(actual >= lower, f"terraform の FROM は {version}、required_version は >= {required.group(1)}")

    for message in errors:
        print(f"NG: {message}")
    if not errors:
        print("OK: 版の書かれた場所はそろっています")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
