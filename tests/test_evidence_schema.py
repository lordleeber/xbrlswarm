import json
import sqlite3
from pathlib import Path

import pytest

from xbrlswarm.domain import EvidenceType


MIGRATIONS_DIR = Path("migrations")
EVIDENCE_MIGRATION_PATH = Path("migrations/0003_create_evidence.sql")
SOURCE_MATRIX_PATH = Path("discovery/source_field_matrix.json")
DECISION_PATH = Path("docs/evidence-schema.md")
ACCEPTANCE_PATH = Path("docs/step-10-acceptance.md")


def _apply(connection: sqlite3.Connection, path: Path) -> None:
    connection.executescript(path.read_text(encoding="utf-8"))


def _database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        _apply(connection, path)
    return connection


def _insert_task(connection: sqlite3.Connection, *, engine: str = "mops") -> int:
    cursor = connection.execute(
        """
        INSERT INTO task (stock_id, fiscal_year, report_period, state, engine)
        VALUES ('2330', 2024, 'Q1', 'undone', ?)
        """,
        (engine,),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _insert_evidence(
    connection: sqlite3.Connection,
    *,
    task_id: int,
    evidence_type: str = "xbrl_document",
    source_type: str = "mops",
    retrieved_at: str = "2026-09-23T04:05:06.000Z",
    verification_state: str = "unverified",
) -> None:
    connection.execute(
        """
        INSERT INTO evidence (
            task_id,
            evidence_type,
            source_type,
            retrieved_at,
            verification_state
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            task_id,
            evidence_type,
            source_type,
            retrieved_at,
            verification_state,
        ),
    )


def test_evidence_table_preserves_the_step10_core_columns() -> None:
    connection = _database()
    columns = connection.execute("PRAGMA table_info(evidence)").fetchall()

    core_columns = [
        "id",
        "task_id",
        "evidence_type",
        "event_date",
        "event_time",
        "event_precision",
        "source_type",
        "source_endpoint",
        "source_url",
        "source_locator",
        "source_title",
        "source_subject",
        "retrieved_at",
        "raw_payload_hash",
        "verification_state",
    ]
    assert [column[1] for column in columns[: len(core_columns)]] == core_columns
    assert {column[1]: column[2] for column in columns if column[1] in core_columns} == {
        "id": "INTEGER",
        "task_id": "INTEGER",
        "evidence_type": "TEXT",
        "event_date": "TEXT",
        "event_time": "TEXT",
        "event_precision": "TEXT",
        "source_type": "TEXT",
        "source_endpoint": "TEXT",
        "source_url": "TEXT",
        "source_locator": "TEXT",
        "source_title": "TEXT",
        "source_subject": "TEXT",
        "retrieved_at": "TEXT",
        "raw_payload_hash": "TEXT",
        "verification_state": "TEXT",
    }
    assert next(column for column in columns if column[1] == "id")[5] == 1
    assert {column[1] for column in columns if column[3]} == {
        "task_id",
        "evidence_type",
        "source_type",
        "retrieved_at",
        "verification_state",
    }
    assert "xbrl_confirmed_at" not in {column[1] for column in columns}
    assert "published_at" not in {column[1] for column in columns}


def test_evidence_table_uses_sqlite_strict_typing() -> None:
    connection = _database()
    evidence = next(
        row
        for row in connection.execute("PRAGMA table_list('evidence')")
        if row[1] == "evidence"
    )

    assert evidence[5] == 1


def test_evidence_type_constraint_matches_the_domain_enum() -> None:
    connection = _database()
    task_id = _insert_task(connection)

    for evidence_type in EvidenceType:
        _insert_evidence(
            connection,
            task_id=task_id,
            evidence_type=evidence_type.value,
        )

    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        _insert_evidence(connection, task_id=task_id, evidence_type="article")


def test_evidence_task_foreign_key_is_restrictive() -> None:
    connection = _database()
    foreign_keys = connection.execute("PRAGMA foreign_key_list(evidence)").fetchall()

    assert [
        (row[2], row[3], row[4], row[6]) for row in foreign_keys
    ] == [("task", "task_id", "id", "RESTRICT")]
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        _insert_evidence(connection, task_id=999)

    task_id = _insert_task(connection)
    _insert_evidence(connection, task_id=task_id)
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
        connection.execute("DELETE FROM task WHERE id = ?", (task_id,))


def test_optional_source_event_and_payload_fields_default_to_null() -> None:
    connection = _database()
    task_id = _insert_task(connection)
    _insert_evidence(connection, task_id=task_id)

    row = connection.execute(
        """
        SELECT
            event_date,
            event_time,
            event_precision,
            source_endpoint,
            source_url,
            source_locator,
            source_title,
            source_subject,
            raw_payload_hash
        FROM evidence
        """
    ).fetchone()

    assert row == (None,) * 9


def test_not_verified_source_fields_do_not_enter_the_production_schema() -> None:
    connection = _database()
    columns = {row[1] for row in connection.execute("PRAGMA table_info(evidence)")}
    matrix = json.loads(SOURCE_MATRIX_PATH.read_text(encoding="utf-8"))
    not_verified = {
        field["field"]
        for field in matrix["fields"]
        if field["status"] == "not_verified"
    }

    assert "filing_kind" in not_verified
    assert columns.isdisjoint(not_verified)


def test_engine_evidence_type_source_and_verification_are_separate_dimensions() -> None:
    connection = _database()
    task_id = _insert_task(connection, engine="google")
    _insert_evidence(
        connection,
        task_id=task_id,
        evidence_type="material_announcement",
        source_type="cnyes",
        verification_state="corroborated",
    )

    row = connection.execute(
        """
        SELECT task.engine, evidence.evidence_type, evidence.source_type,
               evidence.verification_state
        FROM evidence
        JOIN task ON task.id = evidence.task_id
        """
    ).fetchone()

    assert row == ("google", "material_announcement", "cnyes", "corroborated")


def test_step10_does_not_guess_a_logical_evidence_unique_key() -> None:
    connection = _database()
    task_id = _insert_task(connection)

    _insert_evidence(connection, task_id=task_id)
    _insert_evidence(connection, task_id=task_id)

    assert connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 2
    assert [row for row in connection.execute("PRAGMA index_list(evidence)") if row[2]] == []


@pytest.mark.parametrize(
    "field",
    ["source_type", "retrieved_at", "verification_state"],
)
def test_required_evidence_metadata_rejects_empty_text(field: str) -> None:
    connection = _database()
    task_id = _insert_task(connection)

    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        _insert_evidence(connection, task_id=task_id, **{field: ""})


def test_evidence_task_id_rejects_non_integer_values() -> None:
    connection = _database()

    with pytest.raises(sqlite3.IntegrityError, match="INTEGER column"):
        _insert_evidence(connection, task_id="abc")


def test_evidence_migration_preserves_existing_task_data() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    earlier_migrations = [
        path
        for path in sorted(MIGRATIONS_DIR.glob("*.sql"))
        if path < EVIDENCE_MIGRATION_PATH
    ]
    for path in earlier_migrations:
        _apply(connection, path)
    task_id = _insert_task(connection, engine="yahoo")
    before = connection.execute("SELECT * FROM task").fetchall()

    _apply(connection, EVIDENCE_MIGRATION_PATH)

    assert connection.execute("SELECT * FROM task").fetchall() == before
    _insert_evidence(connection, task_id=task_id, source_type="yahoo")


def test_step10_documents_nullability_and_semantic_boundaries() -> None:
    decision = DECISION_PATH.read_text(encoding="utf-8")
    acceptance = ACCEPTANCE_PATH.read_text(encoding="utf-8")

    assert "xbrl_confirmed_at" in decision
    assert "published_at" in decision
    assert "source_type" in decision
    assert "retrieved_at" in decision
    assert "filing_kind" in decision
    assert "verification_state" in decision
    assert "Step-12" in decision
    assert "0003_create_evidence.sql" in acceptance
