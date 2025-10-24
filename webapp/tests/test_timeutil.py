import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from timeutil import JTC, now_jtc_naive


def test_now_jtc_naive_returns_naive_datetime():
    value = now_jtc_naive()
    assert value.tzinfo is None

    localized = value.replace(tzinfo=JTC)
    assert localized.tzinfo == JTC
