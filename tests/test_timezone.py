import json
import logging
from datetime import datetime, timedelta, timezone

from app.core.logging import JsonFormatter
from app.core.timezone import BEIJING_TIMEZONE, as_beijing_time, beijing_now


def _assert_beijing_iso(value: str) -> None:
    parsed = datetime.fromisoformat(value)
    assert parsed.utcoffset() == timedelta(hours=8)


def test_timezone_helpers_store_naive_beijing_and_serialize_explicit_offset() -> None:
    stored_value = beijing_now()
    assert stored_value.tzinfo is None

    converted = as_beijing_time(datetime(2026, 8, 10, 0, 0, tzinfo=BEIJING_TIMEZONE))
    assert converted.isoformat() == "2026-08-10T00:00:00+08:00"

    utc_value = datetime(2026, 8, 10, 0, 0, tzinfo=BEIJING_TIMEZONE).astimezone(timezone.utc)
    assert as_beijing_time(utc_value).isoformat() == "2026-08-10T00:00:00+08:00"


def test_api_response_timestamps_are_explicit_beijing_time(client) -> None:
    created = client.post("/knowledge-bases", json={"name": "timezone-test"})
    assert created.status_code == 201
    _assert_beijing_iso(created.json()["created_at"])
    _assert_beijing_iso(created.json()["updated_at"])


def test_structured_log_timestamp_is_explicit_beijing_time() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="repomind.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="timezone_test",
        args=(),
        exc_info=None,
    )

    payload = json.loads(formatter.format(record))
    _assert_beijing_iso(payload["timestamp"])
