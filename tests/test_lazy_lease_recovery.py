import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import pytest

from xbrlswarm.worker_api import TaskStore, create_app


START = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "lease.sqlite"
    with sqlite3.connect(path) as connection:
        for migration in sorted(Path("migrations").glob("*.sql")):
            connection.executescript(migration.read_text(encoding="utf-8"))
        connection.execute(
            """INSERT INTO task (stock_id, fiscal_year, report_period, state, engine)
               VALUES ('0050', 2024, 'Q1', 'undone', 'mops')"""
        )
    return path


def _row(database: Path):
    with sqlite3.connect(database) as connection:
        return connection.execute(
            "SELECT state, worker_id, dispatched_at, attempts, updated_at FROM task"
        ).fetchone()


def test_reclaim_only_at_timeout_and_preserve_generation(tmp_path: Path) -> None:
    database = _database(tmp_path)
    clock = Clock()
    store = TaskStore(database, lease_timeout_seconds=60, clock=clock)
    first = store.lease("worker-1")
    clock.now = START + timedelta(seconds=59, milliseconds=999)
    assert store.lease("worker-2") is None
    assert _row(database) == (
        "dispatched", "worker-1", first["dispatched_at"], 1, first["dispatched_at"]
    )

    clock.now = START + timedelta(seconds=60)
    second = store.lease("worker-2")
    assert second["task_id"] == first["task_id"]
    assert second["lease_attempt"] == 2
    assert second["dispatched_at"] == "2026-01-02T03:05:05.000Z"
    assert _row(database) == (
        "dispatched", "worker-2", second["dispatched_at"], 2, second["dispatched_at"]
    )
    assert not store.complete(first["task_id"], "worker-1", 1)
    assert store.complete(second["task_id"], "worker-2", 2)
    assert _row(database)[:4] == ("completed", None, None, 2)


def test_expired_result_is_rejected_before_any_reclaim_request(tmp_path: Path) -> None:
    database = _database(tmp_path)
    clock = Clock()
    store = TaskStore(database, lease_timeout_seconds=60, clock=clock)
    task = store.lease("worker-1")
    clock.now = START + timedelta(seconds=60)
    assert not store.complete(task["task_id"], "worker-1", task["lease_attempt"])
    assert _row(database)[:4] == ("dispatched", "worker-1", task["dispatched_at"], 1)
    assert store.lease("worker-1")["lease_attempt"] == 2
    assert not store.complete(task["task_id"], "worker-1", 1)


def test_result_succeeds_just_before_expiry_and_is_never_reclaimed(tmp_path: Path) -> None:
    database = _database(tmp_path)
    clock = Clock()
    store = TaskStore(database, lease_timeout_seconds=60, clock=clock)
    task = store.lease("worker-1")
    clock.now = START + timedelta(seconds=59, milliseconds=999)
    assert store.complete(task["task_id"], "worker-1", task["lease_attempt"])
    clock.now = START + timedelta(hours=1)
    assert store.lease("worker-2") is None
    assert _row(database)[:4] == ("completed", None, None, 1)


def test_one_lease_request_recovers_all_expired_tasks(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """INSERT INTO task (stock_id, fiscal_year, report_period, state, engine)
               VALUES ('0051', 2024, 'Q1', 'undone', 'mops')"""
        )
    clock = Clock()
    store = TaskStore(database, lease_timeout_seconds=60, clock=clock)
    first = store.lease("worker-1")
    second = store.lease("worker-2")
    clock.now = START + timedelta(seconds=60)
    assert store.lease("worker-3")["task_id"] == first["task_id"]
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT state, worker_id, dispatched_at, attempts FROM task WHERE id = ?",
            (second["task_id"],),
        ).fetchone()
    assert row == ("undone", None, None, 1)


def test_reclaim_and_dispatch_roll_back_together_on_failure(tmp_path: Path) -> None:
    database = _database(tmp_path)
    clock = Clock()
    store = TaskStore(database, lease_timeout_seconds=60, clock=clock)
    store.lease("worker-1")
    before = _row(database)
    clock.now = START + timedelta(seconds=60)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TRIGGER fail_redispatch BEFORE UPDATE ON task
               WHEN NEW.state = 'dispatched' AND NEW.attempts = 2
               BEGIN SELECT RAISE(ABORT, 'test redispatch failure'); END"""
        )
    with pytest.raises(sqlite3.IntegrityError, match="test redispatch failure"):
        store.lease("worker-2")
    assert _row(database) == before


def test_concurrent_reclaim_grants_only_one_new_lease(tmp_path: Path) -> None:
    database = _database(tmp_path)
    clock = Clock()
    store = TaskStore(database, lease_timeout_seconds=60, clock=clock)
    store.lease("worker-1")
    clock.now = START + timedelta(seconds=60)
    barrier = threading.Barrier(6)

    def lease(index: int):
        barrier.wait(timeout=10)
        return TaskStore(database, lease_timeout_seconds=60, clock=clock).lease(
            f"worker-{index + 2}"
        )

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lease, range(6)))
    grants = [result for result in results if result is not None]
    assert len(grants) == 1
    assert grants[0]["lease_attempt"] == 2
    assert _row(database)[3] == 2


def test_http_result_rejects_expired_lease(tmp_path: Path) -> None:
    clock = Clock()
    app = create_app(TaskStore(_database(tmp_path), lease_timeout_seconds=60, clock=clock))

    def call(path: str, payload: dict):
        raw = json.dumps(payload).encode()
        result = {}

        def start_response(status, headers):
            result["status"] = status

        body = b"".join(app({
            "PATH_INFO": path, "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": str(len(raw)),
            "wsgi.input": BytesIO(raw),
        }, start_response))
        return result["status"], json.loads(body)

    _, response = call("/lease", {"worker_id": "worker-1"})
    task = response["task"]
    clock.now = START + timedelta(seconds=60)
    status, response = call("/result", {
        "task_id": task["task_id"], "worker_id": "worker-1",
        "lease_attempt": task["lease_attempt"], "outcome": "success",
    })
    assert status == "409 Conflict"
    assert response == {"error": "lease_not_current"}


@pytest.mark.parametrize("timeout", [0, -1, True, 1.5])
def test_timeout_must_be_positive_integer(tmp_path: Path, timeout) -> None:
    with pytest.raises(ValueError, match="lease_timeout_seconds"):
        TaskStore(tmp_path / "unused.sqlite", lease_timeout_seconds=timeout)
