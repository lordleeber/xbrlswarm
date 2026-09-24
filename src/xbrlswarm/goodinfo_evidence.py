"""Persist a verified Goodinfo speech time as an announcement event."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .domain import ReportPeriod, announcement_event_fields, calendar_year_period_end
from .goodinfo_candidates import _period_hints
from .goodinfo_detail import GoodinfoDetailCapture, parse_captured_goodinfo_detail
from .goodinfo_locator import goodinfo_announcement_locator, _same_stored_locator
from .storage import connect_database


@dataclass(frozen=True, slots=True)
class StoredGoodinfoAnnouncement:
    id: int
    raw_payload_hash: str


def _retrieved_at(metadata_path: Path) -> str:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("source_type") != "goodinfo" or metadata["response"].get("http_status") != 200:
        raise ValueError("Goodinfo detail capture metadata is not an accepted response")
    try:
        value = datetime.fromisoformat(metadata["retrieved_at"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, ValueError) as error:
        raise ValueError("invalid Goodinfo retrieved_at") from error
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Goodinfo retrieved_at must contain a timezone")
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def accept_goodinfo_announcement(
    database: str | Path,
    task_id: int,
    capture: GoodinfoDetailCapture,
    *,
    fiscal_calendar: str,
) -> StoredGoodinfoAnnouncement:
    """Save only a matched, published detail's source-claimed speech event.

    The caller must independently establish the company's historical fiscal
    calendar; only calendar-year tasks can currently be checked.
    """

    if not Path(database).is_file():
        raise FileNotFoundError(f"database file does not exist: {database}")
    if fiscal_calendar != "calendar_year":
        raise ValueError("Goodinfo announcement requires a verified calendar-year fiscal calendar")
    detail = parse_captured_goodinfo_detail(capture)
    if detail.scheduled_meeting:
        raise ValueError("scheduled board meeting is not a published report announcement")
    if detail.period_start is None or detail.period_end is None:
        raise ValueError("Goodinfo detail lacks a report period for task matching")
    retrieved_at = _retrieved_at(capture.metadata_path)
    claim_time = detail.claim_time
    event = announcement_event_fields(
        speech_date=claim_time.date().isoformat(),
        speech_time=claim_time.time().isoformat(timespec="seconds"),
    )
    locator = goodinfo_announcement_locator(detail.detail_url)

    connection = connect_database(database)
    try:
        connection.execute("BEGIN IMMEDIATE")
        task = connection.execute(
            "SELECT stock_id, fiscal_year, report_period, engine FROM task WHERE id = ?",
            (task_id,),
        ).fetchone()
        if task is None or task[0] != detail.stock_id or task[3] != "goodinfo":
            raise ValueError("Goodinfo detail does not match task stock or engine")
        expected_end = calendar_year_period_end(task[1], task[2])
        if detail.period_start != expected_end.replace(month=1, day=1) or detail.period_end != expected_end:
            raise ValueError("Goodinfo detail report period does not match task")
        if _period_hints(detail.subject) != (ReportPeriod.parse(task[2]),):
            raise ValueError("Goodinfo detail subject period does not match task")

        existing = connection.execute(
            """SELECT id FROM evidence
               WHERE task_id = ? AND source_type = 'goodinfo'
                 AND evidence_type = 'material_announcement'
                 AND source_locator = ? AND source_subject = ?
                 AND event_date = ? AND event_time = ?
                 AND COALESCE(event_precision, 'second') = 'second'
                 AND raw_payload_hash = ?""",
            (task_id, locator, detail.subject,
             event["event_date"], event["event_time"], detail.raw_payload_hash),
        ).fetchone()
        legacy_rows = connection.execute(
            """SELECT id, source_locator FROM evidence
               WHERE task_id = ? AND source_type = 'goodinfo'
                 AND evidence_type = 'material_announcement'
                 AND source_locator LIKE 'https://goodinfo.tw/%'
                 AND source_subject = ? AND event_date = ? AND event_time = ?
                 AND COALESCE(event_precision, 'second') = 'second'
                 AND raw_payload_hash = ?""",
            (task_id, detail.subject, event["event_date"],
             event["event_time"], detail.raw_payload_hash),
        ).fetchall()
        legacy_matches = [row_id for row_id, stored_locator in legacy_rows
                          if _same_stored_locator(stored_locator, locator)]
        matches = ([existing[0]] if existing is not None else []) + legacy_matches
        if len(matches) > 1:
            raise ValueError("ambiguous Goodinfo evidence identity")
        if matches:
            connection.commit()
            return StoredGoodinfoAnnouncement(matches[0], detail.raw_payload_hash)

        cursor = connection.execute(
            """INSERT INTO evidence (
                 task_id, evidence_type, event_date, event_time, event_precision,
                 source_type, source_endpoint, source_url, source_locator,
                 source_subject, retrieved_at, raw_payload_hash,
                 verification_state
               ) VALUES (
                 :task_id, :evidence_type, :event_date, :event_time, :event_precision,
                 'goodinfo', 'StockAnnounceDetail.asp', :source_url, :source_locator,
                 :source_subject, :retrieved_at, :raw_payload_hash,
                 'unverified'
               )""",
            {**event, "task_id": task_id, "source_url": detail.final_url,
             "source_locator": locator,
             "source_subject": detail.subject, "retrieved_at": retrieved_at,
             "raw_payload_hash": detail.raw_payload_hash},
        )
        connection.commit()
        assert cursor.lastrowid is not None
        return StoredGoodinfoAnnouncement(cursor.lastrowid, detail.raw_payload_hash)
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
