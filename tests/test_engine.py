import json
import sqlite3
from pathlib import Path

import pytest

from xbrlswarm.domain import Engine


FIRST_MIGRATION_PATH = Path("migrations/0001_create_task.sql")
ENGINE_MIGRATION_PATH = Path("migrations/0002_define_engine_enum.sql")
CONTRACT_PATH = Path("contracts/engines.json")
DECISION_PATH = Path("docs/engines.md")
ACCEPTANCE_PATH = Path("docs/step-9-acceptance.md")


def _apply(connection: sqlite3.Connection, path: Path) -> None:
    connection.executescript(path.read_text(encoding="utf-8"))


def _database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    _apply(connection, FIRST_MIGRATION_PATH)
    _apply(connection, ENGINE_MIGRATION_PATH)
    return connection


def _insert_task(
    connection: sqlite3.Connection,
    *,
    stock_id: str = "2330",
    engine: str = "mops",
) -> None:
    connection.execute(
        """
        INSERT INTO task (stock_id, fiscal_year, report_period, state, engine)
        VALUES (?, 2024, 'Q1', 'undone', ?)
        """,
        (stock_id, engine),
    )


def test_engine_has_only_the_five_fixed_values() -> None:
    assert tuple(engine.value for engine in Engine) == (
        "mops",
        "goodinfo",
        "yahoo",
        "google",
        "grounded_ai",
    )


def test_engine_parser_returns_canonical_values_and_rejects_unknown_values() -> None:
    assert Engine.parse("MOPS") is Engine.MOPS
    assert Engine.parse("grounded_ai") is Engine.GROUNDED_AI

    for value in ("bing", "manual_review", "", "grounded-ai"):
        with pytest.raises(ValueError, match="無效的 engine"):
            Engine.parse(value)


def test_machine_readable_contract_matches_domain_enum() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    assert contract == {
        "contract": "engines",
        "version": 1,
        "values": [engine.value for engine in Engine],
    }


def test_task_table_accepts_each_engine_and_rejects_other_values() -> None:
    connection = _database()

    for index, engine in enumerate(Engine):
        _insert_task(connection, stock_id=f"{index:04d}", engine=engine.value)

    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        _insert_task(connection, stock_id="9998", engine="bing")
    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        _insert_task(connection, stock_id="9999", engine="MOPS")


def test_engine_migration_preserves_existing_task_data_and_strict_typing() -> None:
    connection = sqlite3.connect(":memory:")
    _apply(connection, FIRST_MIGRATION_PATH)
    connection.execute(
        """
        INSERT INTO task (
            id,
            stock_id,
            fiscal_year,
            report_period,
            state,
            engine,
            attempts,
            fail_count,
            dispatched_at,
            worker_id,
            created_at,
            updated_at
        ) VALUES (
            42,
            '0050',
            2024,
            'FY',
            'dispatched',
            'goodinfo',
            3,
            1,
            '2026-09-23T01:02:03.000Z',
            'worker-7',
            '2026-09-23T00:00:00.000Z',
            '2026-09-23T01:02:03.000Z'
        )
        """
    )
    before = connection.execute("SELECT * FROM task").fetchone()

    _apply(connection, ENGINE_MIGRATION_PATH)

    assert connection.execute("SELECT * FROM task").fetchone() == before
    task = next(
        row for row in connection.execute("PRAGMA table_list('task')") if row[1] == "task"
    )
    assert task[5] == 1


def test_engine_migration_rejects_preexisting_unknown_engine_without_data_loss() -> None:
    connection = sqlite3.connect(":memory:")
    _apply(connection, FIRST_MIGRATION_PATH)
    _insert_task(connection, engine="bing")
    connection.commit()

    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        _apply(connection, ENGINE_MIGRATION_PATH)
    connection.rollback()

    assert connection.execute("SELECT engine FROM task").fetchone()[0] == "bing"


def test_step9_documents_enum_and_scope_boundaries() -> None:
    decision = DECISION_PATH.read_text(encoding="utf-8")
    acceptance = ACCEPTANCE_PATH.read_text(encoding="utf-8")

    for value in Engine:
        assert value.value in decision
    assert "task.engine" in decision
    assert "source_type" in decision
    assert "fallback" in decision
    assert "state transition" in decision
    assert "0002_define_engine_enum.sql" in acceptance
