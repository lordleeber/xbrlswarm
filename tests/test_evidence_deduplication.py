import sqlite3
from pathlib import Path
from typing import Any

import pytest


MIGRATIONS_DIR = Path("migrations")
STEP12_LAST_MIGRATION_PATH = Path("migrations/0004_add_evidence_metadata.sql")
DEDUPLICATION_MIGRATION_PATH = Path(
    "migrations/0005_add_evidence_deduplication.sql"
)
DECISION_PATH = Path("docs/evidence-deduplication.md")
ACCEPTANCE_PATH = Path("docs/step-13-acceptance.md")


def _apply(connection: sqlite3.Connection, path: Path) -> None:
    connection.executescript(path.read_text(encoding="utf-8"))


def _database(*, through_step12: bool = False) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if through_step12 and path > STEP12_LAST_MIGRATION_PATH:
            continue
        _apply(connection, path)
    return connection


def _insert_task(connection: sqlite3.Connection, stock_id: str = "2330") -> int:
    cursor = connection.execute(
        """
        INSERT INTO task (stock_id, fiscal_year, report_period, state, engine)
        VALUES (?, 2024, 'Q1', 'undone', 'mops')
        """,
        (stock_id,),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _mops_evidence(task_id: int, **changes: Any) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "task_id": task_id,
        "evidence_type": "xbrl_document",
        "event_date": None,
        "event_time": None,
        "event_precision": None,
        "source_type": "mops",
        "source_endpoint": "xbrl-download",
        "source_url": "https://mops.example/first",
        "source_locator": "mops:xbrl:2330:2024:Q1:consolidated",
        "source_title": "Financial report",
        "source_subject": None,
        "retrieved_at": "2026-09-23T01:02:03.000Z",
        "raw_payload_hash": "sha256:abc123",
        "verification_state": "unverified",
        "company_name": "台灣積體電路製造股份有限公司",
    }
    evidence.update(changes)
    return evidence


def _goodinfo_evidence(task_id: int, **changes: Any) -> dict[str, Any]:
    evidence = _mops_evidence(
        task_id,
        evidence_type="material_announcement",
        event_date="2025-02-20",
        event_time="14:35:01",
        event_precision="second",
        source_type="goodinfo",
        source_endpoint="StockAnnounceDetail.asp",
        source_url="https://goodinfo.tw/tw/StockAnnounceDetail.asp?CLAIM_TIME=...",
        source_locator="goodinfo:2330:2025-02-20T14:35:01:subject-hash",
        source_title="重大訊息",
        source_subject="公告本公司董事會通過財務報告",
        raw_payload_hash=None,
    )
    evidence.update(changes)
    return evidence


def _insert_evidence(
    connection: sqlite3.Connection,
    evidence: dict[str, Any],
    *,
    ignore_duplicate: bool = False,
) -> None:
    conflict_clause = "ON CONFLICT DO NOTHING" if ignore_duplicate else ""
    connection.execute(
        f"""
        INSERT INTO evidence (
            task_id,
            evidence_type,
            event_date,
            event_time,
            event_precision,
            source_type,
            source_endpoint,
            source_url,
            source_locator,
            source_title,
            source_subject,
            retrieved_at,
            raw_payload_hash,
            verification_state,
            company_name
        ) VALUES (
            :task_id,
            :evidence_type,
            :event_date,
            :event_time,
            :event_precision,
            :source_type,
            :source_endpoint,
            :source_url,
            :source_locator,
            :source_title,
            :source_subject,
            :retrieved_at,
            :raw_payload_hash,
            :verification_state,
            :company_name
        ) {conflict_clause}
        """,
        evidence,
    )


def _count(connection: sqlite3.Connection) -> int:
    return connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]


def test_step13_adds_source_specific_partial_unique_indexes() -> None:
    connection = _database()
    indexes = {
        row[1]: connection.execute(
            "SELECT sql FROM sqlite_schema WHERE type = 'index' AND name = ?",
            (row[1],),
        ).fetchone()[0]
        for row in connection.execute("PRAGMA index_list(evidence)")
        if row[2]
    }

    assert {
        "evidence_mops_logical_identity_unique",
        "evidence_goodinfo_logical_identity_unique",
    } <= set(indexes)
    assert "WHERE source_type = 'mops'" in indexes[
        "evidence_mops_logical_identity_unique"
    ]
    assert "WHERE source_type = 'goodinfo'" in indexes[
        "evidence_goodinfo_logical_identity_unique"
    ]


def test_mops_crawl_once_and_twice_stores_one_logical_evidence() -> None:
    connection = _database()
    evidence = _mops_evidence(_insert_task(connection))

    _insert_evidence(connection, evidence, ignore_duplicate=True)
    _insert_evidence(
        connection,
        {
            **evidence,
            "retrieved_at": "2026-09-24T05:06:07.000Z",
            "source_url": "https://mops.example/retry",
            "verification_state": "corroborated",
            "company_name": "台積電",
        },
        ignore_duplicate=True,
    )

    assert _count(connection) == 1


@pytest.mark.parametrize("evidence_factory", [_mops_evidence, _goodinfo_evidence])
def test_direct_duplicate_insert_is_rejected_by_the_database(
    evidence_factory: Any,
) -> None:
    connection = _database()
    evidence = evidence_factory(_insert_task(connection))
    _insert_evidence(connection, evidence)

    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE constraint failed"):
        _insert_evidence(connection, evidence)


def test_mops_new_payload_is_preserved_as_new_evidence() -> None:
    connection = _database()
    evidence = _mops_evidence(_insert_task(connection))

    _insert_evidence(connection, evidence)
    _insert_evidence(connection, {**evidence, "raw_payload_hash": "sha256:def456"})

    assert _count(connection) == 2


def test_null_sentinel_does_not_collide_with_source_empty_text() -> None:
    connection = _database()
    task_id = _insert_task(connection)
    mops = _mops_evidence(task_id)
    goodinfo = _goodinfo_evidence(task_id)

    _insert_evidence(connection, mops)
    _insert_evidence(connection, {**mops, "event_date": ""})
    _insert_evidence(connection, goodinfo)
    _insert_evidence(connection, {**goodinfo, "raw_payload_hash": ""})

    assert _count(connection) == 4


def test_goodinfo_retry_without_payload_hash_is_idempotent() -> None:
    connection = _database()
    evidence = _goodinfo_evidence(_insert_task(connection))

    _insert_evidence(connection, evidence, ignore_duplicate=True)
    _insert_evidence(
        connection,
        {**evidence, "retrieved_at": "2026-09-24T05:06:07.000Z"},
        ignore_duplicate=True,
    )

    assert _count(connection) == 1


def test_goodinfo_new_announcement_and_payload_are_preserved() -> None:
    connection = _database()
    evidence = _goodinfo_evidence(_insert_task(connection))

    _insert_evidence(connection, evidence)
    _insert_evidence(
        connection,
        {
            **evidence,
            "source_locator": "goodinfo:2330:2025-02-20T15:00:00:other",
            "event_time": "15:00:00",
            "source_subject": "另一則公告",
        },
    )
    _insert_evidence(connection, {**evidence, "raw_payload_hash": "sha256:abc123"})
    _insert_evidence(connection, {**evidence, "raw_payload_hash": "sha256:def456"})

    assert _count(connection) == 4


def test_different_sources_are_preserved_independently() -> None:
    connection = _database()
    task_id = _insert_task(connection)

    _insert_evidence(connection, _mops_evidence(task_id))
    _insert_evidence(connection, _goodinfo_evidence(task_id))

    assert _count(connection) == 2


@pytest.mark.parametrize(
    "evidence_factory,missing_field",
    [
        (_mops_evidence, "source_locator"),
        (_mops_evidence, "raw_payload_hash"),
        (_goodinfo_evidence, "event_time"),
        (_goodinfo_evidence, "source_subject"),
    ],
)
def test_unresolved_identity_is_not_automatically_folded(
    evidence_factory: Any,
    missing_field: str,
) -> None:
    connection = _database()
    evidence = evidence_factory(_insert_task(connection), **{missing_field: None})

    _insert_evidence(connection, evidence, ignore_duplicate=True)
    _insert_evidence(connection, evidence, ignore_duplicate=True)

    assert _count(connection) == 2


def test_unmapped_source_is_not_automatically_folded() -> None:
    connection = _database()
    evidence = _mops_evidence(_insert_task(connection), source_type="cnyes")

    _insert_evidence(connection, evidence, ignore_duplicate=True)
    _insert_evidence(connection, evidence, ignore_duplicate=True)

    assert _count(connection) == 2


def test_step13_migration_preserves_existing_evidence() -> None:
    connection = _database(through_step12=True)
    evidence = _mops_evidence(_insert_task(connection))
    _insert_evidence(connection, evidence)
    before = connection.execute("SELECT * FROM evidence").fetchall()

    _apply(connection, DEDUPLICATION_MIGRATION_PATH)

    assert connection.execute("SELECT * FROM evidence").fetchall() == before


@pytest.mark.parametrize("evidence_factory", [_mops_evidence, _goodinfo_evidence])
def test_step13_migration_rejects_preexisting_duplicates_without_partial_change(
    evidence_factory: Any,
) -> None:
    connection = _database(through_step12=True)
    evidence = evidence_factory(_insert_task(connection))
    _insert_evidence(connection, evidence)
    _insert_evidence(connection, evidence)
    connection.commit()

    with pytest.raises(sqlite3.IntegrityError, match="CHECK constraint failed"):
        _apply(connection, DEDUPLICATION_MIGRATION_PATH)

    assert connection.in_transaction is False
    assert _count(connection) == 2
    assert [row for row in connection.execute("PRAGMA index_list(evidence)") if row[2]] == []


def test_step13_documents_conflict_handling_and_boundaries() -> None:
    decision = DECISION_PATH.read_text(encoding="utf-8")
    acceptance = ACCEPTANCE_PATH.read_text(encoding="utf-8")

    for phrase in (
        "ON CONFLICT DO NOTHING",
        "unresolved",
        "MOPS",
        "Goodinfo",
        "Step-14",
    ):
        assert phrase in decision
    assert "0005_add_evidence_deduplication.sql" in acceptance
