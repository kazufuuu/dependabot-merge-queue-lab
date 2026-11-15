"""動かしている Python のバージョンが、管理場所と同じことを確かめる。

手元のバージョンがずれていると、ここで落ちる。.python-version のバージョンを入れる。
uv のバージョンは照合しない。手元の uv は、pyproject.toml の required-version の下限より新しければよい。
"""

import platform
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_python_is_the_pinned_version():
    assert platform.python_version() == (ROOT / ".python-version").read_text().strip()
