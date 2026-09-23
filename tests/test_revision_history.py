import json
import sqlite3
from pathlib import Path

import pytest

from xbrlswarm.domain import RevisionKind


MIGRATIONS = Path("migrations")
STEP14_MIGRATION = MIGRATIONS / "0006_preserve_evidence_history.sql"
MATRIX = Path("discovery/source_field_matrix.json")
OBSERVATIONS = Path("discovery/mops_field_observations.json")
CONTRACT = Path("contracts/revision-kinds.json")
DECISION = Path("docs/revision-history.md")
ACCEPTANCE = Path("docs/step-14-acceptance.md")


def database(*, through_step13: bool = False) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if through_step13 and path >= STEP14_MIGRATION:
            continue
        connection.executescript(path.read_text(encoding="utf-8"))
    connection.execute(
        """INSERT INTO task (stock_id, fiscal_year, report_period, state, engine)
           VALUES ('2330', 2024, 'Q1', 'undone', 'mops')"""
    )
    return connection


def add_evidence(
    connection: sqlite3.Connection,
    *,
    payload_hash: str = "sha256:original",
    locator: str = "mops:2330:2024:Q1",
) -> int:
    cursor = connection.execute(
        """
        INSERT INTO evidence (
            task_id, evidence_type, source_type, source_locator,
            retrieved_at, raw_payload_hash, verification_state
        ) VALUES (1, 'xbrl_document', 'mops', ?,
                  '2026-09-23T01:02:03.000Z', ?, 'unverified')
        """,
        (locator, payload_hash),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def test_new_payload_is_appended_and_original_stays_intact() -> None:
    connection = database()
    original_id = add_evidence(connection)
    correction_id = add_evidence(connection, payload_hash="sha256:correction")

    assert correction_id != original_id
    assert connection.execute(
        "SELECT id, raw_payload_hash FROM evidence ORDER BY id"
    ).fetchall() == [
        (original_id, "sha256:original"),
        (correction_id, "sha256:correction"),
    ]


@pytest.mark.parametrize(
    "field,value",
    [
        ("raw_payload_hash", "sha256:correction"),
        ("source_locator", "mops:other"),
        ("source_subject", "更正公告"),
        ("event_date", "2026-09-23"),
        ("company_name", "其他名稱"),
        ("retrieved_at", "2026-09-24T01:02:03.000Z"),
    ],
)
def test_source_evidence_cannot_be_overwritten(field: str, value: str) -> None:
    connection = database()
    evidence_id = add_evidence(connection)
    before = connection.execute(
        "SELECT * FROM evidence WHERE id = ?", (evidence_id,)
    ).fetchone()

    with pytest.raises(sqlite3.IntegrityError, match="immutable source evidence"):
        connection.execute(
            f"UPDATE evidence SET {field} = ? WHERE id = ?", (value, evidence_id)
        )

    assert connection.execute(
        "SELECT * FROM evidence WHERE id = ?", (evidence_id,)
    ).fetchone() == before


def test_source_evidence_cannot_be_deleted() -> None:
    connection = database()
    evidence_id = add_evidence(connection)

    with pytest.raises(sqlite3.IntegrityError, match="immutable source evidence"):
        connection.execute("DELETE FROM evidence WHERE id = ?", (evidence_id,))

    assert connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 1


def test_verification_state_can_be_updated_without_rewriting_source() -> None:
    connection = database()
    evidence_id = add_evidence(connection)

    connection.execute(
        "UPDATE evidence SET verification_state = 'corroborated' WHERE id = ?",
        (evidence_id,),
    )

    assert connection.execute(
        "SELECT raw_payload_hash, verification_state FROM evidence WHERE id = ?",
        (evidence_id,),
    ).fetchone() == ("sha256:original", "corroborated")


def test_migration_preserves_existing_evidence_and_installs_guards() -> None:
    connection = database(through_step13=True)
    evidence_id = add_evidence(connection)
    before = connection.execute(
        "SELECT * FROM evidence WHERE id = ?", (evidence_id,)
    ).fetchone()

    connection.executescript(STEP14_MIGRATION.read_text(encoding="utf-8"))

    assert connection.execute(
        "SELECT * FROM evidence WHERE id = ?", (evidence_id,)
    ).fetchone() == before
    with pytest.raises(sqlite3.IntegrityError, match="immutable source evidence"):
        connection.execute(
            "UPDATE evidence SET raw_payload_hash = 'sha256:other' WHERE id = ?",
            (evidence_id,),
        )


def test_unverified_filing_kind_is_not_added_to_production_schema() -> None:
    connection = database()
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    status = next(
        field["status"] for field in matrix["fields"]
        if field["field"] == "filing_kind"
    )
    columns = {row[1] for row in connection.execute("PRAGMA table_info(evidence)")}

    assert status == "not_verified"
    assert "filing_kind" not in columns


def test_revision_kind_contract_defaults_current_captures_to_unknown() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    observations = json.loads(OBSERVATIONS.read_text(encoding="utf-8"))
    report_types = {
        case["facts"]["tifrs-notes:ReportType"]
        for case in observations["cases"]
    }

    assert contract["values"] == [
        "original", "amendment", "supplemental", "unknown"
    ]
    assert contract["default"] == "unknown"
    assert contract["mops_report_type_rules"] == {
        "Financial report (general)": "unknown"
    }
    assert report_types == set(contract["mops_report_type_rules"])
    assert len(observations["cases"]) == 12


def test_revision_kind_domain_values_match_the_contract() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    assert [kind.value for kind in RevisionKind] == contract["values"]
    assert RevisionKind.UNKNOWN.value == contract["default"]


def test_revision_history_documents_the_source_gate() -> None:
    decision = DECISION.read_text(encoding="utf-8")
    acceptance = ACCEPTANCE.read_text(encoding="utf-8")

    assert "filing_kind" in decision
    assert "not_verified" in decision
    assert "unknown" in decision
    assert "immutable source evidence" in decision
    assert "0006_preserve_evidence_history.sql" in acceptance
