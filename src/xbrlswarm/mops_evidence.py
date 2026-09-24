"""Accept parsed MOPS responses with their exact raw payload provenance."""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from xbrlswarm.discovery.models import DiscoveryCase
from xbrlswarm.mops_parser import parse_mops_report
from xbrlswarm.storage import connect_database


@dataclass(frozen=True, slots=True)
class StoredMopsEvidence:
    id: int
    raw_payload_hash: str
    raw_snapshot_path: str | None


def _snapshot(root: Path, digest: str, body: bytes) -> str:
    directory = root.resolve() / digest[:2] / digest[2:4]
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{digest}.bin"
    fd, temporary = tempfile.mkstemp(prefix=f".{digest}.", dir=directory)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.is_symlink() or path.read_bytes() != body:
                raise ValueError(f"既有 MOPS raw snapshot 與 payload 不一致：{path}")
    finally:
        Path(temporary).unlink(missing_ok=True)
    return str(path)


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("retrieved_at must be timezone aware")
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def accept_mops_response(
    database: str | Path,
    task_id: int,
    case: DiscoveryCase,
    body: bytes,
    *,
    source_url: str,
    retrieved_at: datetime,
    snapshot_root: str | Path | None = None,
) -> StoredMopsEvidence:
    """Insert a verified MOPS document; opt in to a lossless raw snapshot."""

    if not Path(database).is_file():
        raise FileNotFoundError(f"database file does not exist: {database}")
    timestamp = _timestamp(retrieved_at)
    parsed = parse_mops_report(case, body, source_url=source_url)
    digest = hashlib.sha256(body).hexdigest()
    payload_hash = f"sha256:{digest}"
    connection = connect_database(database)
    try:
        connection.execute("BEGIN IMMEDIATE")
        task = connection.execute(
            "SELECT stock_id, fiscal_year, report_period, engine FROM task WHERE id = ?",
            (task_id,),
        ).fetchone()
        if task != (case.stock_id, case.fiscal_year, case.report_period.value, "mops"):
            raise ValueError("MOPS evidence 與 task 身份或 engine 不一致")

        existing = connection.execute(
            """SELECT id, raw_snapshot_path FROM evidence
               WHERE task_id = ? AND source_type = 'mops'
                 AND evidence_type = 'xbrl_document'
                 AND source_locator = ? AND raw_payload_hash = ?
                 AND event_date IS NULL AND event_time IS NULL
                 AND event_precision IS NULL""",
            (task_id, parsed.source_locator, payload_hash),
        ).fetchone()
        if existing is not None:
            evidence_id, snapshot_path = existing
            if snapshot_root is not None:
                if snapshot_path is None:
                    raise ValueError("既有 evidence 沒有 raw snapshot，不能改寫不可變歷史")
                expected_path = (
                    Path(snapshot_root).resolve() / digest[:2] / digest[2:4] / f"{digest}.bin"
                )
                if Path(snapshot_path) != expected_path or expected_path.is_symlink() or expected_path.read_bytes() != body:
                    raise ValueError("既有 raw snapshot 路徑或內容與 payload 不一致")
            connection.commit()
            return StoredMopsEvidence(evidence_id, payload_hash, snapshot_path)

        snapshot_path = (
            _snapshot(Path(snapshot_root), digest, body) if snapshot_root is not None else None
        )
        cursor = connection.execute(
            """INSERT INTO evidence (
                 task_id, evidence_type, source_type, source_endpoint,
                 source_url, source_locator, retrieved_at, raw_payload_hash,
                 verification_state, company_name, raw_snapshot_path
               ) VALUES (?, 'xbrl_document', 'mops', 'FileDownLoad',
                         ?, ?, ?, ?, 'unverified', ?, ?)""",
            (
                task_id,
                source_url,
                parsed.source_locator,
                timestamp,
                payload_hash,
                parsed.company_name,
                snapshot_path,
            ),
        )
        connection.commit()
        assert cursor.lastrowid is not None
        return StoredMopsEvidence(cursor.lastrowid, payload_hash, snapshot_path)
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()
