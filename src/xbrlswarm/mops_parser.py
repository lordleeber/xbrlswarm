"""Parse only fields supported by the verified MOPS source field matrix."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from xbrlswarm.discovery.models import DiscoveryCase
from xbrlswarm.discovery.mops import build_mops_xbrl_capture
from xbrlswarm.discovery.mops_analysis import extract_mops_field_observation
from xbrlswarm.domain import ReportPeriod


@dataclass(frozen=True, slots=True)
class ParsedMopsReport:
    stock_id: str
    company_name: str
    fiscal_year: int
    report_period: ReportPeriod
    report_scope: str
    source_locator: str


def parse_mops_report(
    case: DiscoveryCase, body: bytes, *, source_url: str
) -> ParsedMopsReport:
    """Return the direct and deterministic fields from a verified MOPS XBRL layout.

    The current source evidence covers only the consolidated FileDownLoad
    endpoint. Other responses must be reviewed before adding their mappings.
    """

    expected_url = build_mops_xbrl_capture(case).url
    if source_url != expected_url:
        raise ValueError(f"{case.key} 的 MOPS source_url 不符合已驗證的合併 XBRL endpoint")

    observation = extract_mops_field_observation(
        case,
        body,
        source_url=source_url,
        sha256=hashlib.sha256(body).hexdigest(),
    )
    if observation.report_type != "Financial report (general)":
        raise ValueError(f"{case.key} 的 ReportType 尚無已驗證解析規則")
    return ParsedMopsReport(
        stock_id=observation.stock_id,
        company_name=observation.company_name,
        fiscal_year=observation.fiscal_year,
        report_period=observation.report_period,
        report_scope=observation.report_scope,
        source_locator=expected_url,
    )
