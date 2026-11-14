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


def minor(version: str) -> str:
    return ".".join(version.split(".")[:2])


def main() -> int:
    errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    python = {f: from_versions(f, "python") for f in ("Dockerfile", "api/Dockerfile")}
    all_python = {v for versions in python.values() for v in versions}
    check(len(all_python) == 1, f"python の FROM がそろっていません: {python}")
    uv = {f: from_versions(f, "ghcr.io/astral-sh/uv") for f in ("Dockerfile", "api/Dockerfile")}
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
