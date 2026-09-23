"""Source-faithful event date, time, and precision mapping."""

import re
from datetime import date, time
from enum import StrEnum


class EventPrecision(StrEnum):
    DATE = "date"
    SECOND = "second"


def event_time_fields(
    *, event_date: str, event_time: str | None = None
) -> dict[str, str | None]:
    """Preserve only the precision explicitly present in normalized source fields.

    The caller must not synthesize ``event_time`` from a date-only source.
    """
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", event_date):
        raise ValueError("event_date 必須是 YYYY-MM-DD")
    date.fromisoformat(event_date)

    if event_time is None:
        return {
            "event_date": event_date,
            "event_time": None,
            "event_precision": EventPrecision.DATE.value,
        }

    if not re.fullmatch(r"\d{2}:\d{2}:\d{2}", event_time):
        raise ValueError("event_time 必須是來源提供的 HH:MM:SS")
    time.fromisoformat(event_time)
    return {
        "event_date": event_date,
        "event_time": event_time,
        "event_precision": EventPrecision.SECOND.value,
    }
