import json
from collections import defaultdict
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path("contracts/report-identity-candidate.json")
MATRIX_PATH = Path("discovery/source_field_matrix.json")
OBSERVATIONS_PATH = Path("discovery/mops_field_observations.json")
DECISION_PATH = Path("docs/report-identity-candidate.md")
ACCEPTANCE_PATH = Path("docs/step-5-acceptance.md")


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_candidate_uses_only_evidence_backed_identity_fields() -> None:
    contract = _load_json(CONTRACT_PATH)
    matrix = _load_json(MATRIX_PATH)
    statuses = {record["field"]: record["status"] for record in matrix["fields"]}

    assert contract["contract"] == "report_identity_candidate"
    assert contract["version"] == 1
    assert contract["status"] == "provisional"
    assert contract["identity_kind"] == "task"
    assert contract["fields"] == ["stock_id", "fiscal_year", "report_period"]
    assert {statuses[field] for field in contract["fields"]} <= {"direct", "derived"}


def test_report_scope_expansion_requires_coexistence_and_tracking() -> None:
    contract = _load_json(CONTRACT_PATH)
    scope = contract["report_scope_decision"]

    assert scope["included"] is False
    assert scope["reason"] == "scope_coexistence_not_verified"
    assert scope["observed_scopes"] == ["consolidated"]
    assert scope["expansion_requires"] == {
        "same_report_has_consolidated_and_individual": True,
        "both_scopes_are_tracked": True,
    }
    assert scope["expanded_fields"] == [
        "stock_id",
        "fiscal_year",
        "report_period",
        "report_scope",
    ]


def test_candidate_evidence_is_auditable_and_does_not_claim_nonexistence() -> None:
    contract = _load_json(CONTRACT_PATH)

    assert contract["limitations"] == [
        "individual_scope_not_captured",
        "same_report_scope_coexistence_not_verified",
    ]
    evidence_paths = {Path(item["path"]) for item in contract["evidence"]}
    assert evidence_paths == {
        Path("discovery/mops_field_observations.json"),
        Path("docs/source-field-matrix.md"),
        Path("docs/step-3-acceptance.md"),
    }
    assert all(path.is_file() for path in evidence_paths)


def test_scope_decision_matches_observed_evidence() -> None:
    contract = _load_json(CONTRACT_PATH)
    observations = _load_json(OBSERVATIONS_PATH)
    scopes_by_identity: dict[tuple[str, str, str], set[str]] = defaultdict(set)

    for case in observations["cases"]:
        identity = (
            case["facts"]["tifrs-notes:CompanyID"],
            case["facts"]["tifrs-notes:Year"],
            case["derived"]["report_period"],
        )
        scopes_by_identity[identity].add(case["normalized"]["report_scope"])

    observed_scopes = set().union(*scopes_by_identity.values())
    scope_decision = contract["report_scope_decision"]

    assert observed_scopes == set(scope_decision["observed_scopes"])
    assert "individual_scope_not_captured" in contract["limitations"]
    assert "individual" not in observed_scopes
    assert "same_report_scope_coexistence_not_verified" in contract["limitations"]
    assert all(len(scopes) == 1 for scopes in scopes_by_identity.values())


def test_decision_document_preserves_identity_boundaries() -> None:
    decision = DECISION_PATH.read_text(encoding="utf-8")
    acceptance = ACCEPTANCE_PATH.read_text(encoding="utf-8")

    assert "(stock_id, fiscal_year, report_period)" in decision
    assert "(stock_id, fiscal_year, report_period, report_scope)" in decision
    assert "task identity" in decision
    assert "filing identifier" in decision
    assert "source locator" in decision
    assert "evidence identity" in decision
    assert "不建立 production Schema" in acceptance
