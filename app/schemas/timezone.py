"""Pydantic response type for explicit Asia/Shanghai timestamps."""

from datetime import datetime
from typing import Annotated

from pydantic import PlainSerializer

from app.core.timezone import beijing_isoformat


BeijingDateTime = Annotated[
    datetime,
    PlainSerializer(beijing_isoformat, return_type=str, when_used="json"),
]
