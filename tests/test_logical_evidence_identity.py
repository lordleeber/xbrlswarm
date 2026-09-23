import json
import sqlite3
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path("contracts/logical-evidence-identity.json")
DECISION_PATH = Path("docs/logical-evidence-identity.md")
ACCEPTANCE_PATH = Path("docs/step-12-acceptance.md")
MIGRATIONS_DIR = Path("migrations")


def _load_contract() -> dict[str, Any]:
    value = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _compare(
    contract: dict[str, Any],
    left: dict[str, Any],
    right: dict[str, Any],
) -> str:
    if any(left.get(field) != right.get(field) for field in contract["fields"]):
        return contract["resolution"]["any_field_different_outcome"]
    required = contract["resolution"]["required_non_null"]
    if any(left.get(field) is None or right.get(field) is None for field in required):
        return contract["resolution"]["missing_required_outcome"]
    return contract["resolution"]["all_fields_equal_outcome"]


def _base_evidence() -> dict[str, Any]:
    return {
        "task_id": 42,
        "source_type": "mops",
        "source_locator": "mops:xbrl:2330:2024:Q1:consolidated",
        "evidence_type": "xbrl_document",
        "event_date": None,
        "event_time": None,
        "event_precision": None,
        "raw_payload_hash": "sha256:abc123",
        "retrieved_at": "2026-09-23T01:02:03.000Z",
        "source_url": "https://example.test/first",
        "verification_state": "unverified",
        "company_name": "台灣積體電路製造股份有限公司",
    }


def test_contract_defines_the_five_roadmap_identity_dimensions() -> None:
    contract = _load_contract()

    assert contract["contract"] == "logical_evidence_identity"
    assert contract["version"] == 1
    assert contract["identity_kind"] == "logical_evidence"
    assert contract["comparison"] == "exact_stored_value"
    assert contract["groups"] == {
        "task": ["task_id"],
        "source": ["source_type"],
        "source_locator": ["source_locator"],
        "event": [
            "evidence_type",
            "event_date",
            "event_time",
            "event_precision",
        ],
        "payload": ["raw_payload_hash"],
    }
    assert contract["fields"] == [
        "task_id",
        "source_type",
        "source_locator",
        "evidence_type",
        "event_date",
        "event_time",
        "event_precision",
        "raw_payload_hash",
    ]


def test_identity_fields_exist_in_the_production_evidence_schema() -> None:
    connection = sqlite3.connect(":memory:")
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        connection.executescript(path.read_text(encoding="utf-8"))
    columns = {row[1] for row in connection.execute("PRAGMA table_info(evidence)")}

    assert set(_load_contract()["fields"]) <= columns


def test_retrieval_and_descriptive_metadata_do_not_create_new_evidence() -> None:
    contract = _load_contract()
    left = _base_evidence()
    right = {
        **left,
        "retrieved_at": "2026-09-24T05:06:07.000Z",
        "source_url": "https://example.test/retry",
        "verification_state": "corroborated",
        "company_name": "台積電",
    }

    assert set(contract["non_identity_fields"]) == {
        "id",
        "source_endpoint",
        "source_url",
        "source_title",
        "source_subject",
        "retrieved_at",
        "verification_state",
        "company_name",
    }
    assert _compare(contract, left, right) == "same"


def test_new_payload_event_source_or_task_is_different_evidence() -> None:
    contract = _load_contract()
    original = _base_evidence()

    changes = (
        {"task_id": 43},
        {"source_type": "goodinfo"},
        {"source_locator": "goodinfo:announcement:123"},
        {"evidence_type": "material_announcement"},
        {"event_date": "2025-02-20"},
        {"event_time": "14:35:01"},
        {"event_precision": "second"},
        {"raw_payload_hash": "sha256:def456"},
    )

    for change in changes:
        assert _compare(contract, original, {**original, **change}) == "different"


def test_missing_locator_or_payload_keeps_identity_unresolved() -> None:
    contract = _load_contract()
    original = _base_evidence()

    assert contract["resolution"] == {
        "evaluation_order": [
            "different_if_any_field_differs",
            "unresolved_if_required_missing",
            "same",
        ],
        "required_non_null": ["source_locator", "raw_payload_hash"],
        "missing_required_outcome": "unresolved",
        "all_fields_equal_outcome": "same",
        "any_field_different_outcome": "different",
    }
    for field in contract["resolution"]["required_non_null"]:
        incomplete = {**original, field: None}
        assert _compare(contract, incomplete, incomplete) == "unresolved"

    incomplete_other_task = {**original, "source_locator": None, "task_id": 43}
    assert _compare(contract, {**original, "source_locator": None}, incomplete_other_task) == "different"


def test_step12_does_not_add_deduplication_or_revision_schema() -> None:
    connection = sqlite3.connect(":memory:")
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        connection.executescript(path.read_text(encoding="utf-8"))

    assert [row for row in connection.execute("PRAGMA index_list(evidence)") if row[2]] == []
    assert "filing_kind" not in {
        row[1] for row in connection.execute("PRAGMA table_info(evidence)")
    }


def test_step12_documents_null_semantics_and_scope_boundaries() -> None:
    decision = DECISION_PATH.read_text(encoding="utf-8")
    acceptance = ACCEPTANCE_PATH.read_text(encoding="utf-8")

    for phrase in (
        "same task",
        "same source",
        "same source locator",
        "same event",
        "same payload",
        "unresolved",
        "retrieved_at",
        "Step-13",
        "Step-14",
    ):
        assert phrase in decision
    assert "logical-evidence-identity.json" in acceptance
    assert "不建立 unique constraint" in acceptance
