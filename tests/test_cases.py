import pytest

from xbrlswarm.discovery.cases import DISCOVERY_CASES, find_case
from xbrlswarm.discovery.models import DiscoveryCase, ReportPeriod


def test_discovery_cases_cover_required_companies_and_periods() -> None:
    assert len(DISCOVERY_CASES) == 12
    assert {case.stock_id for case in DISCOVERY_CASES} == {"2330", "6147", "4542"}
    for stock_id in {"2330", "6147", "4542"}:
        periods = {case.report_period for case in DISCOVERY_CASES if case.stock_id == stock_id}
        assert periods == set(ReportPeriod)
        assert {case.fiscal_year for case in DISCOVERY_CASES if case.stock_id == stock_id} == {2024}


def test_report_period_rejects_q4_and_unknown() -> None:
    with pytest.raises(ValueError):
        ReportPeriod.parse("Q4")
    with pytest.raises(ValueError):
        ReportPeriod.parse("unknown")


def test_find_case_returns_fixed_case() -> None:
    case = find_case("4542", 2024, ReportPeriod.Q1)
    assert case == DiscoveryCase("4542", "科嶠", 2024, ReportPeriod.Q1)
