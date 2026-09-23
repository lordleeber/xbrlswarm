"""Map an explicitly sourced speech date and time to an announcement event."""

from .evidence_type import EvidenceType
from .event_time import event_time_fields


def announcement_event_fields(
    *, speech_date: str | None, speech_time: str | None
) -> dict[str, str | None]:
    """Return evidence fields only when both source-provided speech fields exist.

    The caller identifies and extracts the source fields; only their normalized
    format and explicit second-level precision are validated here.
    """
    if not speech_date or not speech_date.strip() or not speech_time or not speech_time.strip():
        raise ValueError("發言日期與發言時間都必須由來源明確提供")

    return {
        "evidence_type": EvidenceType.MATERIAL_ANNOUNCEMENT.value,
        **event_time_fields(event_date=speech_date, event_time=speech_time),
    }
