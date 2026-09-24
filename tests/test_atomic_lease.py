import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from xbrlswarm.worker_api import TaskStore


MIGRATIONS = Path("migrations")
CONTRACT = Path("contracts/atomic-task-lease.json")
DECISION = Path("docs/atomic-task-lease.md")
ACCEPTANCE = Path("docs/step-24-acceptance.md")


def _database(tmp_path: Path, task_count: int) -> Path:
    path = tmp_path / "atomic-lease.sqlite"
    connection = sqlite3.connect(path)
    for migration in sorted(MIGRATIONS.glob("*.sql")):
        connection.executescript(migration.read_text(encoding="utf-8"))
    connection.executemany(
        """INSERT INTO task (stock_id, fiscal_year, report_period, state, engine)
           VALUES (?, 2024, 'Q1', 'undone', 'mops')""",
        [(f"{index:04d}",) for index in range(task_count)],
    )
    connection.commit()
    connection.close()
    return path


@pytest.mark.parametrize("task_count,worker_count", [(1, 2), (1, 8), (3, 8)])
def test_concurrent_workers_receive_each_task_at_most_once(
    tmp_path: Path, task_count: int, worker_count: int
) -> None:
    database = _database(tmp_path, task_count)
    barrier = threading.Barrier(worker_count)

    def lease(index: int):
        barrier.wait(timeout=10)
        return TaskStore(database).lease(f"worker-{index}")

    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        results = list(pool.map(lease, range(worker_count)))

    granted = [result for result in results if result is not None]
    assert len(granted) == task_count
    assert len({result["task_id"] for result in granted}) == task_count

    with sqlite3.connect(database) as connection:
        rows = connection.execute(
            """SELECT id, state, worker_id, dispatched_at, updated_at, attempts
               FROM task ORDER BY id"""
        ).fetchall()
    assert len(rows) == task_count
    for task_id, state, worker_id, dispatched_at, updated_at, attempts in rows:
        grant = next(result for result in granted if result["task_id"] == task_id)
        assert state == "dispatched"
        assert worker_id == grant["worker_id"]
        assert dispatched_at == updated_at == grant["dispatched_at"]
        assert attempts == grant["lease_attempt"] == 1


def test_failed_dispatch_rolls_back_all_lease_fields(tmp_path: Path) -> None:
    database = _database(tmp_path, 1)
    with sqlite3.connect(database) as connection:
        before = connection.execute("SELECT * FROM task").fetchone()
        connection.execute(
            """CREATE TRIGGER fail_dispatch BEFORE UPDATE ON task
               WHEN NEW.state = 'dispatched'
               BEGIN SELECT RAISE(ABORT, 'test dispatch failure'); END"""
        )

    with pytest.raises(sqlite3.IntegrityError, match="test dispatch failure"):
        TaskStore(database).lease("worker-1")

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT * FROM task").fetchone() == before
        connection.execute("DROP TRIGGER fail_dispatch")

    assert TaskStore(database).lease("worker-2")["lease_attempt"] == 1


def test_atomic_lease_contract_and_docs() -> None:
    assert json.loads(CONTRACT.read_text(encoding="utf-8")) == {
        "contract": "atomic_task_lease",
        "version": 1,
        "eligible_state": "undone",
        "leased_state": "dispatched",
        "selection_order": "lowest_task_id_first",
        "transaction": "begin_immediate_then_conditional_update_returning",
        "lease_fields": ["worker_id", "dispatched_at", "attempts", "updated_at"],
        "empty_queue": "no_task",
        "concurrency_invariant": "one_active_lease_per_task",
        "result_generation": "lease_attempt_equals_attempts_after_increment",
        "expiry_recovery_deferred_to_step": 25,
    }
    decision = DECISION.read_text(encoding="utf-8")
    acceptance = ACCEPTANCE.read_text(encoding="utf-8")
    assert "BEGIN IMMEDIATE" in decision
    assert "UPDATE … RETURNING" in decision
    assert "兩個 Worker" in decision
    assert "Step-25" in acceptance
