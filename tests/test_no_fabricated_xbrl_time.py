import json
import sqlite3
from pathlib import Path

from xbrlswarm.domain import announcement_event_fields


CONTRACT = Path("contracts/xbrl-confirmation-time.json")
DECISION = Path("docs/no-fabricated-xbrl-time.md")
ACCEPTANCE = Path("docs/step-16-acceptance.md")


def _evidence_columns() -> set[str]:
    connection = sqlite3.connect(":memory:")
    try:
        for migration in sorted(Path("migrations").glob("*.sql")):
            connection.executescript(migration.read_text(encoding="utf-8"))
        return {row[1] for row in connection.execute("PRAGMA table_info(evidence)")}
    finally:
        connection.close()


def test_announcement_event_never_claims_xbrl_confirmation() -> None:
    fields = announcement_event_fields(
        speech_date="2024-05-10", speech_time="14:48:53"
    )

    assert fields == {
        "evidence_type": "material_announcement",
        "event_date": "2024-05-10",
        "event_time": "14:48:53",
        "event_precision": "second",
    }
    assert "xbrl_confirmed_at" not in fields


def test_production_schema_cannot_store_unverified_confirmation_time() -> None:
    assert "xbrl_confirmed_at" not in _evidence_columns()


def test_discovery_keeps_confirmation_time_unverified() -> None:
    matrix = json.loads(
        Path("discovery/source_field_matrix.json").read_text(encoding="utf-8")
    )
    confirmed = next(
        field for field in matrix["fields"] if field["field"] == "xbrl_confirmed_at"
    )
    assert confirmed["status"] == "not_verified"


def test_contract_rejects_all_semantic_time_substitutes() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    assert contract == {
        "contract": "xbrl_confirmation_time",
        "version": 1,
        "historical_status": "not_publicly_verified",
        "confirmation_field": "xbrl_confirmed_at",
        "prohibited_substitutes": [
            "announcement_at",
            "article_published_at",
            "retrieved_at",
            "http_date",
            "http_last_modified",
        ],
        "prohibited_operation": "rename_or_derive",
        "schema_field_allowed_without_source_evidence": False,
    }


def test_step16_documents_event_boundaries() -> None:
    decision = DECISION.read_text(encoding="utf-8")
    acceptance = ACCEPTANCE.read_text(encoding="utf-8")

    for field in (
        "announcement_at",
        "article_published_at",
        "retrieved_at",
        "http_date",
        "http_last_modified",
        "xbrl_confirmed_at",
    ):
        assert field in decision
    assert "不需要 migration" in acceptance
