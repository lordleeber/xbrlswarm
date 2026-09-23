import sqlite3
from pathlib import Path

import pytest

from xbrlswarm.domain import announcement_event_fields, event_time_fields


MIGRATIONS = Path("migrations")
STEP17_MIGRATION = MIGRATIONS / "0007_enforce_event_precision.sql"


def _database(*, through_step16: bool = False) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA recursive_triggers = ON")
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if through_step16 and path >= STEP17_MIGRATION:
            continue
        connection.executescript(path.read_text(encoding="utf-8"))
    connection.execute(
        "INSERT INTO task (stock_id, fiscal_year, report_period, state, engine) "
        "VALUES ('2330', 2024, 'Q1', 'undone', 'goodinfo')"
    )
    return connection


def _insert_announcement(
    connection: sqlite3.Connection,
    *,
    precision: str | None,
    ignore_duplicate: bool = False,
) -> None:
    conflict = "ON CONFLICT DO NOTHING" if ignore_duplicate else ""
    fields = announcement_event_fields(
        speech_date="2024-05-10", speech_time="14:48:53"
    )
    connection.execute(
        f"""INSERT INTO evidence (
                task_id, evidence_type, event_date, event_time, event_precision,
                source_type, source_locator, source_subject, retrieved_at,
                verification_state
            ) VALUES (1, :evidence_type, :event_date, :event_time,
                      :event_precision, 'goodinfo', 'goodinfo:2330:announcement',
                      '董事會通過財報', '2026-09-23T01:02:03Z', 'unverified')
            {conflict}""",
        {**fields, "event_precision": precision},
    )


def test_legacy_goodinfo_announcement_remains_single_after_retry() -> None:
    connection = _database(through_step16=True)
    _insert_announcement(connection, precision=None)

    connection.executescript(STEP17_MIGRATION.read_text(encoding="utf-8"))
    _insert_announcement(connection, precision="second", ignore_duplicate=True)

    assert connection.execute(
        "SELECT event_precision FROM evidence"
    ).fetchall() == [(None,)]


def test_new_evidence_precision_combinations_are_enforced_by_sqlite() -> None:
    connection = _database()

    for date_value, time_value, precision in (
        (None, None, "date"),
        ("2024-05-10", None, None),
        ("2024-05-10", None, "second"),
        ("2024-05-10", "14:48:53", None),
        ("2024-05-10", "14:48:53", "date"),
        ("2024-05-10", "14:48:53", "minute"),
    ):
        with pytest.raises(sqlite3.IntegrityError, match="event precision"):
            connection.execute(
                """INSERT INTO evidence (
                    task_id, evidence_type, event_date, event_time,
                    event_precision, source_type, retrieved_at,
                    verification_state
                ) VALUES (1, 'search_mirror', ?, ?, ?, 'cnyes',
                          '2026-09-23T01:02:03Z', 'unverified')""",
                (date_value, time_value, precision),
            )

    for fields in (
        {"event_date": None, "event_time": None, "event_precision": None},
        event_time_fields(event_date="2024-05-10"),
        event_time_fields(event_date="2024-05-10", event_time="14:48:53"),
    ):
        connection.execute(
            """INSERT INTO evidence (
                task_id, evidence_type, event_date, event_time,
                event_precision, source_type, retrieved_at,
                verification_state
            ) VALUES (1, 'search_mirror', :event_date, :event_time,
                      :event_precision, 'cnyes', '2026-09-23T01:02:03Z',
                      'unverified')""",
            fields,
        )
    assert connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 3


def test_step17_migration_rejects_existing_normalized_duplicates() -> None:
    connection = _database(through_step16=True)
    _insert_announcement(connection, precision=None)
    _insert_announcement(connection, precision="second")

    with pytest.raises(sqlite3.IntegrityError):
        connection.executescript(STEP17_MIGRATION.read_text(encoding="utf-8"))

    assert connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 2
