"""連絡先への通知を組み立てる。"""

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

from contacts import contact_key

PUSH_SUPPORTED = SpecifierSet(">=2.4,<4")


def supports_push(client_version: str) -> bool:
    """クライアントのバージョンが push 通知に対応しているかを返す。"""
    try:
        version = Version(client_version)
    except InvalidVersion:
        return False
    return PUSH_SUPPORTED.contains(version, prereleases=False)


def channel_for(name: str, client_version: str) -> str:
    """通知の送り先を決める。"""
    kind = "push" if supports_push(client_version) else "mail"
    return f"{kind}:{contact_key(name)}"
