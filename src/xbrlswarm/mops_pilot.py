"""Run the fixed MOPS pilot through leases, parsing, and evidence persistence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from xbrlswarm.discovery.mops import build_mops_xbrl_capture, verify_mops_capture_set
from xbrlswarm.mops_evidence import accept_mops_response
from xbrlswarm.storage import connect_database
from xbrlswarm.worker_api import TaskStore


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("pilot clock must be timezone aware")
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _prepare_database(database: Path, migrations: Path, captures: tuple) -> None:
    database.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(database, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise FileExistsError(f"pilot database already exists: {database}") from exc
    os.close(descriptor)
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        for path in sorted(migrations.glob("*.sql")):
            connection.executescript(path.read_text(encoding="utf-8"))
        for capture in captures:
            case = capture.case
            connection.execute(
                """INSERT INTO task (stock_id, fiscal_year, report_period, state, engine)
                   VALUES (?, ?, ?, 'undone', 'mops')""",
                (case.stock_id, case.fiscal_year, case.report_period.value),
            )
        connection.commit()
    except BaseException:
        connection.rollback()
        connection.close()
        database.unlink(missing_ok=True)
        raise
    connection.close()


def run_mops_pilot(
    database: Path,
    *,
    fixture_root: Path = Path("tests/fixtures/discovery/mops"),
    migrations: Path = Path("migrations"),
    opener: Callable = urlopen,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    snapshot_root: Path | None = None,
) -> dict:
    """Run the 12 fixed cases once and return a machine-readable audit record."""

    captures = verify_mops_capture_set(fixture_root)
    _prepare_database(Path(database), migrations, captures)
    store = TaskStore(database, clock=clock)
    results: list[dict] = []

    for capture in captures:
        case = capture.case
        lease = store.lease("mops-pilot")
        if lease is None or (
            lease["stock_id"], lease["fiscal_year"], lease["report_period"], lease["engine"]
        ) != (case.stock_id, case.fiscal_year, case.report_period.value, "mops"):
            raise RuntimeError(f"pilot lease does not match fixed case {case.key}")
        request = build_mops_xbrl_capture(case)
        row = {
            "case": case.key,
            "task_id": lease["task_id"],
            "source_url": request.url,
            "fixture_sha256": capture.sha256,
            "http_status": None,
            "final_url": None,
            "retrieved_at": None,
            "raw_payload_hash": None,
            "size_bytes": None,
            "fixture_match": None,
            "evidence_id": None,
            "task_state": None,
            "error": None,
        }
        failure = "temporary_error"
        try:
            with opener(Request(request.url, headers=dict(request.request_headers)), timeout=30) as response:
                body = response.read()
                row["http_status"] = response.status
                row["final_url"] = response.geturl()
            retrieved_at = clock()
            row["retrieved_at"] = _timestamp(retrieved_at)
            digest = hashlib.sha256(body).hexdigest()
            row["raw_payload_hash"] = f"sha256:{digest}"
            row["size_bytes"] = len(body)
            row["fixture_match"] = digest == capture.sha256
            if row["http_status"] != 200 or row["final_url"] != request.url:
                raise ValueError("unexpected MOPS HTTP status or final URL")
            if not row["fixture_match"]:
                raise ValueError("MOPS raw payload differs from audited fixture; recapture before acceptance")
            evidence = accept_mops_response(
                database,
                lease["task_id"],
                case,
                body,
                source_url=request.url,
                retrieved_at=retrieved_at,
                snapshot_root=snapshot_root,
            )
            row["evidence_id"] = evidence.id
            outcome = "success"
        except HTTPError as exc:
            row["http_status"] = exc.code
            row["final_url"] = exc.url
            row["error"] = f"HTTP {exc.code}"
            outcome = "rate_limited" if exc.code == 429 else failure
        except URLError as exc:
            row["error"] = f"transport error: {exc.reason}"
            outcome = "transport_error"
        except (ValueError, OSError) as exc:
            row["error"] = str(exc)
            outcome = failure
        if not store.complete(
            lease["task_id"], "mops-pilot", lease["lease_attempt"], outcome
        ):
            raise RuntimeError(f"pilot lease expired before result for {case.key}")
        row["task_state"] = "completed" if outcome == "success" else outcome
        results.append(row)

    with connect_database(database) as connection:
        persisted = connection.execute(
            "SELECT COUNT(*) FROM evidence WHERE source_type = 'mops' AND raw_payload_hash IS NOT NULL"
        ).fetchone()[0]
    return {
        "schema_version": 1,
        "source": "official_mops_live",
        "pilot_cases": [capture.case.key for capture in captures],
        "results": results,
        "summary": {
            "attempted": len(results),
            "completed": sum(row["task_state"] == "completed" for row in results),
            "retryable": sum(row["task_state"] != "completed" for row in results),
            "fixture_hash_matches": sum(row["fixture_match"] is True for row in results),
            "persisted_evidence": persisted,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m xbrlswarm.mops_pilot")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixture-root", type=Path, default=Path("tests/fixtures/discovery/mops"))
    parser.add_argument("--migrations", type=Path, default=Path("migrations"))
    parser.add_argument("--snapshot-root", type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error(f"pilot report already exists: {args.output}")
    result = run_mops_pilot(
        args.database,
        fixture_root=args.fixture_root,
        migrations=args.migrations,
        snapshot_root=args.snapshot_root,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, sort_keys=True))
    return 0 if result["summary"]["completed"] == result["summary"]["attempted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
