from datetime import datetime, timedelta

from contacts import contact_key, last_contacted, storage_used


def test_contact_key_transliterates_and_joins_with_hyphen():
    assert contact_key("Zoë Müller-Štěpánek") == "zoe-muller-stepanek"


def test_contact_key_cuts_at_word_boundary():
    key = contact_key("Alexandria Catherine Montgomery Fitzgerald Worthington")
    assert key == "alexandria-catherine-montgomery"
    assert len(key) <= 40


def test_last_contacted_is_relative():
    now = datetime(2026, 1, 10, 12, 0, 0)
    assert last_contacted(now - timedelta(hours=3), now) == "3 hours ago"
    assert last_contacted(now - timedelta(days=2), now) == "2 days ago"


def test_storage_used_is_binary():
    assert storage_used(3 * 1024 * 1024) == "3.0 MiB"
