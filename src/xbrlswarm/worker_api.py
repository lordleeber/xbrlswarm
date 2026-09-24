"""Small HTTP boundary for workers backed by the existing task table."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable
from wsgiref.simple_server import make_server

from .domain import RetryableFailure, SemanticExhaustion
from .storage import connect_database

_SEMANTIC_OUTCOMES = frozenset(SemanticExhaustion)
_RETRYABLE_OUTCOMES = frozenset(RetryableFailure)
_RESULT_OUTCOMES = _SEMANTIC_OUTCOMES | _RETRYABLE_OUTCOMES | {"success"}


def _utc_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


class TaskStore:
    """One SQLite connection per operation; no long-lived cross-request cursor."""

    def __init__(
        self,
        database: str | Path,
        lease_timeout_seconds: int = 300,
        clock: Callable[[], datetime] | None = None,
        retry_delay_seconds: int = 60,
    ) -> None:
        if type(lease_timeout_seconds) is not int or lease_timeout_seconds <= 0:
            raise ValueError("lease_timeout_seconds must be a positive integer")
        if type(retry_delay_seconds) is not int or retry_delay_seconds <= 0:
            raise ValueError("retry_delay_seconds must be a positive integer")
        self.database = Path(database)
        self.lease_timeout = timedelta(seconds=lease_timeout_seconds)
        self.retry_delay = timedelta(seconds=retry_delay_seconds)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _operation_times(self) -> tuple[str, str, str]:
        now = self.clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return (
            _utc_timestamp(now),
            _utc_timestamp(now - self.lease_timeout),
            _utc_timestamp(now + self.retry_delay),
        )

    def _connect(self):
        if not self.database.is_file():
            raise FileNotFoundError(f"database file does not exist: {self.database}")
        return connect_database(self.database)

    def lease(self, worker_id: str) -> dict | None:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            now, cutoff, _ = self._operation_times()
            connection.execute(
                """UPDATE task SET state = 'undone', worker_id = NULL,
                          dispatched_at = NULL, updated_at = ?
                   WHERE state = 'dispatched' AND dispatched_at <= ?""",
                (now, cutoff),
            )
            connection.execute(
                """UPDATE task SET state = 'undone', retry_at = NULL, updated_at = ?
                   WHERE state IN ('rate_limited', 'transport_error', 'temporary_error')
                     AND retry_at <= ?""",
                (now, now),
            )
            connection.execute(
                """UPDATE task SET
                       engine = CASE engine
                           WHEN 'mops' THEN 'goodinfo'
                           WHEN 'goodinfo' THEN 'yahoo'
                           WHEN 'yahoo' THEN 'google'
                           WHEN 'google' THEN 'grounded_ai'
                           ELSE engine END,
                       state = CASE WHEN engine = 'grounded_ai'
                           THEN 'terminal_unresolved' ELSE 'undone' END,
                       worker_id = NULL, dispatched_at = NULL,
                       retry_at = NULL, updated_at = ?
                   WHERE state IN ('not_found', 'rejected')""",
                (now,),
            )
            row = connection.execute(
                """UPDATE task SET state = 'dispatched', worker_id = ?,
                          dispatched_at = ?, updated_at = ?, attempts = attempts + 1
                   WHERE id = (
                       SELECT id FROM task WHERE state = 'undone' ORDER BY id LIMIT 1
                   ) AND state = 'undone'
                   RETURNING id, stock_id, fiscal_year, report_period, engine,
                             dispatched_at, attempts""",
                (worker_id, now, now),
            ).fetchone()
            connection.commit()
            if row is None:
                return None
            return {
                "task_id": row[0],
                "stock_id": row[1],
                "fiscal_year": row[2],
                "report_period": row[3],
                "engine": row[4],
                "worker_id": worker_id,
                "dispatched_at": row[5],
                "lease_attempt": row[6],
            }
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def complete(
        self, task_id: int, worker_id: str, lease_attempt: int, outcome: str = "success"
    ) -> bool:
        if outcome not in _RESULT_OUTCOMES:
            raise ValueError("unsupported result outcome")
        state = "completed" if outcome == "success" else outcome
        retryable = outcome in _RETRYABLE_OUTCOMES
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            now, cutoff, retry_at = self._operation_times()
            cursor = connection.execute(
                """UPDATE task SET state = ?, worker_id = NULL,
                          dispatched_at = NULL, retry_at = ?,
                          fail_count = fail_count + ?, updated_at = ?
                   WHERE id = ? AND state = 'dispatched' AND worker_id = ?
                         AND attempts = ? AND dispatched_at > ?""",
                (state, retry_at if retryable else None, int(retryable),
                 now, task_id, worker_id, lease_attempt, cutoff),
            )
            connection.commit()
            return cursor.rowcount == 1
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def stats(self) -> dict:
        connection = self._connect()
        try:
            by_state = dict(
                connection.execute(
                    "SELECT state, COUNT(*) FROM task GROUP BY state ORDER BY state"
                )
            )
            by_engine = dict(
                connection.execute(
                    "SELECT engine, COUNT(*) FROM task GROUP BY engine ORDER BY engine"
                )
            )
            return {"total": sum(by_state.values()), "by_state": by_state, "by_engine": by_engine}
        finally:
            connection.close()


def _response(
    start_response: Callable,
    status: str,
    body: bytes,
    content_type: str,
    extra_headers: list[tuple[str, str]] | None = None,
):
    start_response(
        status,
        [("Content-Type", content_type), ("Content-Length", str(len(body)))]
        + (extra_headers or []),
    )
    return [body]


def _json(start_response: Callable, status: str, payload: dict):
    return _response(
        start_response,
        status,
        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        "application/json; charset=utf-8",
    )


def _request_json(environ: dict) -> dict:
    if environ.get("CONTENT_TYPE", "").split(";", 1)[0].strip().lower() != "application/json":
        raise ValueError("Content-Type must be application/json")
    try:
        length = int(environ.get("CONTENT_LENGTH", ""))
    except ValueError as error:
        raise ValueError("Content-Length is required") from error
    if not 0 < length <= 16_384:
        raise ValueError("JSON body size must be 1..16384 bytes")
    try:
        body = json.loads(environ["wsgi.input"].read(length))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid JSON body") from error
    if not isinstance(body, dict):
        raise ValueError("JSON body must be an object")
    return body


def _worker_id(body: dict) -> str:
    worker_id = body.get("worker_id")
    if not isinstance(worker_id, str) or not worker_id.strip() or len(worker_id) > 128:
        raise ValueError("worker_id must be nonblank text of at most 128 characters")
    return worker_id


def create_app(store: TaskStore):
    """Return a WSGI app. Bind behind trusted network controls in production."""

    methods = {
        "/lease": "POST",
        "/result": "POST",
        "/stats": "GET",
        "/status": "GET",
        "/healthz": "GET",
    }

    def app(environ: dict, start_response: Callable):
        path = environ.get("PATH_INFO", "")
        method = environ.get("REQUEST_METHOD", "")
        if path not in methods:
            return _json(start_response, "404 Not Found", {"error": "not_found"})
        if method != methods[path]:
            return _response(
                start_response,
                "405 Method Not Allowed",
                b'{"error":"method_not_allowed"}',
                "application/json; charset=utf-8",
                [("Allow", methods[path])],
            )

        if path == "/healthz":
            return _json(start_response, "200 OK", {"status": "ok"})
        if path == "/stats":
            return _json(start_response, "200 OK", store.stats())
        if path == "/status":
            stats = store.stats()
            states = stats["by_state"]
            body = (
                f"Tasks: {stats['total']}\n"
                f"Undone: {states.get('undone', 0)}\n"
                f"Dispatched: {states.get('dispatched', 0)}\n"
                f"Completed: {states.get('completed', 0)}\n"
                f"Not Found: {states.get('not_found', 0)}\n"
                f"Rejected: {states.get('rejected', 0)}\n"
                f"Rate Limited: {states.get('rate_limited', 0)}\n"
                f"Transport Error: {states.get('transport_error', 0)}\n"
                f"Temporary Error: {states.get('temporary_error', 0)}\n"
                f"Terminal Unresolved: {states.get('terminal_unresolved', 0)}\n"
            ).encode("utf-8")
            return _response(start_response, "200 OK", body, "text/plain; charset=utf-8")

        try:
            body = _request_json(environ)
            worker_id = _worker_id(body)
            if path == "/lease":
                if set(body) != {"worker_id"}:
                    raise ValueError("/lease requires only worker_id")
                task = store.lease(worker_id)
                if task is None:
                    return _response(start_response, "204 No Content", b"", "application/json")
                return _json(start_response, "200 OK", {"task": task})

            task_id = body.get("task_id")
            lease_attempt = body.get("lease_attempt")
            if set(body) != {"task_id", "worker_id", "lease_attempt", "outcome"}:
                raise ValueError("/result requires task_id, worker_id, lease_attempt, outcome")
            if type(task_id) is not int or task_id <= 0:
                raise ValueError("task_id must be a positive integer")
            if type(lease_attempt) is not int or lease_attempt <= 0:
                raise ValueError("lease_attempt must be a positive integer")
            outcome = body["outcome"]
            if not isinstance(outcome, str) or outcome not in _RESULT_OUTCOMES:
                raise ValueError("unsupported result outcome")
            if not store.complete(task_id, worker_id, lease_attempt, outcome):
                return _json(start_response, "409 Conflict", {"error": "lease_not_current"})
            state = "completed" if outcome == "success" else outcome
            return _json(start_response, "200 OK", {"task_id": task_id, "state": state})
        except ValueError as error:
            return _json(start_response, "400 Bad Request", {"error": str(error)})

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the xbrlswarm Worker API")
    parser.add_argument("--database", type=Path, required=True, help="migrated SQLite database")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--lease-timeout-seconds", type=int, default=300)
    parser.add_argument("--retry-delay-seconds", type=int, default=60)
    args = parser.parse_args(argv)
    if args.lease_timeout_seconds <= 0:
        parser.error("--lease-timeout-seconds must be positive")
    if args.retry_delay_seconds <= 0:
        parser.error("--retry-delay-seconds must be positive")
    store = TaskStore(
        args.database,
        lease_timeout_seconds=args.lease_timeout_seconds,
        retry_delay_seconds=args.retry_delay_seconds,
    )
    connection = store._connect()
    try:
        connection.execute("SELECT 1 FROM task LIMIT 1")
    finally:
        connection.close()
    with make_server(args.host, args.port, create_app(store)) as server:
        server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
