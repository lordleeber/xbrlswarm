"""Step-38 persisted Goodinfo speech events from verified detail captures."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import pytest

from xbrlswarm.domain import ReportPeriod
from xbrlswarm.goodinfo_candidates import GoodinfoListCandidate
from xbrlswarm.goodinfo_detail import capture_goodinfo_detail
from xbrlswarm.goodinfo_evidence import accept_goodinfo_announcement
from xbrlswarm.storage import connect_database


def _database(tmp_path: Path, *, stock: str = "2330", year: int = 2024,
              period: str = "Q1", engine: str = "goodinfo") -> Path:
    path = tmp_path / "evidence.sqlite"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    for migration in sorted(Path("migrations").glob("*.sql")):
        connection.executescript(migration.read_text(encoding="utf-8"))
    connection.execute(
        """INSERT INTO task (stock_id, fiscal_year, report_period, state, engine)
           VALUES (?, ?, ?, 'undone', ?)""",
        (stock, year, period, engine),
    )
    connection.commit()
    connection.close()
    return path


def _capture(tmp_path: Path, *, period: str | None = "2024/01/01~2024/03/31",
             scheduled: bool = False, speech_time: str = "14:48:53",
             fiscal_year: int = 2024, report_period: str = "Q1",
             speech_date: str = "2024/05/10", extra: str = ""):
    period_label = "年度" if report_period == "FY" else f"年第{report_period[1]}季"
    url_subject = f"公告本公司董事會通過{fiscal_year - 1911}{period_label}合併財務報告"
    visible_subject = f"公告本公司董事會通過{fiscal_year}{period_label}合併財務報告"
    detail_url = "https://goodinfo.tw/tw/StockAnnounceDetail.asp?" + urlencode({
        "STOCK_ID": "2330", "CLAIM_TIME": f"{speech_date} {speech_time}",
        "SUBJECT": url_subject,
    })
    candidate = GoodinfoListCandidate(
        f"台積電董事會通過{fiscal_year}{period_label}合併財務報告", detail_url,
        "https://goodinfo.tw/tw/StockAnnounceList.asp", "sha256:list",
        (ReportPeriod.parse(report_period),), ("合併",), scheduled,
    )
    explanation = (
        f"3.財務報告報導期間起訖日期:{period}"
        if period is not None else "3.其他應敘明事項:無"
    )
    body = (
        "<html><head><title>2330 台積電 公告訊息 - Goodinfo</title></head>"
        f"<body><table><tr><td>發言日期</td><td>{speech_date}</td>"
        f"<td>發言時間</td><td>{speech_time}</td></tr>"
        f"<tr><td>主旨</td><td>{visible_subject}</td></tr>"
        f"<tr><td>說　明</td><td>{explanation}{extra}</td></tr></table></body></html>"
    ).encode()

    class Response:
        status = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return body

        def geturl(self):
            return detail_url

    return capture_goodinfo_detail(
        candidate, tmp_path / "captures", opener=lambda request, **_: Response(),
        clock=lambda: datetime(2026, 9, 24, 12, 34, 56, tzinfo=timezone.utc),
    )


def test_accepts_speech_time_as_second_precision_announcement(tmp_path: Path) -> None:
    database = _database(tmp_path)
    capture = _capture(tmp_path)
    stored = accept_goodinfo_announcement(
        database, 1, capture, fiscal_calendar="calendar_year",
    )
    with connect_database(database) as connection:
        row = connection.execute(
            """SELECT evidence_type, event_date, event_time, event_precision,
                      source_type, source_endpoint, source_url, source_locator,
                      source_title, source_subject, retrieved_at, raw_payload_hash,
                      raw_snapshot_path, verification_state
               FROM evidence WHERE id = ?""", (stored.id,),
        ).fetchone()
        task = connection.execute("SELECT state, engine FROM task WHERE id = 1").fetchone()
    assert row == (
        "material_announcement", "2024-05-10", "14:48:53", "second",
        "goodinfo", "StockAnnounceDetail.asp", capture.candidate.detail_url,
        capture.candidate.detail_url, None,
        "公告本公司董事會通過2024年第1季合併財務報告",
        "2026-09-24T12:34:56.000Z", capture.raw_payload_hash,
        None, "unverified",
    )
    assert stored.raw_payload_hash == capture.raw_payload_hash
    assert task == ("undone", "goodinfo")
    repeated = accept_goodinfo_announcement(
        database, 1, capture, fiscal_calendar="calendar_year",
    )
    assert repeated == stored
    with connect_database(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 1


@pytest.mark.parametrize("report_period,report_dates,speech_date", [
    ("Q2", "2024/01/01~2024/06/30", "2024/08/14"),
    ("FY", "2024/01/01~2024/12/31", "2025/03/10"),
])
def test_other_calendar_year_periods_keep_source_speech_time(
    tmp_path: Path, report_period: str, report_dates: str, speech_date: str,
) -> None:
    database = _database(tmp_path, period=report_period)
    capture = _capture(
        tmp_path, period=report_dates, report_period=report_period, speech_date=speech_date,
    )
    stored = accept_goodinfo_announcement(
        database, 1, capture, fiscal_calendar="calendar_year",
    )
    with connect_database(database) as connection:
        event = connection.execute(
            "SELECT event_date, event_time, event_precision FROM evidence WHERE id = ?",
            (stored.id,),
        ).fetchone()
    assert event == (speech_date.replace("/", "-"), "14:48:53", "second")


def test_changed_raw_detail_appends_new_immutable_evidence(tmp_path: Path) -> None:
    database = _database(tmp_path)
    first = _capture(tmp_path)
    revised = _capture(tmp_path / "revision", extra="<br>4.其他應敘明事項:更正")
    original_row = accept_goodinfo_announcement(
        database, 1, first, fiscal_calendar="calendar_year",
    )
    revised_row = accept_goodinfo_announcement(
        database, 1, revised, fiscal_calendar="calendar_year",
    )
    assert revised_row.id != original_row.id
    assert revised_row.raw_payload_hash != original_row.raw_payload_hash
    with connect_database(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 2


@pytest.mark.parametrize("changes", [
    {"stock": "2317"}, {"year": 2023}, {"period": "Q2"}, {"engine": "mops"},
])
def test_wrong_task_identity_or_engine_is_rejected(tmp_path: Path, changes: dict) -> None:
    database = _database(tmp_path, **changes)
    capture = _capture(tmp_path)
    with pytest.raises(ValueError, match="task"):
        accept_goodinfo_announcement(database, 1, capture, fiscal_calendar="calendar_year")
    with connect_database(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 0


def test_missing_period_and_scheduled_meeting_cannot_be_accepted(tmp_path: Path) -> None:
    database = _database(tmp_path)
    missing = _capture(tmp_path, period=None)
    with pytest.raises(ValueError, match="period"):
        accept_goodinfo_announcement(database, 1, missing, fiscal_calendar="calendar_year")
    scheduled = _capture(tmp_path / "scheduled", scheduled=True)
    with pytest.raises(ValueError, match="scheduled"):
        accept_goodinfo_announcement(database, 1, scheduled, fiscal_calendar="calendar_year")


def test_subject_period_cannot_contradict_report_period(tmp_path: Path) -> None:
    database = _database(tmp_path, period="Q2")
    capture = _capture(tmp_path, period="2024/01/01~2024/06/30")
    with pytest.raises(ValueError, match="subject period"):
        accept_goodinfo_announcement(database, 1, capture, fiscal_calendar="calendar_year")


def test_raw_tampering_or_unverified_calendar_is_rejected(tmp_path: Path) -> None:
    database = _database(tmp_path)
    capture = _capture(tmp_path)
    with pytest.raises(ValueError, match="calendar"):
        accept_goodinfo_announcement(database, 1, capture, fiscal_calendar="unknown")
    capture.body_path.write_bytes(capture.body_path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="provenance"):
        accept_goodinfo_announcement(database, 1, capture, fiscal_calendar="calendar_year")


def test_invalid_capture_metadata_retrieval_time_is_rejected(tmp_path: Path) -> None:
    database = _database(tmp_path)
    capture = _capture(tmp_path)
    metadata = json.loads(capture.metadata_path.read_text())
    metadata["retrieved_at"] = "2024-05-10T14:48:53"
    capture.metadata_path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="timezone"):
        accept_goodinfo_announcement(database, 1, capture, fiscal_calendar="calendar_year")
    with connect_database(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 0


def test_contract_distinguishes_announcement_from_xbrl_confirmation() -> None:
    contract = json.loads(Path("contracts/goodinfo-announcement-evidence.json").read_text())
    assert contract["event_mapping"] == {
        "evidence_type": "material_announcement",
        "source_type": "goodinfo",
        "event_date": "visible_speech_date",
        "event_time": "visible_speech_time",
        "event_precision": "second",
    }
    assert contract["xbrl_confirmed_at"] is None
    assert contract["completes_task"] is False
    assert contract["requires_migration"] is False
