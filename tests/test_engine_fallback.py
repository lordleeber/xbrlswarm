import json
import sqlite3
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pytest

from xbrlswarm.domain import PAUSED_ENGINES, Engine, next_active_engine, next_engine
from xbrlswarm.worker_api import TaskStore, create_app


NOW = datetime(2026, 9, 24, 1, 2, 3, tzinfo=timezone.utc)
ORDER = ["mops", "goodinfo", "yahoo", "google", "grounded_ai"]


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "fallback.sqlite"
    with sqlite3.connect(path) as connection:
        for migration in sorted(Path("migrations").glob("*.sql")):
            connection.executescript(migration.read_text(encoding="utf-8"))
        connection.execute(
            """INSERT INTO task (stock_id, fiscal_year, report_period, state, engine)
               VALUES ('0050', 2024, 'Q1', 'undone', 'mops')"""
        )
    return path


def _row(path: Path):
    with sqlite3.connect(path) as connection:
        return connection.execute(
            """SELECT state, engine, attempts, fail_count, worker_id,
                      dispatched_at, retry_at FROM task"""
        ).fetchone()


def test_domain_order_has_only_roadmap_engines() -> None:
    assert [engine.value for engine in Engine] == ORDER
    assert [next_engine(engine) for engine in list(Engine)[:-1]] == list(Engine)[1:]
    assert next_engine(Engine.GROUNDED_AI) is None


def test_goodinfo_is_paused_and_skipped_without_changing_fixed_order() -> None:
    assert PAUSED_ENGINES == frozenset({Engine.GOODINFO})
    assert next_engine(Engine.MOPS) is Engine.GOODINFO
    assert next_active_engine(Engine.MOPS) is Engine.YAHOO
    assert next_active_engine(Engine.GOODINFO) is Engine.YAHOO
    assert next_active_engine(Engine.YAHOO) is Engine.GOOGLE
    assert next_active_engine(Engine.GROUNDED_AI) is None
    assert next_active_engine(Engine.MOPS, paused=frozenset()) is Engine.GOODINFO
    assert next_active_engine(
        Engine.MOPS, paused=frozenset({Engine.GOODINFO, Engine.YAHOO})
    ) is Engine.GOOGLE
    with pytest.raises(ValueError):
        next_active_engine("mops")


@pytest.mark.parametrize("outcome", ["not_found", "rejected"])
def test_mops_exhaustion_skips_paused_goodinfo_to_yahoo_on_next_lease(
    tmp_path: Path, outcome: str
) -> None:
    database = _database(tmp_path)
    store = TaskStore(database, clock=lambda: NOW)
    first = store.lease("worker-1")
    assert first["engine"] == "mops"
    assert store.complete(first["task_id"], "worker-1", 1, outcome)
    assert _row(database) == (outcome, "mops", 1, 0, None, None, None)

    second = store.lease("worker-2")
    assert second["task_id"] == first["task_id"]
    assert second["engine"] == "yahoo"
    assert second["lease_attempt"] == 2
    assert _row(database) == (
        "dispatched", "yahoo", 2, 0, "worker-2",
        "2026-09-24T01:02:03.000Z", None,
    )


@pytest.mark.parametrize("engine", ORDER[1:-1])
def test_unenabled_downstream_engine_is_not_dispatched(
    tmp_path: Path, engine: str
) -> None:
    database = _database(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE task SET state = 'rejected', engine = ?", (engine,))
    store = TaskStore(database, clock=lambda: NOW)
    assert store.lease("worker-2") is None
    assert _row(database) == ("rejected", engine, 0, 0, None, None, None)


def test_retryable_failure_stays_on_engine_before_semantic_fallback(tmp_path: Path) -> None:
    database = _database(tmp_path)
    store = TaskStore(database, retry_delay_seconds=60, clock=lambda: NOW)
    first = store.lease("worker-1")
    assert store.complete(first["task_id"], "worker-1", 1, "transport_error")
    assert store.lease("worker-2") is None
    assert _row(database)[:4] == ("transport_error", "mops", 1, 1)


def test_mops_exhaustion_preserves_counters_and_targeted_lease(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """UPDATE task SET state = 'rejected', attempts = 4, fail_count = 2
               WHERE id = 1"""
        )
        connection.execute(
            """INSERT INTO task (stock_id, fiscal_year, report_period, state, engine)
               VALUES ('0051', 2024, 'Q1', 'undone', 'mops')"""
        )
    store = TaskStore(database, clock=lambda: NOW)
    second = store.lease("worker-2", task_id=2)
    assert second["task_id"] == 2
    assert second["engine"] == "mops"
    assert _row(database)[:4] == ("undone", "yahoo", 4, 2)
    first = store.lease("worker-3", task_id=1)
    assert first["engine"] == "yahoo"
    assert first["lease_attempt"] == 5
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT fail_count FROM task WHERE id = 1"
        ).fetchone() == (2,)


def test_mops_advance_and_dispatch_roll_back_together(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE task SET state = 'not_found' WHERE id = 1")
        connection.execute(
            """CREATE TRIGGER fail_yahoo_dispatch BEFORE UPDATE ON task
               WHEN NEW.state = 'dispatched' AND NEW.engine = 'yahoo'
               BEGIN SELECT RAISE(ABORT, 'test dispatch failure'); END"""
        )
    store = TaskStore(database, clock=lambda: NOW)
    with pytest.raises(sqlite3.IntegrityError, match="test dispatch failure"):
        store.lease("worker-2")
    assert _row(database) == ("not_found", "mops", 0, 0, None, None, None)


@pytest.mark.parametrize("state", ["undone", "not_found", "rejected"])
def test_existing_goodinfo_tasks_are_neither_migrated_nor_dispatched_while_paused(
    tmp_path: Path, state: str
) -> None:
    database = _database(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE task SET state = ?, engine = 'goodinfo'", (state,)
        )
        connection.execute(
            """INSERT INTO task (stock_id, fiscal_year, report_period, state, engine)
               VALUES ('0051', 2024, 'Q1', 'rejected', 'mops')"""
        )
    store = TaskStore(database, clock=lambda: NOW)
    grant = store.lease("worker-2")
    assert grant["task_id"] == 2
    assert grant["engine"] == "yahoo"
    assert store.lease("worker-3") is None
    assert store.lease("worker-3", task_id=1) is None
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT state, engine, attempts, worker_id FROM task WHERE id = 1"
        ).fetchone() == (state, "goodinfo", 0, None)


def test_paused_goodinfo_task_is_not_redispatched_after_retry_or_lease_expiry(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """UPDATE task SET engine = 'goodinfo', state = 'dispatched',
                   worker_id = 'old', dispatched_at = '2026-09-24T00:00:00.000Z',
                   attempts = 3"""
        )
        connection.execute(
            """INSERT INTO task (stock_id, fiscal_year, report_period, state,
                                 engine, retry_at, fail_count)
               VALUES ('0051', 2024, 'Q1', 'temporary_error', 'goodinfo',
                       '2026-09-24T00:00:00.000Z', 2)"""
        )
    store = TaskStore(database, clock=lambda: NOW)
    assert store.lease("worker-2") is None
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT state, engine, attempts, fail_count FROM task ORDER BY id"
        ).fetchall() == [("undone", "goodinfo", 3, 0), ("undone", "goodinfo", 0, 2)]


def test_completed_task_does_not_fallback(tmp_path: Path) -> None:
    database = _database(tmp_path)
    store = TaskStore(database, clock=lambda: NOW)
    grant = store.lease("worker-1")
    assert store.complete(grant["task_id"], "worker-1", 1, "success")
    assert store.lease("worker-2") is None
    assert _row(database)[:4] == ("completed", "mops", 1, 0)


def test_terminal_transition_and_dispatch_roll_back_together(tmp_path: Path) -> None:
    database = _database(tmp_path)
    store = TaskStore(database, clock=lambda: NOW)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE task SET state = 'not_found', engine = 'grounded_ai'"
        )
        connection.execute(
            """INSERT INTO task (stock_id, fiscal_year, report_period, state, engine)
               VALUES ('0051', 2024, 'Q1', 'undone', 'mops')"""
        )
    with sqlite3.connect(database) as connection:
        before = connection.execute(
            "SELECT id, state, engine, attempts FROM task ORDER BY id"
        ).fetchall()
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TRIGGER fail_dispatch BEFORE UPDATE ON task
               WHEN NEW.state = 'dispatched' AND NEW.stock_id = '0051'
               BEGIN SELECT RAISE(ABORT, 'test dispatch failure'); END"""
        )
    with pytest.raises(sqlite3.IntegrityError, match="test dispatch failure"):
        store.lease("worker-2")
    with sqlite3.connect(database) as connection:
        after = connection.execute(
            "SELECT id, state, engine, attempts FROM task ORDER BY id"
        ).fetchall()
    assert after == before


def test_terminal_unresolved_is_visible_in_status(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE task SET state = 'rejected', engine = 'grounded_ai'"
        )
    app = create_app(TaskStore(database, clock=lambda: NOW))
    response = {}

    def call(path: str):
        def start_response(status, headers):
            response["status"] = status

        return b"".join(app({
            "PATH_INFO": path, "REQUEST_METHOD": "GET", "wsgi.input": BytesIO(),
        }, start_response))

    assert TaskStore(database, clock=lambda: NOW).lease("worker-1") is None
    status = call("/status").decode()
    assert response["status"] == "200 OK"
    assert "Tasks: 1\n" in status
    assert "Terminal Unresolved: 1\n" in status
    assert json.loads(call("/stats"))["by_state"] == {"terminal_unresolved": 1}


def test_contract_documents_order_and_terminal_state() -> None:
    contract = json.loads(Path("contracts/engine-fallback.json").read_text())
    assert contract["engine_order"] == ORDER
    assert contract["advance_states"] == ["not_found", "rejected"]
    assert contract["terminal_state"] == "terminal_unresolved"
    assert contract["runtime_fallback_enabled"] is True
    assert contract["enabled_transitions"] == [{"from": "mops", "to": "yahoo"}]
    assert contract["paused_engines"] == sorted(engine.value for engine in PAUSED_ENGINES)
    assert contract["paused_engine_tasks_migrated"] is False
    assert contract["paused_engine_tasks_dispatched"] is False
    assert all(
        transition["to"] not in contract["paused_engines"]
        for transition in contract["enabled_transitions"]
    )
    assert "pending" in Path("docs/engine-fallback.md").read_text()
    assert "terminal_unresolved" in Path("docs/engine-fallback.md").read_text()
