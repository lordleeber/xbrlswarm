import json
import sqlite3
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import pytest

from xbrlswarm.worker_api import TaskStore, create_app
from xbrlswarm.domain import SemanticExhaustion


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "semantic.sqlite"
    with sqlite3.connect(path) as connection:
        for migration in sorted(Path("migrations").glob("*.sql")):
            connection.executescript(migration.read_text(encoding="utf-8"))
        connection.execute(
            """INSERT INTO task (stock_id, fiscal_year, report_period, state, engine)
               VALUES ('0050', 2024, 'Q1', 'undone', 'mops')"""
        )
    return path


def _post(app, path: str, payload: dict):
    raw = json.dumps(payload).encode()
    response = {}

    def start_response(status, headers):
        response["status"] = status

    body = b"".join(app({
        "PATH_INFO": path,
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": "application/json",
        "CONTENT_LENGTH": str(len(raw)),
        "wsgi.input": BytesIO(raw),
    }, start_response))
    return response["status"], json.loads(body) if body else None


def _status(app) -> tuple[str, str]:
    response = {}

    def start_response(status, headers):
        response["status"] = status

    body = b"".join(app({
        "PATH_INFO": "/status", "REQUEST_METHOD": "GET",
    }, start_response))
    return response["status"], body.decode()


@pytest.mark.parametrize("outcome", ["not_found", "rejected"])
def test_semantic_exhaustion_ends_current_lease_without_changing_engine(
    tmp_path: Path, outcome: str
) -> None:
    database = _database(tmp_path)
    app = create_app(TaskStore(database))
    _, grant = _post(app, "/lease", {"worker_id": "worker-1"})
    task = grant["task"]
    result = {
        "task_id": task["task_id"], "worker_id": task["worker_id"],
        "lease_attempt": task["lease_attempt"], "outcome": outcome,
    }
    status, payload = _post(app, "/result", result)
    assert (status, payload) == (
        "200 OK", {"task_id": task["task_id"], "state": outcome}
    )
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            """SELECT state, engine, worker_id, dispatched_at, attempts,
                      fail_count, updated_at FROM task"""
        ).fetchone()
    assert row[:6] == (outcome, "mops", None, None, 1, 0)
    assert row[6] is not None
    assert _post(app, "/result", result) == (
        "409 Conflict", {"error": "lease_not_current"}
    )
    assert _post(app, "/lease", {"worker_id": "worker-2"}) == (
        "204 No Content", None
    )


@pytest.mark.parametrize("outcome", ["not_found", "rejected"])
def test_status_includes_semantic_exhaustion_state(
    tmp_path: Path, outcome: str
) -> None:
    app = create_app(TaskStore(_database(tmp_path)))
    _, grant = _post(app, "/lease", {"worker_id": "worker-1"})
    task = grant["task"]
    result = {
        "task_id": task["task_id"], "worker_id": task["worker_id"],
        "lease_attempt": task["lease_attempt"], "outcome": outcome,
    }
    assert _post(app, "/result", result)[0] == "200 OK"
    assert _status(app) == (
        "200 OK",
        f"Tasks: 1\nUndone: 0\nDispatched: 0\nCompleted: 0\n"
        f"Not Found: {int(outcome == 'not_found')}\n"
        f"Rejected: {int(outcome == 'rejected')}\n",
    )


@pytest.mark.parametrize("outcome", ["not_found", "rejected"])
def test_semantic_outcome_requires_current_unexpired_lease(
    tmp_path: Path, outcome: str
) -> None:
    database = _database(tmp_path)
    store = TaskStore(database)
    task = store.lease("worker-1")
    assert not store.complete(task["task_id"], "worker-2", 1, outcome)
    assert not store.complete(task["task_id"], "worker-1", 2, outcome)
    assert store.complete(task["task_id"], "worker-1", 1, outcome)
    assert not store.complete(task["task_id"], "worker-1", 1, "success")


@pytest.mark.parametrize("outcome", ["not_found", "rejected"])
def test_semantic_result_at_expiry_is_rejected(tmp_path: Path, outcome: str) -> None:
    database = _database(tmp_path)
    now = [datetime(2026, 1, 2, tzinfo=timezone.utc)]
    store = TaskStore(database, lease_timeout_seconds=60, clock=lambda: now[0])
    task = store.lease("worker-1")
    now[0] += timedelta(seconds=60)
    assert not store.complete(task["task_id"], "worker-1", 1, outcome)
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT state FROM task").fetchone()[0] == "dispatched"
    assert store.lease("worker-2")["lease_attempt"] == 2


@pytest.mark.parametrize("outcome", ["rate_limited", "transport_error", "temporary_error", "unknown"])
def test_other_outcomes_are_rejected_without_mutating_task(
    tmp_path: Path, outcome: str
) -> None:
    database = _database(tmp_path)
    app = create_app(TaskStore(database))
    _, grant = _post(app, "/lease", {"worker_id": "worker-1"})
    task = grant["task"]
    with sqlite3.connect(database) as connection:
        before = connection.execute("SELECT * FROM task").fetchone()
    status, _ = _post(app, "/result", {
        "task_id": task["task_id"], "worker_id": "worker-1",
        "lease_attempt": 1, "outcome": outcome,
    })
    assert status == "400 Bad Request"
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT * FROM task").fetchone() == before


def test_contract_and_docs_define_eligible_results() -> None:
    contract = json.loads(Path("contracts/semantic-exhaustion.json").read_text())
    assert contract["outcomes"] == [item.value for item in SemanticExhaustion]
    assert contract["next_engine_eligible"] is True
    assert contract["current_engine_preserved_until_step"] == 28
    assert "not_found" in Path("docs/semantic-exhaustion.md").read_text()
