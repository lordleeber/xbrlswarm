import json
import sqlite3
from io import BytesIO
from pathlib import Path

import pytest

from xbrlswarm.worker_api import TaskStore, create_app


MIGRATIONS = Path("migrations")


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "worker.sqlite"
    connection = sqlite3.connect(path)
    for migration in sorted(MIGRATIONS.glob("*.sql")):
        connection.executescript(migration.read_text(encoding="utf-8"))
    connection.execute(
        """INSERT INTO task (stock_id, fiscal_year, report_period, state, engine)
           VALUES ('0050', 2024, 'Q1', 'undone', 'mops')"""
    )
    connection.commit()
    connection.close()
    return path


def _call(app, method: str, path: str, payload=None, *, content_type="application/json"):
    raw = b"" if payload is None else json.dumps(payload).encode("utf-8")
    result = {}

    def start_response(status, headers):
        result["status"] = status
        result["headers"] = dict(headers)

    response = b"".join(
        app(
            {
                "REQUEST_METHOD": method,
                "PATH_INFO": path,
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": str(len(raw)),
                "wsgi.input": BytesIO(raw),
            },
            start_response,
        )
    )
    assert result["headers"]["Content-Length"] == str(len(response))
    return result["status"], result["headers"], response


def test_worker_api_lease_result_and_read_endpoints(tmp_path: Path) -> None:
    database = _database(tmp_path)
    app = create_app(TaskStore(database))

    status, _, body = _call(app, "GET", "/healthz")
    assert status == "200 OK"
    assert json.loads(body) == {"status": "ok"}

    status, _, body = _call(app, "POST", "/lease", {"worker_id": "worker-1"})
    task = json.loads(body)["task"]
    assert status == "200 OK"
    assert {key: task[key] for key in ("stock_id", "fiscal_year", "report_period", "engine")} == {
        "stock_id": "0050",
        "fiscal_year": 2024,
        "report_period": "Q1",
        "engine": "mops",
    }
    assert task["worker_id"] == "worker-1"
    assert task["dispatched_at"].endswith("Z")

    status, _, body = _call(app, "POST", "/lease", {"worker_id": "worker-2"})
    assert status == "204 No Content"
    assert body == b""

    status, _, body = _call(app, "GET", "/stats")
    assert status == "200 OK"
    assert json.loads(body) == {
        "total": 1,
        "by_state": {"dispatched": 1},
        "by_engine": {"mops": 1},
    }
    status, headers, body = _call(app, "GET", "/status")
    assert status == "200 OK"
    assert headers["Content-Type"].startswith("text/plain")
    assert b"Dispatched: 1" in body

    result = {"task_id": task["task_id"], "worker_id": "worker-1", "outcome": "success"}
    status, _, body = _call(app, "POST", "/result", {**result, "worker_id": "worker-2"})
    assert status == "409 Conflict"
    assert json.loads(body) == {"error": "lease_not_owned"}

    status, _, body = _call(app, "POST", "/result", result)
    assert status == "200 OK"
    assert json.loads(body) == {"task_id": task["task_id"], "state": "completed"}

    status, _, _ = _call(app, "POST", "/result", result)
    assert status == "409 Conflict"
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT state, worker_id, dispatched_at, attempts FROM task"
        ).fetchone()
    assert row == ("completed", None, None, 1)


@pytest.mark.parametrize(
    "method,path,payload,expected",
    [
        ("GET", "/missing", None, "404 Not Found"),
        ("GET", "/lease", None, "405 Method Not Allowed"),
        ("POST", "/lease", {}, "400 Bad Request"),
        ("POST", "/lease", {"worker_id": " "}, "400 Bad Request"),
        ("POST", "/lease", {"worker_id": "x", "extra": 1}, "400 Bad Request"),
        ("POST", "/result", {"task_id": True, "worker_id": "x", "outcome": "success"}, "400 Bad Request"),
        ("POST", "/result", {"task_id": 1, "worker_id": "x", "outcome": "not_found"}, "400 Bad Request"),
    ],
)
def test_invalid_methods_and_bodies_are_rejected(
    tmp_path: Path, method: str, path: str, payload: object, expected: str
) -> None:
    app = create_app(TaskStore(_database(tmp_path)))
    status, _, _ = _call(app, method, path, payload)
    assert status == expected


def test_healthz_means_server_alive_not_database_ready(tmp_path: Path) -> None:
    missing_database = tmp_path / "not-initialized.sqlite"
    app = create_app(TaskStore(missing_database))
    status, _, body = _call(app, "GET", "/healthz")
    assert status == "200 OK"
    assert json.loads(body) == {"status": "ok"}
    assert not missing_database.exists()


def test_step23_docs_and_command_are_present() -> None:
    decision = Path("docs/worker-api.md").read_text(encoding="utf-8")
    acceptance = Path("docs/step-23-acceptance.md").read_text(encoding="utf-8")
    project = Path("pyproject.toml").read_text(encoding="utf-8")

    assert "POST /lease" in decision
    assert "POST /result" in decision
    assert "GET /healthz" in decision
    assert "127.0.0.1" in decision
    assert "Step-24" in acceptance
    assert "xbrlswarm-worker-api" in project
