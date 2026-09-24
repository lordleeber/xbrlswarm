import json
import sqlite3
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path("contracts/logical-evidence-identity.json")
DECISION_PATH = Path("docs/logical-evidence-identity.md")
ACCEPTANCE_PATH = Path("docs/step-12-acceptance.md")
MIGRATIONS_DIR = Path("migrations")
STEP12_LAST_MIGRATION_PATH = Path("migrations/0004_add_evidence_metadata.sql")


def _load_contract() -> dict[str, Any]:
    value = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _compare(
    contract: dict[str, Any],
    left: dict[str, Any],
    right: dict[str, Any],
) -> str:
    def profile_value(evidence: dict[str, Any], field: str) -> Any:
        value = evidence.get(field)
        if (
            evidence.get("source_type") == "goodinfo"
            and field == "event_precision"
            and value is None
            and evidence.get("event_date") is not None
            and evidence.get("event_time") is not None
        ):
            return contract["legacy_goodinfo_null_precision_equivalent_to"]
        return value

    if any(
        left.get(field) is not None
        and right.get(field) is not None
        and left.get(field) != right.get(field)
        for field in contract["universal_fields"]
    ):
        return contract["resolution"]["any_field_different_outcome"]
    source_type = left.get("source_type")
    profile_name = contract["profile_by_source_type"].get(source_type)
    if profile_name is None:
        return contract["resolution"]["unmapped_source_outcome"]
    profile = contract["profiles"][profile_name]
    if any(
        profile_value(left, field) is not None
        and profile_value(right, field) is not None
        and profile_value(left, field) != profile_value(right, field)
        for field in profile["comparison_fields"]
    ):
        return contract["resolution"]["any_field_different_outcome"]
    if any(
        (profile_value(left, field) is None) != (profile_value(right, field) is None)
        for field in profile["comparison_fields"]
    ):
        return contract["resolution"]["asymmetric_missing_outcome"]
    required = profile["required_non_null"]
    if any(
        profile_value(left, field) is None or profile_value(right, field) is None
        for field in required
    ):
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
        "source_subject": None,
        "verification_state": "unverified",
        "company_name": "台灣積體電路製造股份有限公司",
    }


def test_contract_defines_the_five_roadmap_identity_dimensions() -> None:
    contract = _load_contract()

    assert contract["contract"] == "logical_evidence_identity"
    assert contract["version"] == 4
    assert contract["identity_kind"] == "logical_evidence"
    assert contract["comparison"] == "exact_stored_value_with_legacy_goodinfo_precision"
    assert contract["legacy_goodinfo_null_precision_equivalent_to"] == "second"
    assert contract["groups"] == {
        "task": ["task_id"],
        "source": ["source_type"],
        "source_locator": ["source_locator"],
        "event": [
            "evidence_type",
            "event_date",
            "event_time",
            "event_precision",
            "source_subject",
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
        "source_subject",
        "raw_payload_hash",
    ]
    assert contract["universal_fields"] == [
        "task_id",
        "source_type",
        "evidence_type",
    ]


def test_identity_contract_classifies_every_production_evidence_column() -> None:
    connection = sqlite3.connect(":memory:")
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        connection.executescript(path.read_text(encoding="utf-8"))
    columns = {row[1] for row in connection.execute("PRAGMA table_info(evidence)")}

    contract = _load_contract()
    identity = set(contract["fields"])
    non_identity = set(contract["non_identity_fields"])
    assert identity.isdisjoint(non_identity)
    assert identity | non_identity == columns


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
        "retrieved_at",
        "verification_state",
        "company_name",
        "raw_snapshot_path",
    }
    assert _compare(contract, left, right) == "same"


def test_mops_snapshot_path_does_not_change_logical_identity() -> None:
    contract = _load_contract()
    original = {**_base_evidence(), "raw_snapshot_path": None}
    moved = {**original, "raw_snapshot_path": "/archive/mops/abc.bin"}
    elsewhere = {**original, "raw_snapshot_path": "/mirror/mops/abc.bin"}

    assert _compare(contract, original, moved) == "same"
    assert _compare(contract, moved, elsewhere) == "same"


def test_legacy_goodinfo_null_precision_matches_explicit_second_only() -> None:
    contract = _load_contract()
    goodinfo = {
        **_base_evidence(),
        "source_type": "goodinfo",
        "source_locator": "goodinfo:announcement:123",
        "evidence_type": "material_announcement",
        "event_date": "2024-05-10",
        "event_time": "14:48:53",
        "event_precision": "second",
        "source_subject": "董事會通過財報",
    }
    assert _compare(contract, {**goodinfo, "event_precision": None}, goodinfo) == "same"
    assert _compare(
        contract, {**goodinfo, "event_precision": None},
        {**goodinfo, "event_precision": "date"},
    ) == "different"

    mops = {
        **_base_evidence(),
        "event_date": "2024-05-10",
        "event_time": "14:48:53",
        "event_precision": "second",
    }
    assert _compare(contract, {**mops, "event_precision": None}, mops) == "unresolved"


def test_new_payload_event_source_or_task_is_different_evidence() -> None:
    contract = _load_contract()
    original = _base_evidence()

    identity_changes = (
        {"task_id": 43},
        {"source_type": "goodinfo"},
        {"source_locator": "goodinfo:announcement:123"},
        {"evidence_type": "material_announcement"},
        {"raw_payload_hash": "sha256:def456"},
    )

    for change in identity_changes:
        assert _compare(contract, original, {**original, **change}) == "different"

    original_with_event = {
        **original,
        "event_date": "2025-02-20",
        "event_time": "14:35:01",
        "event_precision": "second",
    }
    event_changes = (
        {"event_date": "2025-02-21"},
        {"event_time": "14:35:02"},
        {"event_precision": "minute"},
    )
    for change in event_changes:
        assert _compare(
            contract,
            original_with_event,
            {**original_with_event, **change},
        ) == "different"


def test_missing_locator_or_payload_keeps_identity_unresolved() -> None:
    contract = _load_contract()
    original = _base_evidence()

    assert contract["resolution"] == {
        "evaluation_order": [
            "different_if_known_universal_value_differs",
            "select_source_profile",
            "different_if_both_known_profile_values_differ",
            "unresolved_if_profile_value_asymmetric_missing",
            "unresolved_if_profile_required_value_missing",
            "same",
        ],
        "missing_required_outcome": "unresolved",
        "asymmetric_missing_outcome": "unresolved",
        "unmapped_source_outcome": "unresolved",
        "all_fields_equal_outcome": "same",
        "any_field_different_outcome": "different",
    }
    for field in contract["profiles"]["mops_payload_backed"]["required_non_null"]:
        incomplete = {**original, field: None}
        assert _compare(contract, incomplete, incomplete) == "unresolved"

    incomplete_other_task = {**original, "source_locator": None, "task_id": 43}
    assert _compare(contract, {**original, "source_locator": None}, incomplete_other_task) == "different"


def test_asymmetric_missing_required_value_is_unresolved_not_different() -> None:
    contract = _load_contract()
    complete = _base_evidence()

    for field in contract["profiles"]["mops_payload_backed"]["required_non_null"]:
        incomplete = {**complete, field: None}
        assert _compare(contract, incomplete, complete) == "unresolved"
        assert _compare(contract, complete, incomplete) == "unresolved"


def test_asymmetric_missing_optional_profile_value_is_unresolved() -> None:
    contract = _load_contract()
    complete = {**_base_evidence(), "event_date": "2025-02-20"}
    incomplete = {**complete, "event_date": None}

    assert _compare(contract, incomplete, complete) == "unresolved"
    assert _compare(contract, complete, incomplete) == "unresolved"


def test_goodinfo_can_resolve_identity_without_a_payload_hash() -> None:
    contract = _load_contract()
    evidence = {
        **_base_evidence(),
        "source_type": "goodinfo",
        "source_locator": "goodinfo:2330:2025-02-20T14:35:01:subject-hash",
        "evidence_type": "material_announcement",
        "event_date": "2025-02-20",
        "event_time": "14:35:01",
        "event_precision": "second",
        "source_subject": "公告本公司董事會通過財務報告",
        "raw_payload_hash": None,
    }

    assert contract["profile_by_source_type"] == {
        "mops": "mops_payload_backed",
        "goodinfo": "goodinfo_announcement",
    }
    assert contract["profiles"] == {
        "mops_payload_backed": {
            "comparison_fields": [
                "source_locator",
                "event_date",
                "event_time",
                "event_precision",
                "raw_payload_hash",
            ],
            "required_non_null": ["source_locator", "raw_payload_hash"],
            "roadmap_basis": "Step-31",
        },
        "goodinfo_announcement": {
            "comparison_fields": [
                "source_locator",
                "event_date",
                "event_time",
                "event_precision",
                "source_subject",
                "raw_payload_hash",
            ],
            "required_non_null": [
                "source_locator",
                "event_date",
                "event_time",
                "source_subject",
            ],
            "roadmap_basis": "Step-39",
        },
    }
    assert _compare(contract, evidence, evidence) == "same"
    assert _compare(
        contract,
        evidence,
        {**evidence, "source_subject": "另一則公告"},
    ) == "different"

    mops_with_subject = {**_base_evidence(), "source_subject": "descriptive only"}
    assert _compare(contract, _base_evidence(), mops_with_subject) == "same"


def test_unmapped_source_profile_stays_unresolved() -> None:
    contract = _load_contract()
    evidence = {**_base_evidence(), "source_type": "cnyes"}

    assert _compare(contract, evidence, evidence) == "unresolved"


def test_step12_does_not_add_deduplication_or_revision_schema() -> None:
    connection = sqlite3.connect(":memory:")
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if path > STEP12_LAST_MIGRATION_PATH:
            continue
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
