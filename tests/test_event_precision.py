import json
import sqlite3
from pathlib import Path

import pytest

from xbrlswarm.domain import EventPrecision


MIGRATIONS = Path("migrations")
CONTRACT = Path("contracts/event-time-precision.json")
DECISION = Path("docs/event-time-precision.md")
ACCEPTANCE = Path("docs/step-17-acceptance.md")


def _event_fields(*, event_date: str, event_time: str | None = None) -> dict:
    from xbrlswarm.domain import event_time_fields

    return event_time_fields(event_date=event_date, event_time=event_time)


def test_date_only_preserves_missing_time() -> None:
    assert _event_fields(event_date="2024-05-10") == {
        "event_date": "2024-05-10",
        "event_time": None,
        "event_precision": "date",
    }


def test_event_precision_enum_matches_contract_values() -> None:
    assert {item.value for item in EventPrecision} == {"date", "second"}


def test_explicit_seconds_are_preserved_without_timezone_inference() -> None:
    assert _event_fields(event_date="2024-05-10", event_time="00:00:00") == {
        "event_date": "2024-05-10",
        "event_time": "00:00:00",
        "event_precision": "second",
    }


@pytest.mark.parametrize(
    "event_date,event_time",
    [
        ("2024-02-30", None),
        ("2024-5-10", None),
        ("2024-05-10", "14:35"),
        ("2024-05-10", "24:00:00"),
        ("2024-05-10", ""),
    ],
)
def test_invalid_or_unsupported_precision_is_not_guessed(
    event_date: str, event_time: str | None
) -> None:
    with pytest.raises(ValueError):
        _event_fields(event_date=event_date, event_time=event_time)


def test_date_only_round_trips_without_synthetic_midnight() -> None:
    connection = sqlite3.connect(":memory:")
    for path in sorted(MIGRATIONS.glob("*.sql")):
        connection.executescript(path.read_text(encoding="utf-8"))
    connection.execute(
        "INSERT INTO task (stock_id, fiscal_year, report_period, state, engine) "
        "VALUES ('2330', 2024, 'Q1', 'undone', 'mops')"
    )
    connection.execute(
        """INSERT INTO evidence (
               task_id, evidence_type, event_date, event_time, event_precision,
               source_type, source_locator, retrieved_at, verification_state
           ) VALUES (1, 'financial_report_document', :event_date, :event_time,
                     :event_precision, 'mops', 'mops:date-only',
                     '2026-09-23T01:02:03Z', 'unverified')""",
        _event_fields(event_date="2024-05-10"),
    )
    assert connection.execute(
        "SELECT event_date, event_time, event_precision FROM evidence"
    ).fetchone() == ("2024-05-10", None, "date")


def test_precision_contract_and_docs() -> None:
    assert json.loads(CONTRACT.read_text(encoding="utf-8")) == {
        "contract": "event_time_precision",
        "version": 1,
        "values": ["date", "second"],
        "date_only": {"event_time": None, "event_precision": "date"},
        "explicit_hh_mm_ss": {"event_precision": "second"},
        "synthetic_midnight_forbidden": True,
        "unsupported_precision": "reject_without_guessing",
        "new_evidence_storage_enforcement": "migration_0007_insert_trigger",
        "legacy_goodinfo_null_precision_identity": "second_when_event_date_and_time_present",
    }
    assert "2024-05-10 00:00:00" in DECISION.read_text(encoding="utf-8")
    assert "0007_enforce_event_precision.sql" in ACCEPTANCE.read_text(encoding="utf-8")
