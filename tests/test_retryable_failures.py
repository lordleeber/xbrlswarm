import json
import sqlite3
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import pytest

from xbrlswarm.domain import RetryableFailure
from xbrlswarm.worker_api import TaskStore, create_app


START = datetime(2026, 9, 24, 1, 2, 3, tzinfo=timezone.utc)


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "retry.sqlite"
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
                      dispatched_at, retry_at, updated_at FROM task"""
        ).fetchone()


def _call(app, method: str, path: str, payload: dict | None = None):
    raw = b"" if payload is None else json.dumps(payload).encode()
    response = {}

    def start_response(status, headers):
        response["status"] = status

    body = b"".join(app({
        "PATH_INFO": path, "REQUEST_METHOD": method,
        "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": str(len(raw)),
        "wsgi.input": BytesIO(raw),
    }, start_response))
    return (
        response["status"],
        json.loads(body) if body and path != "/status" else None,
        body.decode(),
    )


@pytest.mark.parametrize("outcome", [item.value for item in RetryableFailure])
def test_retryable_result_waits_then_releases_same_engine(
    tmp_path: Path, outcome: str
) -> None:
    database = _database(tmp_path)
    now = [START]
    store = TaskStore(database, retry_delay_seconds=60, clock=lambda: now[0])
    app = create_app(store)
    _, response, _ = _call(app, "POST", "/lease", {"worker_id": "worker-1"})
    first = response["task"]
    result = {"task_id": first["task_id"], "worker_id": "worker-1",
              "lease_attempt": 1, "outcome": outcome}
    status, response, _ = _call(app, "POST", "/result", result)
    assert (status, response) == (
        "200 OK", {"task_id": first["task_id"], "state": outcome}
    )
    assert _row(database) == (
        outcome, "mops", 1, 1, None, None, "2026-09-24T01:03:03.000Z",
        "2026-09-24T01:02:03.000Z",
    )
    assert _call(app, "POST", "/result", result)[0] == "409 Conflict"
    now[0] += timedelta(seconds=59, milliseconds=999)
    assert _call(app, "POST", "/lease", {"worker_id": "worker-2"})[0] == "204 No Content"
    assert _row(database)[0:4] == (outcome, "mops", 1, 1)
    now[0] += timedelta(milliseconds=1)
    _, response, _ = _call(app, "POST", "/lease", {"worker_id": "worker-2"})
    second = response["task"]
    assert (second["task_id"], second["engine"], second["lease_attempt"]) == (
        first["task_id"], "mops", 2
    )
    assert _row(database)[:7] == (
        "dispatched", "mops", 2, 1, "worker-2", second["dispatched_at"], None
    )
    assert not store.complete(first["task_id"], "worker-1", 1, "success")
    assert store.complete(second["task_id"], "worker-2", 2, "success")
    assert _row(database)[:7] == ("completed", "mops", 2, 1, None, None, None)


def test_retryable_failure_does_not_block_other_ready_tasks(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """INSERT INTO task (stock_id, fiscal_year, report_period, state, engine)
               VALUES ('0051', 2024, 'Q1', 'undone', 'goodinfo')"""
        )
    now = [START]
    store = TaskStore(database, retry_delay_seconds=60, clock=lambda: now[0])
    first = store.lease("worker-1")
    assert store.complete(first["task_id"], "worker-1", 1, "rate_limited")
    second = store.lease("worker-2")
    assert second["stock_id"] == "0051"
    assert second["engine"] == "goodinfo"


def test_invalid_or_stale_retry_result_does_not_increment_fail_count(tmp_path: Path) -> None:
    database = _database(tmp_path)
    now = [START]
    store = TaskStore(database, retry_delay_seconds=60, clock=lambda: now[0])
    task = store.lease("worker-1")
    assert not store.complete(task["task_id"], "other", 1, "temporary_error")
    assert not store.complete(task["task_id"], "worker-1", 2, "temporary_error")
    assert _row(database)[3] == 0
    now[0] += timedelta(seconds=300)
    assert not store.complete(task["task_id"], "worker-1", 1, "temporary_error")
    assert _row(database)[3] == 0


def test_repeated_infrastructure_failures_increment_once_per_valid_result(
    tmp_path: Path,
) -> None:
    database = _database(tmp_path)
    now = [START]
    store = TaskStore(database, retry_delay_seconds=60, clock=lambda: now[0])
    first = store.lease("worker-1")
    assert store.complete(first["task_id"], "worker-1", 1, "rate_limited")
    now[0] += timedelta(seconds=60)
    second = store.lease("worker-2")
    assert second["lease_attempt"] == 2
    assert store.complete(second["task_id"], "worker-2", 2, "transport_error")
    assert _row(database)[:4] == ("transport_error", "mops", 2, 2)
    assert not store.complete(first["task_id"], "worker-1", 1, "temporary_error")
    assert _row(database)[3] == 2


@pytest.mark.parametrize("delay", [0, -1, True, 1.5])
def test_retry_delay_must_be_positive_integer(tmp_path: Path, delay) -> None:
    with pytest.raises(ValueError, match="retry_delay_seconds"):
        TaskStore(tmp_path / "unused.sqlite", retry_delay_seconds=delay)


def test_status_shows_retryable_states(tmp_path: Path) -> None:
    database = _database(tmp_path)
    store = TaskStore(database, clock=lambda: START)
    app = create_app(store)
    task = store.lease("worker-1")
    assert store.complete(task["task_id"], "worker-1", 1, "rate_limited")
    status, _, body = _call(app, "GET", "/status")
    assert status == "200 OK"
    assert "Tasks: 1\n" in body
    assert "Rate Limited: 1\n" in body
    assert "Transport Error: 0\n" in body
    assert "Temporary Error: 0\n" in body


def test_step27_migration_preserves_existing_tasks_and_strict_table() -> None:
    connection = sqlite3.connect(":memory:")
    for migration in sorted(Path("migrations").glob("*.sql")):
        if migration.name.startswith("0008_"):
            break
        connection.executescript(migration.read_text(encoding="utf-8"))
    connection.execute(
        """INSERT INTO task (stock_id, fiscal_year, report_period, state, engine,
                  attempts, fail_count) VALUES ('0050', 2024, 'Q1', 'not_found',
                  'mops', 3, 2)"""
    )
    before = connection.execute("SELECT * FROM task").fetchone()
    connection.executescript(Path("migrations/0008_add_retry_at.sql").read_text())
    assert connection.execute("SELECT * FROM task").fetchone() == before + (None,)
    assert next(row for row in connection.execute("PRAGMA table_list('task')")
                if row[1] == "task")[5] == 1


def test_retryable_contract_and_docs() -> None:
    contract = json.loads(Path("contracts/retryable-failures.json").read_text())
    assert contract["outcomes"] == [item.value for item in RetryableFailure]
    assert contract["same_engine"] is True
    assert contract["retry_after_required"] is True
    assert "retry_at" in Path("docs/retryable-failures.md").read_text()
