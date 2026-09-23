"""xbrlswarm 的來源無關領域契約。"""

from .announcement_time import announcement_event_fields
from .calendar_period import calendar_year_period_end
from .evidence_type import EvidenceType
from .engine import Engine
from .event_time import EventPrecision, event_time_fields
from .report_period import ReportPeriod
from .revision_kind import RevisionKind

__all__ = [
    "Engine",
    "EvidenceType",
    "EventPrecision",
    "ReportPeriod",
    "RevisionKind",
    "announcement_event_fields",
    "calendar_year_period_end",
    "event_time_fields",
]
