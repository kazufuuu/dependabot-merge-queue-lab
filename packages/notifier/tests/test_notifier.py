import pytest
from notifier import channel_for, supports_push


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("2.4", True),
        ("2.4.0.post1", True),
        ("3.9.12", True),
        ("2.3.9", False),
        ("4.0", False),
        ("3.0rc1", False),
        ("not-a-version", False),
    ],
)
def test_supports_push(version, expected):
    assert supports_push(version) is expected


def test_channel_uses_contact_key():
    assert channel_for("Zoë Müller", "3.1") == "push:zoe-muller"
    assert channel_for("Zoë Müller", "1.0") == "mail:zoe-muller"
