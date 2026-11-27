from __future__ import annotations
from datetime import datetime, timedelta, timezone

__all__ = ["CHROMIUM_EPOCH", "timestamp_from_microseconds"]

CHROMIUM_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)


def timestamp_from_microseconds(microseconds: int) -> datetime:
    return CHROMIUM_EPOCH + timedelta(microseconds=microseconds)
