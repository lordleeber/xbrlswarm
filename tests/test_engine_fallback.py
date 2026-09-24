import json
import sqlite3
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pytest

from xbrlswarm.domain import Engine, next_engine
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


@pytest.mark.parametrize("outcome", ["not_found", "rejected"])
def test_semantic_exhaustion_advances_one_engine_per_result(
    tmp_path: Path, outcome: str
) -> None:
    database = _database(tmp_path)
    store = TaskStore(database, clock=lambda: NOW)
    first = store.lease("worker-1")
    assert first["engine"] == "mops"
    assert store.complete(first["task_id"], "worker-1", 1, outcome)
    assert _row(database) == (outcome, "mops", 1, 0, None, None, None)

    second = store.lease("worker-2")
    assert (second["task_id"], second["engine"], second["lease_attempt"]) == (
        first["task_id"], "goodinfo", 2
    )
    assert _row(database)[:4] == ("dispatched", "goodinfo", 2, 0)
    assert not store.complete(first["task_id"], "worker-1", 1, "success")


def test_full_order_terminates_after_grounded_ai_exhaustion(tmp_path: Path) -> None:
    database = _database(tmp_path)
    store = TaskStore(database, clock=lambda: NOW)
    for attempt, engine in enumerate(ORDER, start=1):
        grant = store.lease(f"worker-{attempt}")
        assert (grant["engine"], grant["lease_attempt"]) == (engine, attempt)
        outcome = "not_found" if attempt % 2 else "rejected"
        assert store.complete(grant["task_id"], grant["worker_id"], attempt, outcome)
    assert _row(database)[:4] == ("not_found", "grounded_ai", 5, 0)
    assert store.lease("worker-6") is None
    assert _row(database) == ("terminal_unresolved", "grounded_ai", 5, 0, None, None, None)
    assert store.lease("worker-7") is None


def test_retryable_failure_stays_on_engine_before_semantic_fallback(tmp_path: Path) -> None:
    database = _database(tmp_path)
    store = TaskStore(database, retry_delay_seconds=60, clock=lambda: NOW)
    first = store.lease("worker-1")
    assert store.complete(first["task_id"], "worker-1", 1, "transport_error")
    assert store.lease("worker-2") is None
    assert _row(database)[:4] == ("transport_error", "mops", 1, 1)


def test_completed_task_does_not_fallback(tmp_path: Path) -> None:
    database = _database(tmp_path)
    store = TaskStore(database, clock=lambda: NOW)
    grant = store.lease("worker-1")
    assert store.complete(grant["task_id"], "worker-1", 1, "success")
    assert store.lease("worker-2") is None
    assert _row(database)[:4] == ("completed", "mops", 1, 0)


def test_fallback_and_dispatch_roll_back_together(tmp_path: Path) -> None:
    database = _database(tmp_path)
    store = TaskStore(database, clock=lambda: NOW)
    grant = store.lease("worker-1")
    assert store.complete(grant["task_id"], "worker-1", 1, "not_found")
    before = _row(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TRIGGER fail_fallback_dispatch BEFORE UPDATE ON task
               WHEN NEW.state = 'dispatched' AND NEW.engine = 'goodinfo'
               BEGIN SELECT RAISE(ABORT, 'test fallback dispatch failure'); END"""
        )
    with pytest.raises(sqlite3.IntegrityError, match="test fallback dispatch failure"):
        store.lease("worker-2")
    assert _row(database) == before


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
    assert "terminal_unresolved" in Path("docs/engine-fallback.md").read_text()
