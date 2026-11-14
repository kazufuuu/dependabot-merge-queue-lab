import pytest
from pydantic import ValidationError

from api import Contact, sms_text


def test_phone_is_normalized_to_e164():
    assert Contact(name="Aya", phone="+81 90-1234-5678").phone == "+819012345678"


@pytest.mark.parametrize("phone", ["12345", "+81 90-1234", "not a number"])
def test_invalid_phone_is_rejected(phone):
    with pytest.raises(ValidationError):
        Contact(name="Aya", phone=phone)


def test_carrier_name_is_looked_up():
    assert Contact(name="Awa", phone="+226 70 12 34 56").carrier_name == "Onatel"


def test_sms_text_escapes_name_and_shows_carrier():
    contact = Contact(name="<b>Awa</b>", phone="+226 70 12 34 56")
    assert sms_text(contact) == (
        "&lt;b&gt;Awa&lt;/b&gt; 様、Onatelの番号 +22670123456 を登録しました。"
    )


def test_sms_text_without_carrier():
    contact = Contact(name="Aya", phone="+81 3-1234-5678")
    assert sms_text(contact) == "Aya 様、携帯の番号 +81312345678 を登録しました。"
