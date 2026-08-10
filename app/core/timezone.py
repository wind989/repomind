"""Timezone helpers for user-visible RepoMind timestamps.

MySQL ``DATETIME`` values do not carry a timezone. RepoMind stores those values
as Asia/Shanghai wall-clock time and treats naive values read from the database
as Asia/Shanghai before serializing them to API clients.
"""

from datetime import datetime
from zoneinfo import ZoneInfo


BEIJING_TIMEZONE = ZoneInfo("Asia/Shanghai")


def beijing_now() -> datetime:
    """Return a naive datetime intended for a MySQL DATETIME column."""
    return datetime.now(BEIJING_TIMEZONE).replace(tzinfo=None)


def as_beijing_time(value: datetime) -> datetime:
    """Attach or convert a datetime to Asia/Shanghai for user-facing output."""
    if value.tzinfo is None:
        return value.replace(tzinfo=BEIJING_TIMEZONE)
    return value.astimezone(BEIJING_TIMEZONE)


def beijing_isoformat(value: datetime) -> str:
    """Serialize a user-visible timestamp with an explicit +08:00 offset."""
    return as_beijing_time(value).isoformat()
