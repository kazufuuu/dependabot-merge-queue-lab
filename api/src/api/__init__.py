"""連絡先を受け取り、SMS の文面を作る。"""

import phonenumbers
from jinja2 import Environment, StrictUndefined
from phonenumbers import PhoneNumberFormat, carrier
from pydantic import BaseModel, field_validator

_env = Environment(autoescape=True, undefined=StrictUndefined)
_SMS = _env.from_string("{{ name }} 様、{{ carrier or '携帯' }}の番号 {{ phone }} を登録しました。")


class Contact(BaseModel):
    name: str
    phone: str

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: str) -> str:
        try:
            parsed = phonenumbers.parse(value, None)
        except phonenumbers.NumberParseException as exc:
            raise ValueError("電話番号を読み取れません") from exc
        if not phonenumbers.is_valid_number(parsed):
            raise ValueError("電話番号が正しくありません")
        return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)

    @property
    def carrier_name(self) -> str:
        """番号の割り当て先の通信事業者名。分からなければ空文字。"""
        return carrier.name_for_number(phonenumbers.parse(self.phone, None), "en")


def sms_text(contact: Contact) -> str:
    return _SMS.render(name=contact.name, phone=contact.phone, carrier=contact.carrier_name)
