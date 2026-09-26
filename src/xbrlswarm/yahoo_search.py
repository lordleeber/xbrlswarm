"""Yahoo announcement-mirror search: query builder, SERP parser and outcomes.

Step-44 showed that Yahoo search only answers a real browser that completes the
``/_bv/`` bot-validation redirect, so fetching is done by the headed-browser
capture tool (``tools/yahoo_serp_capture.js``). This module turns a task into the
query that tool requests and classifies the captured response. A candidate is only
a search result whose visible identity fits the task; it is not accepted evidence.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

from .domain import ReportPeriod, RetryableFailure, SemanticExhaustion

SEARCH_URL = "https://tw.search.yahoo.com/search?p="
MIRROR_HOST = "tw.stock.yahoo.com"
ANNOUNCEMENT_WORDING = "董事會通過"
_SERP_TITLE_SUFFIX = " - Yahoo 網頁搜尋"
_PERIOD_WORDING = {
    ReportPeriod.FY: "年度",
    ReportPeriod.Q1: "年第一季",
    ReportPeriod.Q2: "年第二季",
    ReportPeriod.Q3: "年第三季",
}
_QUARTER_NUMERALS = {ReportPeriod.Q1: "一1", ReportPeriod.Q2: "二2", ReportPeriod.Q3: "三3"}
_STOCK_ID = re.compile(r"[0-9A-Za-z]+")
_COMPANY = re.compile(r"[^\s\"'“”:：]+")
_COMPANY_CONTINUATIONS = ("董事會", "民國", "公告", "本公司")
_SNIPPET_CODE = re.compile(r"公司名稱:\s*[^()]*?\(\s*([0-9A-Za-z]+)\s*\)")


class ReportScope(StrEnum):
    CONSOLIDATED = "consolidated"
    INDIVIDUAL = "individual"


_SCOPE_WORDING = {ReportScope.CONSOLIDATED: "合併", ReportScope.INDIVIDUAL: "個體"}


@dataclass(frozen=True, slots=True)
class YahooTarget:
    """Task identity as far as Yahoo search can see it.

    The task table has no company name or report scope; callers supply the company
    name, and scope stays ``None`` when the task does not fix it.
    """

    stock_id: str
    company: str
    fiscal_year: int
    report_period: ReportPeriod
    report_scope: ReportScope | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.stock_id, str) or not _STOCK_ID.fullmatch(self.stock_id):
            raise ValueError(f"invalid stock_id {self.stock_id!r}")
        if not isinstance(self.company, str) or not _COMPANY.fullmatch(self.company):
            raise ValueError(f"invalid company {self.company!r}")
        if (
            not isinstance(self.fiscal_year, int)
            or isinstance(self.fiscal_year, bool)
            or self.fiscal_year < 1912
        ):
            raise ValueError(f"invalid fiscal_year {self.fiscal_year!r}; ROC years start in 1912")
        object.__setattr__(self, "report_period", ReportPeriod.parse(str(self.report_period)))
        if self.report_scope is not None:
            try:
                scope = ReportScope(self.report_scope)
            except ValueError as exc:
                raise ValueError(f"invalid report_scope {self.report_scope!r}") from exc
            object.__setattr__(self, "report_scope", scope)

    @property
    def roc_year(self) -> int:
        return self.fiscal_year - 1911


@dataclass(frozen=True, slots=True)
class YahooSearchPlan:
    target: YahooTarget
    query: str
    url: str


def yahoo_search_plan(
    stock_id: str,
    company: str,
    fiscal_year: int,
    report_period: ReportPeriod | str,
    report_scope: ReportScope | str | None = None,
) -> YahooSearchPlan:
    """Build the site-restricted query that mirrors MOPS announcement titles.

    Yahoo mirrors title announcements like ``公信董事會通過113年度合併財務報告``,
    so the query uses the ROC year and the announcement's period wording. It does
    not guarantee the mirror is returned; see ``classify_yahoo_serp_response``.
    """

    return _plan_for(YahooTarget(stock_id, company, fiscal_year, report_period, report_scope))


def _plan_for(target: YahooTarget) -> YahooSearchPlan:
    scope = "" if target.report_scope is None else _SCOPE_WORDING[target.report_scope]
    query = " ".join((
        f"site:{MIRROR_HOST}",
        target.stock_id,
        target.company,
        ANNOUNCEMENT_WORDING,
        f"{target.roc_year}{_PERIOD_WORDING[target.report_period]}",
        f"{scope}財務報告",
    ))
    # Same escaping as the capture tool's encodeURIComponent.
    return YahooSearchPlan(target, query, SEARCH_URL + quote(query, safe="-_.!~*'()"))


@dataclass(frozen=True, slots=True)
class SerpResult:
    title: str
    url: str
    snippet: str


class YahooSerpLayoutError(ValueError):
    """The page is not a Yahoo SERP whose organic results this parser understands."""


class _SerpParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.page_title = ""
        self.results: list[dict[str, str]] = []
        self._in_page_title = False
        self._current: dict[str, str] | None = None
        self._h3_depth = 0
        self._li_depth = 0
        self._result_li_depth = 0
        self._awaiting_snippet: dict[str, str] | None = None
        self._in_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "title":
            self._in_page_title = True
        elif tag == "li":
            self._li_depth += 1
        elif tag == "a" and attributes.get("data-matarget") == "algo":
            self._awaiting_snippet = None
            self._current = {"href": attributes.get("href") or "", "title": "", "snippet": ""}
            self._result_li_depth = self._li_depth
        elif tag == "h3" and self._current is not None:
            self._h3_depth += 1
        elif tag == "p" and self._awaiting_snippet is not None:
            self._in_snippet = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_page_title = False
        elif tag == "li":
            if self._li_depth == self._result_li_depth:
                self._awaiting_snippet = None
            self._li_depth -= 1
        elif tag == "h3" and self._h3_depth:
            self._h3_depth -= 1
        elif tag == "a" and self._current is not None:
            self.results.append(self._current)
            self._awaiting_snippet = self._current
            self._current = None
            self._h3_depth = 0
        elif tag == "p" and self._in_snippet:
            self._in_snippet = False
            self._awaiting_snippet = None

    def handle_data(self, data: str) -> None:
        if self._in_page_title:
            self.page_title += data
        elif self._current is not None and self._h3_depth:
            self._current["title"] += data
        elif self._in_snippet and self._awaiting_snippet is not None:
            self._awaiting_snippet["snippet"] += data


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _target_url(href: str) -> str:
    marker = "/RU="
    if marker in href:
        start = href.index(marker) + len(marker)
        end = href.find("/", start)
        href = unquote(href[start:] if end < 0 else href[start:end])
    split = urlsplit(href)
    if split.scheme not in {"http", "https"} or not split.hostname:
        raise YahooSerpLayoutError(f"organic result has no absolute target URL: {href!r}")
    if split.hostname.endswith("search.yahoo.com"):
        raise YahooSerpLayoutError(f"organic result target is still a Yahoo redirect: {href!r}")
    return href


def parse_yahoo_serp(body: bytes | str) -> tuple[SerpResult, ...]:
    """Return the organic results of a Yahoo SERP in page order.

    Organic result links carry ``data-matarget="algo"`` and point at a
    ``*.search.yahoo.com/.../RU=<encoded target>/...`` redirect. A result without a
    usable absolute target URL is skipped, since it names no page to verify; a
    result without a title is kept because its URL slug can still identify it.
    A page that is not a SERP, or a SERP where no organic result has a usable
    target URL, raises ``YahooSerpLayoutError``: Yahoo was never observed to
    return an empty SERP.
    """

    try:
        text = body.decode("utf-8") if isinstance(body, bytes) else body
    except UnicodeDecodeError as exc:
        raise YahooSerpLayoutError("SERP body is not UTF-8") from exc
    parser = _SerpParser()
    parser.feed(text)
    parser.close()
    if not _collapse(parser.page_title).endswith(_SERP_TITLE_SUFFIX.strip()):
        raise YahooSerpLayoutError(f"not a Yahoo SERP: title {parser.page_title!r}")
    results = []
    for raw in parser.results:
        try:
            url = _target_url(raw["href"])
        except YahooSerpLayoutError:
            continue
        results.append(SerpResult(_collapse(raw["title"]), url, _collapse(raw["snippet"])))
    if not results:
        raise YahooSerpLayoutError("Yahoo SERP has no organic result with a usable target URL")
    return tuple(results)


def _period_pattern(target: YahooTarget) -> re.Pattern[str]:
    year = rf"(?<!\d){target.roc_year}"
    if target.report_period is ReportPeriod.FY:
        return re.compile(rf"{year}年度(?!第)")
    return re.compile(rf"{year}年度?第[{_QUARTER_NUMERALS[target.report_period]}]季")


def _is_cjk(character: str) -> bool:
    return "\u3400" <= character <= "\u4dbf" or "\u4e00" <= character <= "\u9fff"


def _names_company(text: str, company: str) -> bool:
    """Whether ``company`` appears as a whole short name, not inside another one.

    Yahoo mirror titles and slugs put the MOPS subject after punctuation
    (``【公告】``, ``公告-``, ``興櫃：``), and the subject continues after the name
    with 董事會, 民國, 公告, 本公司, a year or punctuation. A CJK character on
    either side otherwise means a longer name: 統一 inside 統一超, 華電 inside 中華電.
    """

    for match in re.finditer(re.escape(company), text):
        before = text[match.start() - 1] if match.start() else ""
        after = text[match.end():]
        if before and _is_cjk(before):
            continue
        if not after or not _is_cjk(after[0]) or after.startswith(_COMPANY_CONTINUATIONS):
            return True
    return False


def is_target_candidate(result: SerpResult, target: YahooTarget) -> bool:
    """Whether a result is a Yahoo stock-news page whose visible identity fits the task.

    Title and URL slug are checked together because SERP titles may be truncated
    while the slug carries the full announcement subject. This is a lenient
    pre-filter for later verification of the page itself, not acceptance.
    """

    split = urlsplit(result.url)
    if split.scheme not in {"http", "https"} or split.hostname != MIRROR_HOST:
        return False
    if not split.path.startswith("/news/"):
        return False
    text = unicodedata.normalize("NFKC", f"{result.title} {unquote(split.path)}")
    company = unicodedata.normalize("NFKC", target.company)
    if not _names_company(text, company) or "財務報告" not in text:
        return False
    if not _period_pattern(target).search(text):
        return False
    if target.report_scope is not None:
        wanted = _SCOPE_WORDING[target.report_scope]
        other = next(word for scope, word in _SCOPE_WORDING.items() if scope is not target.report_scope)
        if other in text and wanted not in text:
            return False
    code = _SNIPPET_CODE.search(unicodedata.normalize("NFKC", result.snippet))
    return code is None or code.group(1) == target.stock_id


@dataclass(frozen=True, slots=True)
class YahooSearchOutcome:
    """Candidates when ``outcome`` is ``None``; otherwise why there are none."""

    candidates: tuple[SerpResult, ...]
    outcome: RetryableFailure | SemanticExhaustion | None


def classify_yahoo_serp_response(
    target: YahooTarget, status: int, body: bytes | str
) -> YahooSearchOutcome:
    """Classify one fetched Yahoo search response for ``target``.

    Only a recognized HTTP 200 SERP can yield ``not_found``, and only when none of
    its organic results matches the target identity. Bot-validation redirects,
    ``/_bv/`` errors, other statuses and unrecognized pages are retryable.
    """

    if status == 429:
        return YahooSearchOutcome((), RetryableFailure.RATE_LIMITED)
    if status != 200:
        return YahooSearchOutcome((), RetryableFailure.TEMPORARY_ERROR)
    try:
        results = parse_yahoo_serp(body)
    except YahooSerpLayoutError:
        return YahooSearchOutcome((), RetryableFailure.TEMPORARY_ERROR)
    candidates = tuple(result for result in results if is_target_candidate(result, target))
    if not candidates:
        return YahooSearchOutcome((), SemanticExhaustion.NOT_FOUND)
    return YahooSearchOutcome(candidates, None)


def classify_yahoo_serp_capture(target: YahooTarget, metadata_file: Path) -> YahooSearchOutcome:
    """Classify a capture written by ``tools/yahoo_serp_capture.js``.

    The capture must be for exactly this target's query and its body must match
    the recorded hash. When the tool exits without writing a capture (no HTTP 200
    document, e.g. ``/_bv/`` answered 500), report ``temporary_error`` instead.
    """

    metadata_file = Path(metadata_file)
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    expected = _plan_for(target).url
    if metadata["request"]["url"] != expected:
        raise ValueError(
            f"capture query {metadata['request']['url']!r} is not the target query {expected!r}"
        )
    response = metadata["response"]
    final = urlsplit(response["final_url"])
    if (final.hostname, final.path) != ("tw.search.yahoo.com", "/search"):
        raise ValueError(f"capture final_url is not Yahoo search: {response['final_url']!r}")
    body = gzip.decompress((metadata_file.parent / response["body_file"]).read_bytes())
    if hashlib.sha256(body).hexdigest() != response["sha256"]:
        raise ValueError(f"capture body sha256 mismatch for {metadata_file}")
    return classify_yahoo_serp_response(target, response["status"], body)
