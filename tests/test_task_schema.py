import json
import sqlite3
from pathlib import Path

import pytest


MIGRATION_PATH = Path("migrations/0001_create_task.sql")
IDENTITY_CONTRACT_PATH = Path("contracts/report-identity-candidate.json")
DECISION_PATH = Path("docs/task-schema.md")
ACCEPTANCE_PATH = Path("docs/step-8-acceptance.md")


def _database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(MIGRATION_PATH.read_text(encoding="utf-8"))
    return connection


def _insert_task(
    connection: sqlite3.Connection,
    *,
    stock_id: str = "2330",
    fiscal_year: int = 2024,
    report_period: str = "Q1",
    attempts: int = 0,
    fail_count: int = 0,
) -> None:
    connection.execute(
        """
        INSERT INTO task (
            stock_id,
            fiscal_year,
            report_period,
            state,
            engine,
            attempts,
            fail_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            stock_id,
            fiscal_year,
            report_period,
            "undone",
            "mops",
            attempts,
            fail_count,
        ),
    )


def test_task_table_has_only_the_step8_columns() -> None:
    connection = _database()
    columns = connection.execute("PRAGMA table_info(task)").fetchall()

    assert [column[1] for column in columns] == [
        "id",
        "stock_id",
        "fiscal_year",
        "report_period",
        "state",
        "engine",
        "attempts",
        "fail_count",
        "dispatched_at",
        "worker_id",
        "created_at",
        "updated_at",
    ]
    assert "report_scope" not in {column[1] for column in columns}
    assert {column[1]: column[2] for column in columns} == {
        "id": "INTEGER",
        "stock_id": "TEXT",
        "fiscal_year": "INTEGER",
        "report_period": "TEXT",
        "state": "TEXT",
        "engine": "TEXT",
        "attempts": "INTEGER",
        "fail_count": "INTEGER",
        "dispatched_at": "TEXT",
        "worker_id": "TEXT",
        "created_at": "TEXT",
        "updated_at": "TEXT",
    }
    assert next(column for column in columns if column[1] == "id")[5] == 1
    assert {column[1] for column in columns if column[3]} == {
        "stock_id",
        "fiscal_year",
        "report_period",
        "state",
        "engine",
        "attempts",
        "fail_count",
        "created_at",
        "updated_at",
    }


def test_task_identity_is_unique_and_preserves_stock_id_as_text() -> None:
    connection = _database()
    _insert_task(connection, stock_id="0050")

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        _insert_task(connection, stock_id="0050")

    stored_stock_id = connection.execute("SELECT stock_id FROM task").fetchone()[0]
    assert stored_stock_id == "0050"


def test_unique_constraint_matches_the_task_identity_contract() -> None:
    connection = _database()
    contract = json.loads(IDENTITY_CONTRACT_PATH.read_text(encoding="utf-8"))
    unique_indexes = [
        row[1]
        for row in connection.execute("PRAGMA index_list(task)")
        if row[2] == 1
    ]
    unique_fields = [
        [
            row[0]
            for row in connection.execute(
                "SELECT name FROM pragma_index_info(?) ORDER BY seqno", (index,)
            )
        ]
        for index in unique_indexes
    ]

    assert contract["fields"] in unique_fields
    assert contract["report_scope_decision"]["included"] is False


@pytest.mark.parametrize("report_period", ["Q1", "Q2", "Q3", "FY"])
def test_task_accepts_each_canonical_report_period(report_period: str) -> None:
    connection = _database()

    _insert_task(connection, report_period=report_period)


def test_task_rejects_q4_and_negative_counters() -> None:
    connection = _database()

    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        _insert_task(connection, report_period="Q4")
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        _insert_task(connection, attempts=-1)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        _insert_task(connection, fail_count=-1)


def test_new_task_defaults_counters_timestamps_and_empty_lease() -> None:
    connection = _database()
    connection.execute(
        """
        INSERT INTO task (stock_id, fiscal_year, report_period, state, engine)
        VALUES ('2330', 2024, 'FY', 'undone', 'mops')
        """
    )

    row = connection.execute(
        """
        SELECT attempts, fail_count, dispatched_at, worker_id, created_at, updated_at
        FROM task
        """
    ).fetchone()

    assert row[0:4] == (0, 0, None, None)
    assert row[4]
    assert row[5]


def test_step8_documents_schema_decisions_and_boundaries() -> None:
    decision = DECISION_PATH.read_text(encoding="utf-8")
    acceptance = ACCEPTANCE_PATH.read_text(encoding="utf-8")

    assert "(stock_id, fiscal_year, report_period)" in decision
    assert "report_scope" in decision
    assert "Step-9" in decision
    assert "lease" in decision
    assert "不建立 evidence table" in decision
    assert "先因 `migrations/0001_create_task.sql` 尚不存在而失敗" in acceptance
