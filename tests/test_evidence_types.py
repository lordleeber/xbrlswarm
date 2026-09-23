import json
from pathlib import Path
from typing import Any

import pytest

from xbrlswarm.domain import EvidenceType


CONTRACT_PATH = Path("contracts/evidence-types.json")
DECISION_PATH = Path("docs/evidence-types.md")
ACCEPTANCE_PATH = Path("docs/step-7-acceptance.md")


def _load_contract() -> dict[str, Any]:
    value = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_evidence_type_has_the_five_required_canonical_values() -> None:
    assert tuple(item.value for item in EvidenceType) == (
        "xbrl_document",
        "financial_report_document",
        "material_announcement",
        "search_mirror",
        "manual_review",
    )


def test_evidence_type_parser_rejects_other_domain_dimensions() -> None:
    assert EvidenceType.parse("XBRL_DOCUMENT") is EvidenceType.XBRL_DOCUMENT

    for value in ("mops", "corroborated", "published_at", "announcement_at"):
        with pytest.raises(ValueError, match="無效的證據類型"):
            EvidenceType.parse(value)


def test_machine_readable_contract_matches_domain_enum() -> None:
    contract = _load_contract()
    records = contract["types"]

    assert contract["contract"] == "evidence_types"
    assert contract["version"] == 1
    assert [record["value"] for record in records] == [item.value for item in EvidenceType]
    assert len({record["value"] for record in records}) == len(records)
    assert {record["value"]: record["role"] for record in records} == {
        "xbrl_document": "document",
        "financial_report_document": "document",
        "material_announcement": "announcement",
        "search_mirror": "discovery",
        "manual_review": "adjudication",
    }
    assert all(record["meaning"].strip() for record in records)


def test_contract_keeps_type_source_verification_and_time_separate() -> None:
    separation = _load_contract()["separation"]

    assert separation == {
        "source_type": "separate_dimension",
        "verification_state": "separate_dimension",
        "event_time": "optional_source_claim",
        "retrieved_at": "capture_metadata",
        "generic_published_at": False,
    }


def test_traceable_material_announcement_mirror_is_not_search_mirror() -> None:
    contract = _load_contract()
    rules = {rule["id"]: rule for rule in contract["classification_rules"]}

    assert rules["traceable_material_announcement_mirror"] == {
        "id": "traceable_material_announcement_mirror",
        "conditions": {
            "source_is_mirror": True,
            "upstream_event_type": "material_announcement",
            "upstream_event_identified": True,
        },
        "evidence_type": "material_announcement",
        "excluded_evidence_types": ["search_mirror"],
    }
    assert rules["unresolved_discovery_evidence"] == {
        "id": "unresolved_discovery_evidence",
        "conditions": {"upstream_artifact_or_event_identified": False},
        "evidence_type": "search_mirror",
    }


def test_step7_documents_semantic_boundaries() -> None:
    decision = DECISION_PATH.read_text(encoding="utf-8")
    acceptance = ACCEPTANCE_PATH.read_text(encoding="utf-8")

    for term in (
        "evidence_type",
        "source_type",
        "verification_state",
        "event time",
        "retrieved_at",
    ):
        assert term in decision
    assert "published_at" in decision
    assert "不建立 production Schema" in acceptance
