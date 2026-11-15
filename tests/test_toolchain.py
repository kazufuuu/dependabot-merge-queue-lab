"""動かしている Python と uv の版が、正本と同じことを確かめる。

手元の版がずれていると、ここで落ちる。mise か asdf で、.tool-versions の版を入れる。
"""

import os
import platform
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_python_is_the_pinned_version():
    assert platform.python_version() == (ROOT / ".python-version").read_text().strip()


def test_uv_is_the_pinned_version():
    uv = os.environ.get("UV")
    if uv is None:
        pytest.skip("uv run を通さずに動かしている")
    pinned = re.search(r"^uv (\S+)$", (ROOT / ".tool-versions").read_text(), re.MULTILINE).group(1)
    running = subprocess.run([uv, "--version"], capture_output=True, text=True, check=True).stdout.split()[1]
    assert running == pinned, f"uv は {running}、正本（.tool-versions）は {pinned}。mise install を動かしてください"
