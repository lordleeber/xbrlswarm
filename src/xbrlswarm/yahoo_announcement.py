"""Prefer MOPS-form Yahoo announcement mirrors and verify them against a task.

Yahoo stock news republishes MOPS material announcements with the MOPS header
(日期／公司名稱 (代號)／主旨／發言人／說明) followed by the numbered explanation.
Only those mirrors carry the four fields Step-46 requires: 公司代號, 公司名稱,
主旨 and the 財務報告報導期間. News articles about the same report lack the
header and are never accepted. Nothing here writes evidence, and the article's
publication time is deliberately not exposed (Step-47).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit

from .domain import ReportPeriod, RetryableFailure, SemanticExhaustion, calendar_year_period_end
from .yahoo_search import MIRROR_HOST, ReportScope, YahooTarget

REQUIRED_FIELDS = ("公司代號", "公司名稱", "主旨", "財務報告期間")
IDENTITY_CHECKS = (
    "stock_id", "company", "fiscal_year", "report_period", "report_scope",
    "financial_report_subject",
)
_SCOPE_WORDS = {ReportScope.CONSOLIDATED: ("合併",), ReportScope.INDIVIDUAL: ("個體", "個別")}
_QUARTER_START_MONTH = {ReportPeriod.Q1: 1, ReportPeriod.Q2: 4, ReportPeriod.Q3: 7, ReportPeriod.FY: 1}
_DATE_LINE = re.compile(r"^日\s*期\s*:\s*(\d{4})年(\d{1,2})月(\d{1,2})日$")
_COMPANY_LINE = re.compile(r"^公司名稱\s*:\s*(.+?)\s*(?:\(\s*([0-9A-Za-z]+)\s*\))?$")
_SUBJECT_LINE = re.compile(r"^主\s*旨\s*:\s*(.+)$")
_EXPLANATION_LINE = re.compile(r"^說\s*明\s*:?")
_ROC_DATE = r"(\d{2,3})/(\d{1,2})/(\d{1,2})"
_PERIOD = re.compile(
    r"報導期間\s*起訖日期(?:\([^)]*\))?\s*:\s*" + _ROC_DATE + r"\s*~\s*" + _ROC_DATE
)


class YahooArticleLayoutError(ValueError):
    """The page has no single article body, or its MOPS fields contradict each other."""


class NotMopsForm(ValueError):
    """The article body lacks at least one required MOPS-form field."""

    def __init__(self, missing: tuple[str, ...]) -> None:
        super().__init__(f"Yahoo article is not a MOPS-form mirror; missing {', '.join(missing)}")
        self.missing = missing


@dataclass(frozen=True, slots=True)
class YahooAnnouncement:
    url: str
    headline: str
    announcement_date: date | None
    company: str
    stock_id: str
    subject: str
    period_start: date
    period_end: date


class _ArticleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.headline = ""
        self.bodies = 0
        self.lines: list[str] = []
        self._h1_seen = False
        self._in_h1 = False
        self._div_depth = 0
        self._body_depth: int | None = None
        self._paragraph: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "h1" and not self._h1_seen:
            self._h1_seen = self._in_h1 = True
        elif tag == "div":
            self._div_depth += 1
            classes = (attributes.get("class") or "").split()
            if "atoms" in classes and attributes.get("data-component") == "blocks":
                self.bodies += 1
                if self._body_depth is None and self.bodies == 1:
                    self._body_depth = self._div_depth
        elif tag == "p" and self._body_depth is not None:
            self._paragraph = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1":
            self._in_h1 = False
        elif tag == "div":
            if self._body_depth == self._div_depth:
                self._body_depth = None
            self._div_depth -= 1
        elif tag == "p" and self._paragraph is not None:
            self.lines.append("".join(self._paragraph))
            self._paragraph = None

    def handle_data(self, data: str) -> None:
        if self._in_h1:
            self.headline += data
        if self._paragraph is not None:
            self._paragraph.append(data)


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).split())


def _only(values: list, field: str):
    if len(set(values)) > 1:
        raise YahooArticleLayoutError(f"conflicting {field} fields in Yahoo article")
    return values[0] if values else None


def _roc_date(year: str, month: str, day: str, field: str) -> date:
    try:
        return date(int(year) + 1911, int(month), int(day))
    except ValueError as exc:
        raise YahooArticleLayoutError(f"invalid {field} date in Yahoo article") from exc


def parse_yahoo_announcement(body: bytes, *, url: str) -> YahooAnnouncement:
    """Read the MOPS-form fields from the article body of a Yahoo news page.

    Only paragraphs inside the article's ``div.atoms`` count: the meta
    description and related-news cards repeat the same labels for other pages.
    Header fields count only before the 說明 line, so explanation items such as
    ``2.公司名稱:公信電子股份有限公司`` are not mistaken for the header.
    """

    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise YahooArticleLayoutError("Yahoo article is not UTF-8") from exc
    parser = _ArticleParser()
    parser.feed(text)
    parser.close()
    if parser.bodies != 1:
        raise YahooArticleLayoutError(
            f"expected one Yahoo article body, found {parser.bodies}"
        )
    lines = [_normalize(line) for line in parser.lines]
    lines = [line for line in lines if line]
    split = next(
        (index for index, line in enumerate(lines) if _EXPLANATION_LINE.match(line)), None
    )
    header = [] if split is None else lines[:split]
    explanation = lines if split is None else lines[split + 1:]

    dates, companies, codes, subjects = [], [], [], []
    for line in header:
        if match := _DATE_LINE.match(line):
            try:
                dates.append(date(*(int(part) for part in match.groups())))
            except ValueError as exc:
                raise YahooArticleLayoutError("invalid 日期 in Yahoo article") from exc
        elif match := _COMPANY_LINE.match(line):
            companies.append(match.group(1))
            if match.group(2):
                codes.append(match.group(2))
        elif match := _SUBJECT_LINE.match(line):
            subjects.append(match.group(1))
    announcement_date = _only(dates, "日期")
    company = _only(companies, "公司名稱")
    stock_id = _only(codes, "公司名稱")
    subject = _only(subjects, "主旨")

    periods = []
    for match in _PERIOD.finditer(" ".join(explanation)):
        groups = match.groups()
        start = _roc_date(*groups[:3], "報導期間")
        end = _roc_date(*groups[3:], "報導期間")
        if start > end:
            raise YahooArticleLayoutError("報導期間 starts after it ends in Yahoo article")
        periods.append((start, end))
    period = _only(periods, "報導期間")

    present = {
        "公司代號": stock_id, "公司名稱": company, "主旨": subject, "財務報告期間": period,
    }
    missing = tuple(field for field in REQUIRED_FIELDS if present[field] is None)
    if missing:
        raise NotMopsForm(missing)
    return YahooAnnouncement(
        url=url,
        headline=_normalize(parser.headline),
        announcement_date=announcement_date,
        company=company,
        stock_id=stock_id,
        subject=subject,
        period_start=period[0],
        period_end=period[1],
    )


def verify_yahoo_announcement(
    announcement: YahooAnnouncement, target: YahooTarget
) -> tuple[str, ...]:
    """Return the identity checks the mirror fails for ``target``, in a fixed order.

    Periods follow a calendar-year fiscal calendar: the period must end on the
    target's period end and start on January 1 (cumulative) or the quarter start.
    When the target fixes a scope, the subject must name it.
    """

    failed = set()
    if announcement.stock_id != target.stock_id:
        failed.add("stock_id")
    if _normalize(announcement.company) != _normalize(target.company):
        failed.add("company")
    if announcement.period_end.year != target.fiscal_year:
        failed.add("fiscal_year")
    else:
        starts = {
            date(target.fiscal_year, 1, 1),
            date(target.fiscal_year, _QUARTER_START_MONTH[target.report_period], 1),
        }
        expected_end = calendar_year_period_end(target.fiscal_year, target.report_period)
        if announcement.period_end != expected_end or announcement.period_start not in starts:
            failed.add("report_period")
    subject = _normalize(announcement.subject)
    if target.report_scope is not None and not any(
        word in subject for word in _SCOPE_WORDS[target.report_scope]
    ):
        failed.add("report_scope")
    if "財務報告" not in subject:
        failed.add("financial_report_subject")
    return tuple(check for check in IDENTITY_CHECKS if check in failed)


class YahooArticleOutcome(StrEnum):
    ACCEPTED = "accepted"
    NOT_MOPS_FORM = "not_mops_form"
    IDENTITY_MISMATCH = "identity_mismatch"
    ARTICLE_UNAVAILABLE = "article_unavailable"
    NOT_ARTICLE_PAGE = "not_article_page"


@dataclass(frozen=True, slots=True)
class YahooArticleReview:
    url: str
    outcome: YahooArticleOutcome | RetryableFailure
    announcement: YahooAnnouncement | None = None
    mismatches: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()


def _is_news_article(url: str) -> bool:
    split = urlsplit(url)
    return (
        split.scheme in {"http", "https"}
        and split.hostname == MIRROR_HOST
        and split.path.startswith("/news/")
    )


def review_yahoo_article(
    target: YahooTarget, *, url: str, final_url: str, status: int, body: bytes
) -> YahooArticleReview:
    """Classify one fetched candidate article for ``target``.

    A removed article (404/410) is a final answer for that candidate. Rate limits,
    other statuses and pages without a recognizable article body are retryable.
    """

    if status in {404, 410}:
        return YahooArticleReview(url, YahooArticleOutcome.ARTICLE_UNAVAILABLE)
    if status == 429:
        return YahooArticleReview(url, RetryableFailure.RATE_LIMITED)
    if status != 200:
        return YahooArticleReview(url, RetryableFailure.TEMPORARY_ERROR)
    if not _is_news_article(final_url):
        return YahooArticleReview(url, YahooArticleOutcome.NOT_ARTICLE_PAGE)
    try:
        announcement = parse_yahoo_announcement(body, url=final_url)
    except NotMopsForm as exc:
        return YahooArticleReview(url, YahooArticleOutcome.NOT_MOPS_FORM, missing=exc.missing)
    except YahooArticleLayoutError:
        return YahooArticleReview(url, RetryableFailure.TEMPORARY_ERROR)
    mismatches = verify_yahoo_announcement(announcement, target)
    if mismatches:
        return YahooArticleReview(
            url, YahooArticleOutcome.IDENTITY_MISMATCH, announcement, mismatches
        )
    return YahooArticleReview(url, YahooArticleOutcome.ACCEPTED, announcement)


def review_yahoo_article_capture(target: YahooTarget, metadata_file: Path) -> YahooArticleReview:
    """Review an article saved in the Step-44 fixture format (``.meta.json`` + body)."""

    metadata_file = Path(metadata_file)
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    request_url = metadata["request"]["url"]
    if not _is_news_article(request_url):
        raise ValueError(f"capture request url is not a Yahoo news article: {request_url!r}")
    response = metadata["response"]
    body = gzip.decompress((metadata_file.parent / response["body_file"]).read_bytes())
    if hashlib.sha256(body).hexdigest() != response["sha256"]:
        raise ValueError(f"capture body sha256 mismatch for {metadata_file}")
    return review_yahoo_article(
        target, url=request_url, final_url=response["final_url"],
        status=response["status"], body=body,
    )


@dataclass(frozen=True, slots=True)
class YahooSelection:
    """Accepted mirrors when ``outcome`` is ``None``; otherwise why there are none."""

    accepted: tuple[YahooAnnouncement, ...]
    reviews: tuple[YahooArticleReview, ...]
    outcome: RetryableFailure | SemanticExhaustion | None


def select_yahoo_announcements(reviews: Iterable[YahooArticleReview]) -> YahooSelection:
    """Keep every accepted MOPS-form mirror, in candidate order.

    Non-MOPS-form articles are never accepted, whatever their rank. Without an
    accepted mirror, an unfinished (retryable) review keeps the task retryable;
    only when every candidate was finally judged is the result ``rejected``.
    Call this only with candidates from a SERP; no candidates is ``not_found``.
    """

    reviews = tuple(reviews)
    if not reviews:
        raise ValueError("select_yahoo_announcements needs at least one reviewed candidate")
    accepted = tuple(
        review.announcement for review in reviews
        if review.outcome is YahooArticleOutcome.ACCEPTED
    )
    if accepted:
        return YahooSelection(accepted, reviews, None)
    retryable = {review.outcome for review in reviews if isinstance(review.outcome, RetryableFailure)}
    if RetryableFailure.RATE_LIMITED in retryable:
        return YahooSelection((), reviews, RetryableFailure.RATE_LIMITED)
    if retryable:
        return YahooSelection((), reviews, RetryableFailure.TEMPORARY_ERROR)
    return YahooSelection((), reviews, SemanticExhaustion.REJECTED)
