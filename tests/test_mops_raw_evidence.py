"""Step-31 raw payload and optional snapshot persistence regressions."""

import gzip
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from xbrlswarm.discovery.cases import DISCOVERY_CASES
from xbrlswarm.discovery.mops import build_mops_xbrl_capture
from xbrlswarm.mops_evidence import accept_mops_response
from xbrlswarm.storage import connect_database


MIGRATIONS = Path("migrations")
CASE = next(case for case in DISCOVERY_CASES if case.key == "2330-2024-Q1")
URL = build_mops_xbrl_capture(CASE).url
BODY = gzip.decompress(
    Path("tests/fixtures/discovery/mops/2330/2024/Q1/xbrl-consolidated.bin.gz").read_bytes()
)
NOW = datetime(2026, 9, 24, 12, 34, 56, tzinfo=timezone.utc)


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "evidence.sqlite"
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    for migration in sorted(MIGRATIONS.glob("*.sql")):
        connection.executescript(migration.read_text(encoding="utf-8"))
    connection.execute(
        """INSERT INTO task (stock_id, fiscal_year, report_period, state, engine)
           VALUES ('2330', 2024, 'Q1', 'undone', 'mops')"""
    )
    connection.commit()
    connection.close()
    return path


def _accept(path: Path, body: bytes = BODY, **changes):
    arguments = {
        "source_url": URL,
        "retrieved_at": NOW,
        **changes,
    }
    return accept_mops_response(path, 1, CASE, body, **arguments)


def test_accepted_mops_evidence_always_persists_exact_raw_hash(tmp_path: Path) -> None:
    database = _database(tmp_path)
    stored = _accept(database)
    expected_hash = "sha256:" + hashlib.sha256(BODY).hexdigest()
    assert stored.raw_payload_hash == expected_hash
    assert stored.raw_snapshot_path is None

    with connect_database(database) as connection:
        row = connection.execute(
            """SELECT evidence_type, source_type, source_url, source_locator,
                      raw_payload_hash, raw_snapshot_path, retrieved_at,
                      company_name, event_date, event_time, event_precision,
                      verification_state FROM evidence WHERE id = ?""",
            (stored.id,),
        ).fetchone()
    assert row == (
        "xbrl_document", "mops", URL, URL, expected_hash, None,
        "2026-09-24T12:34:56.000Z", "台灣積體電路製造股份有限公司",
        None, None, None, "unverified",
    )


def test_snapshot_policy_stores_lossless_content_addressed_raw_bytes(tmp_path: Path) -> None:
    database = _database(tmp_path)
    root = tmp_path / "raw"
    stored = _accept(database, snapshot_root=root)
    digest = hashlib.sha256(BODY).hexdigest()
    expected = root / digest[:2] / digest[2:4] / f"{digest}.bin"
    assert stored.raw_snapshot_path == str(expected)
    assert expected.read_bytes() == BODY

    repeated = _accept(database, snapshot_root=root, retrieved_at=NOW.replace(hour=13))
    assert repeated == stored
    with connect_database(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 1
        assert connection.execute(
            "SELECT raw_snapshot_path FROM evidence WHERE id = ?", (stored.id,)
        ).fetchone() == (str(expected),)


def test_changed_raw_bytes_append_a_new_evidence_row(tmp_path: Path) -> None:
    database = _database(tmp_path)
    original = _accept(database)
    revised = _accept(database, BODY + b"\n")
    assert revised.id != original.id
    assert revised.raw_payload_hash != original.raw_payload_hash
    with connect_database(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 2


def test_invalid_response_or_task_cannot_be_accepted(tmp_path: Path) -> None:
    database = _database(tmp_path)
    with pytest.raises(ValueError):
        _accept(database, "<html>查無資料</html>".encode(), snapshot_root=tmp_path / "raw")
    with pytest.raises(ValueError, match="task"):
        accept_mops_response(database, 999, CASE, BODY, source_url=URL, retrieved_at=NOW)
    with pytest.raises(ValueError, match="retrieved_at"):
        _accept(database, retrieved_at=datetime(2026, 9, 24))
    with connect_database(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 0
    assert not (tmp_path / "raw").exists()


def test_immutable_snapshot_cannot_be_replaced_or_added_to_old_row(tmp_path: Path) -> None:
    database = _database(tmp_path)
    root = tmp_path / "raw"
    stored = _accept(database, snapshot_root=root)
    path = Path(stored.raw_snapshot_path)
    with connect_database(database) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable source evidence"):
            connection.execute(
                "UPDATE evidence SET raw_snapshot_path = NULL WHERE id = ?", (stored.id,)
            )

    path.write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="snapshot"):
        _accept(database, snapshot_root=root)
    assert path.read_bytes() == b"corrupted"

    # A hash-only historical row cannot be rewritten when policy is enabled later.
    another = _accept(database, BODY + b"\n")
    assert another.raw_snapshot_path is None
    with pytest.raises(ValueError, match="raw snapshot"):
        _accept(database, BODY + b"\n", snapshot_root=root)


def test_migration_preserves_earlier_evidence_and_adds_immutable_path(tmp_path: Path) -> None:
    database = tmp_path / "earlier.sqlite"
    connection = sqlite3.connect(database)
    for migration in sorted(MIGRATIONS.glob("*.sql")):
        if migration.name == "0009_add_raw_snapshot_path.sql":
            break
        connection.executescript(migration.read_text(encoding="utf-8"))
    connection.execute(
        """INSERT INTO task (stock_id, fiscal_year, report_period, state, engine)
           VALUES ('2330', 2024, 'Q1', 'undone', 'mops')"""
    )
    connection.execute(
        """INSERT INTO evidence (task_id, evidence_type, source_type,
                                  retrieved_at, verification_state)
           VALUES (1, 'xbrl_document', 'mops', '2026-09-24T00:00:00.000Z', 'unverified')"""
    )
    connection.commit()
    connection.executescript(
        (MIGRATIONS / "0009_add_raw_snapshot_path.sql").read_text(encoding="utf-8")
    )
    assert connection.execute(
        "SELECT raw_snapshot_path FROM evidence WHERE id = 1"
    ).fetchone() == (None,)
    connection.close()
    with connect_database(database) as checked:
        assert checked.execute("SELECT COUNT(*) FROM evidence").fetchone()[0] == 1
