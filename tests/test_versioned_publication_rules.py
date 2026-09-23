import json
from datetime import date
from pathlib import Path

import pytest

from xbrlswarm.domain import (
    PublicationRuleUnavailable,
    ReportPeriod,
    calendar_year_period_end,
    expected_publication_window,
)


CONTRACT = Path("contracts/versioned-publication-rules.json")
DECISION = Path("docs/versioned-publication-rules.md")
ACCEPTANCE = Path("docs/step-20-acceptance.md")


def _rule(
    *,
    valid_from: date,
    valid_to: date | None,
    rule_id: str,
    report_period: ReportPeriod = ReportPeriod.Q1,
    company_class: str = "test_class",
    fiscal_calendar: str = "calendar_year",
    source_ref: str = "TEST-ONLY-NOT-LAW",
    last_day: int = 2,
):
    from xbrlswarm.domain import VersionedPublicationRule

    return VersionedPublicationRule(
        valid_from=valid_from,
        valid_to=valid_to,
        rule_id=rule_id,
        report_period=report_period,
        company_class=company_class,
        fiscal_calendar=fiscal_calendar,
        source_ref=source_ref,
        window_for=lambda query: (
            date(query.fiscal_year, 4, 1),
            date(query.fiscal_year, 4, last_day),
        ),
    )


def _provider(*rules):
    from xbrlswarm.domain import VersionedPublicationRuleProvider

    return VersionedPublicationRuleProvider(
        rules,
        effective_date_for_query=lambda query: calendar_year_period_end(
            query.fiscal_year, query.report_period
        ),
    )


def _lookup(year: int, provider, period: ReportPeriod = ReportPeriod.Q1):
    return expected_publication_window(
        fiscal_year=year,
        report_period=period,
        company_class="test_class",
        fiscal_calendar="calendar_year",
        rule_provider=provider,
    )


def test_historical_query_selects_effective_version_not_current_rule() -> None:
    old = _rule(
        valid_from=date(2020, 1, 1), valid_to=date(2023, 12, 31),
        rule_id="TEST-OLD", last_day=2,
    )
    current = _rule(
        valid_from=date(2024, 1, 1), valid_to=None,
        rule_id="TEST-NEW", last_day=3,
    )
    provider = _provider(current, old)

    assert _lookup(2023, provider).rule_id == "TEST-OLD"
    assert _lookup(2023, provider).latest_date == date(2023, 4, 2)
    assert _lookup(2024, provider).rule_id == "TEST-NEW"
    assert _lookup(2024, provider).latest_date == date(2024, 4, 3)
    with pytest.raises(PublicationRuleUnavailable):
        _lookup(2019, provider)


def test_validity_boundaries_are_inclusive_and_gap_is_unresolved() -> None:
    first = _rule(
        valid_from=date(2020, 1, 1), valid_to=date(2022, 3, 31),
        rule_id="TEST-FIRST",
    )
    second = _rule(
        valid_from=date(2024, 1, 1), valid_to=None, rule_id="TEST-SECOND",
    )
    provider = _provider(first, second)

    assert _lookup(2022, provider).rule_id == "TEST-FIRST"
    with pytest.raises(PublicationRuleUnavailable):
        _lookup(2023, provider)
    assert _lookup(2024, provider).rule_id == "TEST-SECOND"


def test_rule_scope_must_match_class_calendar_and_period() -> None:
    provider = _provider(
        _rule(
            valid_from=date(2020, 1, 1), valid_to=None,
            rule_id="TEST-Q2", report_period=ReportPeriod.Q2,
        )
    )
    with pytest.raises(PublicationRuleUnavailable):
        _lookup(2024, provider, ReportPeriod.Q1)


def test_overlapping_versions_or_reused_rule_ids_are_rejected() -> None:
    old = _rule(
        valid_from=date(2020, 1, 1), valid_to=date(2024, 12, 31),
        rule_id="TEST-OLD",
    )
    overlap = _rule(
        valid_from=date(2024, 1, 1), valid_to=None, rule_id="TEST-NEW",
    )
    with pytest.raises(ValueError, match="overlap"):
        _provider(old, overlap)

    reused_id = _rule(
        valid_from=date(2025, 1, 1), valid_to=None, rule_id="TEST-OLD",
    )
    with pytest.raises(ValueError, match="rule_id"):
        _provider(old, reused_id)

    reused_across_scope = _rule(
        valid_from=date(2025, 1, 1), valid_to=None,
        rule_id="TEST-OLD", report_period=ReportPeriod.Q2,
    )
    with pytest.raises(ValueError, match="rule_id"):
        _provider(old, reused_across_scope)


@pytest.mark.parametrize(
    "change",
    [
        {"valid_to": date(2019, 12, 31)},
        {"rule_id": " "},
        {"source_ref": " "},
    ],
)
def test_version_metadata_cannot_be_missing_or_inverted(change) -> None:
    with pytest.raises(ValueError):
        _rule(**{
            "valid_from": date(2020, 1, 1),
            "valid_to": date(2023, 12, 31),
            "rule_id": "TEST-ONLY",
            **change,
        })


def test_contract_and_docs_define_temporal_selection_without_law_values() -> None:
    assert json.loads(CONTRACT.read_text(encoding="utf-8")) == {
        "contract": "versioned_publication_rules",
        "version": 1,
        "required_rule_fields": ["valid_from", "valid_to", "rule_id", "source_ref"],
        "validity_bounds": "inclusive",
        "effective_date": "explicit_provider_dependency",
        "rule_scope": ["report_period", "company_class", "fiscal_calendar"],
        "overlap": "reject_same_scope",
        "rule_id_uniqueness": "global_within_provider",
        "missing_or_gap": "unresolved",
        "built_in_legal_rules": False,
    }
    decision = DECISION.read_text(encoding="utf-8")
    acceptance = ACCEPTANCE.read_text(encoding="utf-8")
    assert "TEST-ONLY-NOT-LAW" in decision
    assert "Step-20" in acceptance
    assert "不需要 migration" in acceptance
