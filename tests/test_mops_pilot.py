"""Offline regressions for the fixed Step-32 MOPS pilot runner."""

import gzip
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from xbrlswarm.discovery.cases import DISCOVERY_CASES
from xbrlswarm.discovery.mops import build_mops_xbrl_capture, verify_mops_capture_set
from xbrlswarm.mops_pilot import run_mops_pilot


FIXTURES = Path("tests/fixtures/discovery/mops")
NOW = datetime(2026, 9, 24, 15, 0, tzinfo=timezone.utc)


class FixtureResponse:
    status = 200

    def __init__(self, url: str, body: bytes):
        self.url = url
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self) -> bytes:
        return self.body

    def geturl(self) -> str:
        return self.url


def _opener(*, invalid_case: str | None = None, changed_case: str | None = None):
    def open_fixture(request, *, timeout):
        assert timeout == 30
        url = request.full_url
        query = parse_qs(urlsplit(url).query)
        stock_id = query["co_id"][0]
        year = query["year"][0]
        period = {"1": "Q1", "2": "Q2", "3": "Q3", "4": "FY"}[query["season"][0]]
        case_key = f"{stock_id}-{year}-{period}"
        if case_key == invalid_case:
            body = "<html>查無資料</html>".encode()
        else:
            body = gzip.decompress(
                (FIXTURES / stock_id / year / period / "xbrl-consolidated.bin.gz").read_bytes()
            )
            if case_key == changed_case:
                body += b"\n"
        return FixtureResponse(url, body)

    return open_fixture


def test_pilot_runs_all_fixed_cases_through_lease_and_evidence(tmp_path: Path) -> None:
    database = tmp_path / "pilot.sqlite"
    report = run_mops_pilot(database, opener=_opener(), clock=lambda: NOW)

    assert report["pilot_cases"] == [case.key for case in DISCOVERY_CASES]
    assert report["summary"] == {
        "attempted": 12,
        "completed": 12,
        "retryable": 0,
        "fixture_hash_matches": 12,
        "persisted_evidence": 12,
    }
    assert all(row["task_state"] == "completed" for row in report["results"])
    assert all(row["raw_payload_hash"] == f"sha256:{row['fixture_sha256']}" for row in report["results"])
    assert all(row["retrieved_at"] == "2026-09-24T15:00:00.000Z" for row in report["results"])

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT state, COUNT(*) FROM task GROUP BY state"
        ).fetchall() == [("completed", 12)]
        assert connection.execute(
            "SELECT COUNT(*) FROM evidence WHERE raw_snapshot_path IS NULL"
        ).fetchone() == (12,)


def test_invalid_source_response_is_retryable_and_not_evidence(tmp_path: Path) -> None:
    database = tmp_path / "pilot.sqlite"
    report = run_mops_pilot(
        database,
        opener=_opener(invalid_case="2330-2024-Q1"),
        clock=lambda: NOW,
    )

    assert report["summary"] == {
        "attempted": 12,
        "completed": 11,
        "retryable": 1,
        "fixture_hash_matches": 11,
        "persisted_evidence": 11,
    }
    first = report["results"][0]
    assert first["task_state"] == "temporary_error"
    assert first["evidence_id"] is None
    assert first["fixture_match"] is False
    assert first["error"]
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT state, retry_at FROM task WHERE id = 1"
        ).fetchone() == ("temporary_error", "2026-09-25T15:00:00.000Z")


def test_pilot_will_not_overwrite_existing_database(tmp_path: Path) -> None:
    database = tmp_path / "pilot.sqlite"
    database.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        run_mops_pilot(database, opener=_opener(), clock=lambda: NOW)
    assert database.read_bytes() == b"existing"


def test_valid_but_changed_payload_requires_new_audit(tmp_path: Path) -> None:
    report = run_mops_pilot(
        tmp_path / "pilot.sqlite",
        opener=_opener(changed_case="2330-2024-Q1"),
        clock=lambda: NOW,
    )
    first = report["results"][0]
    assert first["http_status"] == 200
    assert first["fixture_match"] is False
    assert first["evidence_id"] is None
    assert first["task_state"] == "temporary_error"
    assert "recapture" in first["error"]


def test_expired_retry_does_not_interrupt_remaining_fixed_cases(tmp_path: Path) -> None:
    # First lease, retrieval, and result happen at T0. Before the next lease,
    # advance beyond even the pilot's one-day cooldown to force recovery.
    calls = 0

    def advancing_clock():
        nonlocal calls
        calls += 1
        return NOW if calls <= 3 else NOW + timedelta(hours=25)

    database = tmp_path / "pilot.sqlite"
    report = run_mops_pilot(
        database,
        opener=_opener(invalid_case="2330-2024-Q1"),
        clock=advancing_clock,
    )

    assert report["summary"] == {
        "attempted": 12,
        "completed": 11,
        "retryable": 1,
        "fixture_hash_matches": 11,
        "persisted_evidence": 11,
    }
    assert [row["case"] for row in report["results"]] == [case.key for case in DISCOVERY_CASES]
    assert report["results"][0]["task_state"] == "temporary_error"
    assert all(row["task_state"] == "completed" for row in report["results"][1:])
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT state FROM task WHERE id = 1"
        ).fetchone() == ("undone",)


def test_committed_live_pilot_report_matches_verified_captures() -> None:
    report = json.loads(Path("discovery/mops_pilot_2026-09-24.json").read_text(encoding="utf-8"))
    decision = Path("docs/mops-pilot-report.md").read_text(encoding="utf-8")
    captures = verify_mops_capture_set(FIXTURES)

    assert report["source"] == "official_mops_live"
    assert report["pilot_cases"] == [capture.case.key for capture in captures]
    assert report["summary"] == {
        "attempted": 12,
        "completed": 12,
        "retryable": 0,
        "fixture_hash_matches": 12,
        "persisted_evidence": 12,
    }
    for capture, row in zip(captures, report["results"], strict=True):
        assert row["case"] == capture.case.key
        assert row["source_url"] == build_mops_xbrl_capture(capture.case).url
        assert row["final_url"] == row["source_url"]
        assert row["http_status"] == 200
        assert row["raw_payload_hash"] == f"sha256:{capture.sha256}"
        assert row["fixture_sha256"] == capture.sha256
        assert row["size_bytes"] == capture.size_bytes
        assert row["fixture_match"] is True
        assert row["task_state"] == "completed"
        assert row["evidence_id"] is not None
        assert row["error"] is None
        assert row["retrieved_at"].startswith("2026-09-24T")
        assert capture.case.key in decision
    assert "Step-33" in decision
