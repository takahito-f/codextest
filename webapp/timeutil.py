"""Utilities for working with Japan Time (JTC)."""

from __future__ import annotations

import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

JTC = ZoneInfo("Asia/Tokyo")


def configure_tz() -> None:
    """Ensure the process runs in JTC."""

    os.environ.setdefault("TZ", "Asia/Tokyo")
    if hasattr(time, "tzset"):
        time.tzset()


def now_jtc_naive() -> datetime:
    """Return the current time in JTC without tzinfo for DB storage."""

    return datetime.now(JTC).replace(tzinfo=None)
