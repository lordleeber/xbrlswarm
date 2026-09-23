import json
import sqlite3
from pathlib import Path

import pytest


CONTRACT = Path("contracts/announcement-time.json")
DECISION = Path("docs/announcement-time.md")
ACCEPTANCE = Path("docs/step-15-acceptance.md")
MIGRATIONS = Path("migrations")


def _announcement_fields(
    *, speech_date: str | None, speech_time: str | None
) -> dict[str, str | None]:
    from xbrlswarm.domain import announcement_event_fields

    return announcement_event_fields(
        speech_date=speech_date,
        speech_time=speech_time,
    )


def _database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    for path in sorted(MIGRATIONS.glob("*.sql")):
        connection.executescript(path.read_text(encoding="utf-8"))
    connection.execute(
        """INSERT INTO task (stock_id, fiscal_year, report_period, state, engine)
           VALUES ('2330', 2024, 'Q1', 'undone', 'goodinfo')"""
    )
    return connection


def test_explicit_speech_fields_map_to_announcement_event() -> None:
    assert _announcement_fields(
        speech_date="2024-05-10", speech_time="14:48:53"
    ) == {
        "evidence_type": "material_announcement",
        "event_date": "2024-05-10",
        "event_time": "14:48:53",
        "event_precision": "second",
    }


@pytest.mark.parametrize(
    "speech_date,speech_time",
    [
        (None, "14:48:53"),
        ("2024-05-10", None),
        ("", "14:48:53"),
        ("2024-05-10", ""),
        ("  ", "14:48:53"),
        ("2024-05-10", "  "),
    ],
)
def test_incomplete_speech_fields_cannot_form_announcement_at(
    speech_date: str | None, speech_time: str | None
) -> None:
    with pytest.raises(ValueError, match="發言日期與發言時間"):
        _announcement_fields(speech_date=speech_date, speech_time=speech_time)


def test_announcement_time_round_trips_separately_from_retrieval_time() -> None:
    connection = _database()
    fields = _announcement_fields(
        speech_date="2024-05-10", speech_time="14:48:53"
    )
    connection.execute(
        """
        INSERT INTO evidence (
            task_id, evidence_type, event_date, event_time, event_precision,
            source_type, source_locator, retrieved_at, verification_state
        ) VALUES (1, :evidence_type, :event_date, :event_time, :event_precision,
                  'goodinfo', 'goodinfo:2330:2024-05-10T14:48:53',
                  '2026-09-23T01:02:03.000Z', 'unverified')
        """,
        fields,
    )

    assert connection.execute(
        """
        SELECT evidence_type, event_date, event_time, event_precision, retrieved_at
        FROM evidence
        """
    ).fetchone() == (
        "material_announcement",
        "2024-05-10",
        "14:48:53",
        "second",
        "2026-09-23T01:02:03.000Z",
    )


def test_announcement_query_excludes_document_events() -> None:
    connection = _database()
    fields = _announcement_fields(
        speech_date="2024-05-10", speech_time="14:48:53"
    )
    connection.execute(
        """
        INSERT INTO evidence (
            task_id, evidence_type, event_date, event_time, event_precision,
            source_type, source_locator, retrieved_at, verification_state
        ) VALUES (1, :evidence_type, :event_date, :event_time, :event_precision,
                  'goodinfo', 'goodinfo:announcement',
                  '2026-09-23T01:02:03.000Z', 'unverified')
        """,
        fields,
    )
    connection.execute(
        """
        INSERT INTO evidence (
            task_id, evidence_type, event_date, event_time,
            source_type, source_locator, retrieved_at, raw_payload_hash,
            verification_state
        ) VALUES (1, 'xbrl_document', '2024-05-10', '14:48:53',
                  'mops', 'mops:document', '2026-09-23T01:02:03.000Z',
                  'sha256:other', 'unverified')
        """
    )

    assert connection.execute(
        """
        SELECT COUNT(*) FROM evidence
        WHERE evidence_type = 'material_announcement'
          AND event_date IS NOT NULL AND event_time IS NOT NULL
        """
    ).fetchone()[0] == 1


def test_contract_specifies_equivalent_schema_and_source_boundary() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    assert contract == {
        "contract": "announcement_time",
        "version": 2,
        "source_fields": ["speech_date", "speech_time"],
        "requires_explicit_source_claim": True,
        "requires_both_fields": True,
        "evidence_mapping": {
            "evidence_type": "material_announcement",
            "event_date": "speech_date",
            "event_time": "speech_time",
            "event_precision": "second",
        },
        "excluded_substitutes": [
            "article_published_at",
            "retrieved_at",
            "xbrl_confirmed_at",
        ],
        "event_precision_contract": "event-time-precision",
    }


def test_step15_documents_semantics_and_no_new_migration() -> None:
    decision = DECISION.read_text(encoding="utf-8")
    acceptance = ACCEPTANCE.read_text(encoding="utf-8")

    assert "announcement_at" in decision
    assert "material_announcement" in decision
    assert "retrieved_at" in decision
    assert "xbrl_confirmed_at" in decision
    assert "不需要 migration" in acceptance
