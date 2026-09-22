from __future__ import annotations

import gzip
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import DiscoveryCase, ReportPeriod
from .mops import verify_mops_capture_set

_REQUIRED_FACTS = (
    "tifrs-notes:CompanyID",
    "tifrs-notes:CompanyChineseName",
    "tifrs-notes:Year",
    "tifrs-notes:Quarter",
    "tifrs-notes:ReportType",
    "tifrs-notes:ReportCategory",
)
_PERIOD_BY_QUARTER = {
    1: ReportPeriod.Q1,
    2: ReportPeriod.Q2,
    3: ReportPeriod.Q3,
    4: ReportPeriod.FY,
}
_SCOPE_BY_CATEGORY = {
    "Consolidated report": "consolidated",
}
_NOT_OBSERVED = (
    "filing_identifier",
    "filing_date",
    "filing_time",
    "xbrl_confirmed_at",
    "filing_kind",
)
_SEMANTIC_REVIEW_TERMS = (
    "filing",
    "filed",
    "submission",
    "confirmation",
    "confirmed",
    "amend",
    "correct",
    "supplement",
    "authorisation",
    "authorization",
    "reporttype",
)


@dataclass(frozen=True, slots=True)
class MopsFieldObservation:
    case: DiscoveryCase
    stock_id: str
    company_name: str
    fiscal_year: int
    source_quarter: int
    report_period: ReportPeriod
    report_scope: str
    report_type: str
    source_url: str
    sha256: str
    fact_names: tuple[str, ...]


def _fact_values(body: bytes) -> dict[str, set[str]]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise ValueError("MOPS raw payload 不是可解析的 XML/XHTML") from exc

    facts: dict[str, set[str]] = {}
    for node in root.iter():
        local_name = node.tag.rsplit("}", 1)[-1].lower()
        if local_name not in {"nonnumeric", "nonfraction"}:
            continue
        fact_name = node.attrib.get("name")
        if not fact_name:
            continue
        value = "".join(node.itertext()).strip()
        if value:
            facts.setdefault(fact_name, set()).add(value)
    return facts


def _required_fact(facts: dict[str, set[str]], name: str, case: DiscoveryCase) -> str:
    values = facts.get(name, set())
    if len(values) != 1:
        raise ValueError(
            f"{case.key} 的 {name} 必須恰有一個非空且不互相衝突的值"
        )
    return next(iter(values))


def extract_mops_field_observation(
    case: DiscoveryCase,
    body: bytes,
    *,
    source_url: str,
    sha256: str,
) -> MopsFieldObservation:
    facts = _fact_values(body)
    stock_id = _required_fact(facts, "tifrs-notes:CompanyID", case)
    company_name = _required_fact(facts, "tifrs-notes:CompanyChineseName", case)
    year_text = _required_fact(facts, "tifrs-notes:Year", case)
    quarter_text = _required_fact(facts, "tifrs-notes:Quarter", case)
    report_type = _required_fact(facts, "tifrs-notes:ReportType", case)
    category = _required_fact(facts, "tifrs-notes:ReportCategory", case)

    if stock_id != case.stock_id:
        raise ValueError(f"{case.key} 的 tifrs-notes:CompanyID 與 capture case 不一致")
    try:
        fiscal_year = int(year_text)
    except ValueError as exc:
        raise ValueError(f"{case.key} 的 tifrs-notes:Year 不是整數") from exc
    if fiscal_year != case.fiscal_year:
        raise ValueError(f"{case.key} 的 tifrs-notes:Year 與 capture case 不一致")
    try:
        source_quarter = int(quarter_text)
        report_period = _PERIOD_BY_QUARTER[source_quarter]
    except (ValueError, KeyError) as exc:
        raise ValueError(f"{case.key} 的 tifrs-notes:Quarter 無法映射為報告期別") from exc
    if report_period is not case.report_period:
        raise ValueError(f"{case.key} 的 tifrs-notes:Quarter 與 capture case 不一致")
    try:
        report_scope = _SCOPE_BY_CATEGORY[category]
    except KeyError as exc:
        raise ValueError(f"{case.key} 的 tifrs-notes:ReportCategory 尚無已驗證映射") from exc

    return MopsFieldObservation(
        case=case,
        stock_id=stock_id,
        company_name=company_name,
        fiscal_year=fiscal_year,
        source_quarter=source_quarter,
        report_period=report_period,
        report_scope=report_scope,
        report_type=report_type,
        source_url=source_url,
        sha256=sha256,
        fact_names=tuple(sorted(facts)),
    )


def analyze_mops_capture_set(output_root: Path) -> tuple[MopsFieldObservation, ...]:
    observations: list[MopsFieldObservation] = []
    for capture in verify_mops_capture_set(output_root):
        metadata: Any = json.loads(capture.metadata_path.read_text(encoding="utf-8"))
        source_url = metadata["request"]["url"]
        body = gzip.decompress(capture.body_path.read_bytes())
        observations.append(
            extract_mops_field_observation(
                capture.case,
                body,
                source_url=source_url,
                sha256=capture.sha256,
            )
        )
    return tuple(observations)


def render_mops_field_observations(
    observations: tuple[MopsFieldObservation, ...],
) -> str:
    fact_names = sorted({name for item in observations for name in item.fact_names})
    semantic_candidates = [
        name
        for name in fact_names
        if any(term in name.lower() for term in _SEMANTIC_REVIEW_TERMS)
    ]
    document = {
        "schema_version": 1,
        "source": "mops-xbrl-download",
        "scope": "Step-3 field availability evidence from the 12 fixed Step-2 captures",
        "capture_count": len(observations),
        "coverage": {name: f"{len(observations)}/{len(observations)}" for name in _REQUIRED_FACTS},
        "period_rule": {str(key): value.value for key, value in _PERIOD_BY_QUARTER.items()},
        "scope_rule": dict(_SCOPE_BY_CATEGORY),
        "not_observed": list(_NOT_OBSERVED),
        "semantic_review": {
            "distinct_fact_name_count": len(fact_names),
            "candidate_fact_names": semantic_candidates,
            "method": "Review all distinct fact names for filing/submission/confirmation/amendment/correction/supplement and adjacent authorisation/report-type semantics.",
        },
        "cautions": [
            "DateAndProceduresOfAuthorisationForIssueOfFinancialStatements is a board-authorisation disclosure, not a filing timestamp.",
            "retrieved_at and HTTP headers are capture metadata, not filing or confirmation timestamps.",
            "ReportType=Financial report (general) does not identify original, amendment, correction, or supplemental filing kind.",
            "Only consolidated captures were sampled; coexistence with individual reports remains outside this evidence set.",
        ],
        "cases": [
            {
                "case": item.case.key,
                "sha256": item.sha256,
                "source_url": item.source_url,
                "facts": {
                    "tifrs-notes:CompanyID": item.stock_id,
                    "tifrs-notes:CompanyChineseName": item.company_name,
                    "tifrs-notes:Year": str(item.fiscal_year),
                    "tifrs-notes:Quarter": str(item.source_quarter),
                    "tifrs-notes:ReportType": item.report_type,
                    "tifrs-notes:ReportCategory": next(
                        category
                        for category, scope in _SCOPE_BY_CATEGORY.items()
                        if scope == item.report_scope
                    ),
                },
                "derived": {"report_period": item.report_period.value},
                "normalized": {
                    "report_scope": item.report_scope,
                },
            }
            for item in observations
        ],
    }
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
