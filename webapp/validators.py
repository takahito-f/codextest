"""Input validation helpers."""

from __future__ import annotations

import re
from typing import Tuple


OPERATOR_ID_PATTERN = re.compile(r"^[A-Za-z0-9]{4}$")
BILLING_MONTH_PATTERN = re.compile(r"^[0-9]{6}$")


def validate_operator_id(value: str) -> Tuple[bool, str]:
    if not value:
        return False, "事業者IDを入力してください。"
    if not OPERATOR_ID_PATTERN.fullmatch(value):
        return False, "事業者IDは半角英数字4桁で入力してください。"
    return True, ""


def validate_billing_month(value: str) -> Tuple[bool, str]:
    if not value:
        return False, "課金月を入力してください。"
    if not BILLING_MONTH_PATTERN.fullmatch(value):
        return False, "課金月はYYYYMM形式で入力してください。"
    return True, ""
