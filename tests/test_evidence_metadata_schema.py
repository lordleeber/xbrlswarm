import json
import sqlite3
from pathlib import Path


MIGRATIONS_DIR = Path("migrations")
EVIDENCE_MIGRATION_PATH = Path("migrations/0003_create_evidence.sql")
METADATA_MIGRATION_PATH = Path("migrations/0004_add_evidence_metadata.sql")
DECISION_PATH = Path("docs/evidence-schema.md")
ACCEPTANCE_PATH = Path("docs/step-11-acceptance.md")
SOURCE_MATRIX_PATH = Path("discovery/source_field_matrix.json")
OBSERVATIONS_PATH = Path("discovery/mops_field_observations.json")
STEP11_CANDIDATE_FIELDS = (
    "period_start",
    "period_end",
    "board_approved_date",
    "audit_committee_date",
    "company_name",
)
METADATA_FIELDS = ("company_name",)


def _apply(connection: sqlite3.Connection, path: Path) -> None:
    connection.executescript(path.read_text(encoding="utf-8"))


def _database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        _apply(connection, path)
    return connection


def _insert_task(connection: sqlite3.Connection) -> int:
    cursor = connection.execute(
        """
        INSERT INTO task (stock_id, fiscal_year, report_period, state, engine)
        VALUES ('2330', 2024, 'FY', 'undone', 'mops')
        """
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _insert_evidence(connection: sqlite3.Connection, task_id: int) -> int:
    cursor = connection.execute(
        """
        INSERT INTO evidence (
            task_id,
            evidence_type,
            source_type,
            retrieved_at,
            verification_state
        ) VALUES (?, 'xbrl_document', 'mops',
                  '2026-09-23T04:05:06.000Z', 'unverified')
        """,
        (task_id,),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def test_evidence_has_the_verified_step11_metadata_field_as_nullable_text() -> None:
    connection = _database()
    columns = {
        row[1]: {"type": row[2], "not_null": bool(row[3])}
        for row in connection.execute("PRAGMA table_info(evidence)")
    }

    assert {field: columns[field] for field in METADATA_FIELDS} == {
        field: {"type": "TEXT", "not_null": False}
        for field in METADATA_FIELDS
    }


def test_step11_schema_only_includes_candidates_that_pass_the_source_gate() -> None:
    connection = _database()
    schema_fields = {
        row[1] for row in connection.execute("PRAGMA table_info(evidence)")
    }
    matrix = json.loads(SOURCE_MATRIX_PATH.read_text(encoding="utf-8"))
    statuses = {item["field"]: item["status"] for item in matrix["fields"]}
    eligible_fields = {
        field
        for field in STEP11_CANDIDATE_FIELDS
        if statuses.get(field) in {"direct", "derived"}
    }

    assert eligible_fields == {"company_name"}
    assert schema_fields.intersection(STEP11_CANDIDATE_FIELDS) == eligible_fields


def test_step11_metadata_defaults_to_null_when_the_source_does_not_provide_it() -> None:
    connection = _database()
    evidence_id = _insert_evidence(connection, _insert_task(connection))

    row = connection.execute(
        f"SELECT {', '.join(METADATA_FIELDS)} FROM evidence WHERE id = ?",
        (evidence_id,),
    ).fetchone()

    assert row == (None,) * len(METADATA_FIELDS)


def test_company_name_round_trips_a_raw_observation_value() -> None:
    connection = _database()
    evidence_id = _insert_evidence(connection, _insert_task(connection))
    observations = json.loads(OBSERVATIONS_PATH.read_text(encoding="utf-8"))
    company_name = observations["cases"][0]["facts"][
        "tifrs-notes:CompanyChineseName"
    ]

    connection.execute(
        "UPDATE evidence SET company_name = ? WHERE id = ?",
        (company_name, evidence_id),
    )

    row = connection.execute(
        "SELECT company_name FROM evidence WHERE id = ?",
        (evidence_id,),
    ).fetchone()
    assert row == (company_name,)


def test_step11_migration_preserves_existing_evidence() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    earlier_migrations = [
        path
        for path in sorted(MIGRATIONS_DIR.glob("*.sql"))
        if path <= EVIDENCE_MIGRATION_PATH
    ]
    for path in earlier_migrations:
        _apply(connection, path)
    evidence_id = _insert_evidence(connection, _insert_task(connection))
    before = connection.execute(
        "SELECT * FROM evidence WHERE id = ?", (evidence_id,)
    ).fetchone()

    _apply(connection, METADATA_MIGRATION_PATH)

    after = connection.execute(
        "SELECT * FROM evidence WHERE id = ?", (evidence_id,)
    ).fetchone()
    assert after[: len(before)] == before
    assert after[len(before) :] == (None,) * len(METADATA_FIELDS)


def test_step11_documents_source_provenance_and_nullability_contract() -> None:
    decision = DECISION_PATH.read_text(encoding="utf-8")
    acceptance = ACCEPTANCE_PATH.read_text(encoding="utf-8")

    for field in STEP11_CANDIDATE_FIELDS:
        assert field in decision
        assert field in acceptance
    assert "來源明確提供" in decision
    assert "direct" in decision
    assert "derived" in decision
    assert "NULL" in decision
    assert "0004_add_evidence_metadata.sql" in acceptance
