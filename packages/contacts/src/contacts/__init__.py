"""連絡先の表示用の値を作る。"""

from datetime import datetime

import humanize
from slugify import slugify


def contact_key(name: str) -> str:
    """名前から URL に使えるキーを作る。"""
    return slugify(name, max_length=40, word_boundary=True)


def last_contacted(when: datetime, now: datetime) -> str:
    """最後に連絡した時刻を、今から見た言い方にする。"""
    return humanize.naturaltime(now - when)


def storage_used(size: int) -> str:
    """添付の合計サイズを読みやすくする。"""
    return humanize.naturalsize(size, binary=True)
