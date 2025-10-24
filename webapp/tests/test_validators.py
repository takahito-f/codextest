import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from validators import validate_billing_month, validate_operator_id


def test_validate_operator_id():
    assert validate_operator_id("AB12")[0]
    assert not validate_operator_id("abc")[0]


def test_validate_billing_month():
    assert validate_billing_month("202401")[0]
    assert not validate_billing_month("20241")[0]
