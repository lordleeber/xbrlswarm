"""Select an explicitly versioned publication rule without bundling legal data."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date

from .publication_window import PublicationWindow, PublicationWindowQuery
from .report_period import ReportPeriod


@dataclass(frozen=True, slots=True)
class VersionedPublicationRule:
    valid_from: date
    valid_to: date | None
    rule_id: str
    report_period: ReportPeriod
    company_class: str
    fiscal_calendar: str
    source_ref: str
    window_for: Callable[[PublicationWindowQuery], tuple[date, date]]

    def __post_init__(self) -> None:
        if type(self.valid_from) is not date or (
            self.valid_to is not None and type(self.valid_to) is not date
        ):
            raise ValueError("valid_from / valid_to 必須是日期")
        if self.valid_to is not None and self.valid_from > self.valid_to:
            raise ValueError("valid_from 不得晚於 valid_to")
        if not isinstance(self.rule_id, str) or not self.rule_id.strip():
            raise ValueError("rule_id 不得為空白")
        if not isinstance(self.source_ref, str) or not self.source_ref.strip():
            raise ValueError("source_ref 不得為空白")
        if not isinstance(self.report_period, ReportPeriod):
            raise ValueError("report_period 必須是正式期別")
        if not isinstance(self.company_class, str) or not self.company_class.strip():
            raise ValueError("company_class 不得為空白")
        if not isinstance(self.fiscal_calendar, str) or not self.fiscal_calendar.strip():
            raise ValueError("fiscal_calendar 不得為空白")
        if not callable(self.window_for):
            raise ValueError("window_for 必須是規則計算函式")


class VersionedPublicationRuleProvider:
    """Resolve only the rule whose scope and explicit validity cover a query."""

    def __init__(
        self,
        rules: Iterable[VersionedPublicationRule],
        *,
        effective_date_for_query: Callable[[PublicationWindowQuery], date],
    ) -> None:
        if not callable(effective_date_for_query):
            raise ValueError("effective_date_for_query 必須明確提供")
        self.rules = tuple(rules)
        self.effective_date_for_query = effective_date_for_query

        seen_ids: set[str] = set()
        for rule in self.rules:
            if not isinstance(rule, VersionedPublicationRule):
                raise TypeError("rules 必須是 VersionedPublicationRule")
            if rule.rule_id in seen_ids:
                raise ValueError(f"duplicate rule_id: {rule.rule_id}")
            seen_ids.add(rule.rule_id)

        for index, left in enumerate(self.rules):
            for right in self.rules[index + 1 :]:
                same_scope = (
                    left.report_period == right.report_period
                    and left.company_class == right.company_class
                    and left.fiscal_calendar == right.fiscal_calendar
                )
                if same_scope and (
                    left.valid_from <= (right.valid_to or date.max)
                    and right.valid_from <= (left.valid_to or date.max)
                ):
                    raise ValueError(
                        f"overlap in publication rules: {left.rule_id}, {right.rule_id}"
                    )

    def resolve(self, query: PublicationWindowQuery) -> PublicationWindow | None:
        effective_date = self.effective_date_for_query(query)
        if type(effective_date) is not date:
            raise ValueError("effective_date_for_query 必須回傳日期")

        for rule in self.rules:
            if (
                rule.report_period == query.report_period
                and rule.company_class == query.company_class
                and rule.fiscal_calendar == query.fiscal_calendar
                and rule.valid_from <= effective_date
                and (rule.valid_to is None or effective_date <= rule.valid_to)
            ):
                earliest_date, latest_date = rule.window_for(query)
                return PublicationWindow(earliest_date, latest_date, rule.rule_id)
        return None
