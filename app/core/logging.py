import json
import logging
import re
from typing import Any

from app.core.timezone import beijing_isoformat, beijing_now


_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|password|passwd|pwd)([=:])([^\s,&]+)"),
    re.compile(r"(?i)(mysql(?:\+\w+)?://[^:\s/]+:)([^@\s]+)(@)"),
    re.compile(r"(?i)(bearer\s+)([^\s,]+)"),
)


def redact_secrets(value: str) -> str:
    """Remove common credential forms before a value reaches application logs."""
    redacted = value
    for pattern in _SECRET_PATTERNS:
        if pattern.pattern.startswith("(?i)(mysql"):
            redacted = pattern.sub(r"\1***\3", redacted)
        elif pattern.pattern.startswith("(?i)(bearer"):
            redacted = pattern.sub(r"\1***", redacted)
        else:
            redacted = pattern.sub(r"\1\2***", redacted)
    return redacted


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.getMessage())
            record.args = ()
        for key, value in list(record.__dict__.items()):
            if isinstance(value, str):
                record.__dict__[key] = redact_secrets(value)
        return True


class JsonFormatter(logging.Formatter):
    _EXTRA_FIELDS = (
        "request_id",
        "method",
        "path",
        "status_code",
        "latency_ms",
        "error_type",
        "knowledge_base_id",
        "retrieval_log_id",
        "retrieved_count",
        "keyword_latency_ms",
        "vector_latency_ms",
        "fusion_latency_ms",
        "rerank_latency_ms",
        "task_id",
        "document_id",
        "operation",
        "chunk_count",
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": beijing_isoformat(beijing_now()),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in self._EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(log_level: str) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(SecretRedactionFilter())
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=log_level, handlers=[handler], force=True)
