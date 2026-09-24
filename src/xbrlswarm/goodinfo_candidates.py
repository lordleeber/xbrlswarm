"""Extract unverified report-announcement candidates from a Goodinfo list."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

from .domain import ReportPeriod
from .goodinfo_list import AnnouncementListCapture, AnnouncementListQuery, _same_query

_PERIOD_MARKERS = {
    ReportPeriod.Q1: re.compile(r"第\s*[1１一]\s*季"),
    ReportPeriod.Q2: re.compile(r"第\s*[2２二]\s*季"),
    ReportPeriod.Q3: re.compile(r"第\s*[3３三]\s*季"),
}
_HALF_YEAR = re.compile(r"([上下])半年度")
_ANNUAL_REPORT = re.compile(r"年度|\d{3,4}\s*年\s*(?:合併|個體|個別)?\s*財務報告")
_DETAIL_PATHS = {
    "/tw/StockAnnounceDetail.asp",
    "/tw2/StockAnnounceDetail.asp",
    "/tw/data/StockAnnounceDetail.asp",
    "/tw2/data/StockAnnounceDetail.asp",
}
_CHARSET = re.compile(r"(?:^|;)\s*charset\s*=\s*['\"]?([A-Za-z0-9_-]+)", re.I)


@dataclass(frozen=True, slots=True)
class GoodinfoListCandidate:
    display_title: str
    detail_url: str
    list_url: str
    list_raw_payload_hash: str
    report_period_hints: tuple[ReportPeriod, ...]
    report_scope_hints: tuple[str, ...]
    scheduled_meeting: bool


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None
            self._text = []


def _decode(body: bytes, content_type: str) -> str:
    if "html" not in content_type.lower():
        raise ValueError("Goodinfo list content type must be HTML")
    charset = _CHARSET.search(content_type)
    encoding = charset.group(1).lower() if charset else "utf-8"
    if encoding not in {"utf-8", "utf8", "big5", "cp950"}:
        raise ValueError(f"unsupported Goodinfo list charset: {encoding}")
    try:
        return body.decode(encoding)
    except UnicodeError as error:
        raise ValueError("Goodinfo list bytes do not match declared charset") from error


def _detail_url(href: str, *, list_url: str, query: AnnouncementListQuery) -> str | None:
    url = urljoin(list_url, href)
    parsed = urlsplit(url)
    if (parsed.scheme, parsed.netloc) != ("https", "goodinfo.tw") or parsed.path not in _DETAIL_PATHS:
        return None
    params = parse_qs(parsed.query)
    if params.get("STOCK_ID") != [query.stock_id]:
        return None
    if len(params.get("SUBJECT", [])) != 1 or not params["SUBJECT"][0].strip():
        return None
    times = params.get("CLAIM_TIME", [])
    if len(times) != 1:
        return None
    try:
        claim_date = datetime.strptime(times[0], "%Y/%m/%d %H:%M:%S").date()
    except ValueError:
        return None
    if not query.start_date <= claim_date <= query.end_date:
        return None
    return url


def _period_hints(title: str) -> tuple[ReportPeriod, ...]:
    quarters = tuple(period for period, marker in _PERIOD_MARKERS.items() if marker.search(title))
    if quarters:
        return quarters
    half_year = _HALF_YEAR.search(title)
    if half_year:
        return (ReportPeriod.Q2,) if half_year.group(1) == "上" else ()
    if _ANNUAL_REPORT.search(title):
        return (ReportPeriod.FY,)
    return ()


def parse_goodinfo_candidates(
    body: bytes,
    *,
    query: AnnouncementListQuery,
    final_url: str,
    content_type: str,
) -> tuple[GoodinfoListCandidate, ...]:
    """Return title-based hints for matching detail links, never accepted evidence."""

    if not _same_query(query.url, final_url):
        raise ValueError("Goodinfo list URL does not preserve the requested query")
    parser = _Links()
    parser.feed(_decode(body, content_type))
    list_hash = f"sha256:{hashlib.sha256(body).hexdigest()}"
    candidates: list[GoodinfoListCandidate] = []
    seen: set[str] = set()
    for href, title in parser.links:
        detail_url = _detail_url(href, list_url=final_url, query=query)
        if detail_url is None or detail_url in seen or "財務報告" not in title:
            continue
        periods = _period_hints(title)
        if not periods:
            continue
        scopes = tuple(scope for scope, present in (
            ("合併", "合併" in title),
            ("個體", "個體" in title or "個別" in title),
        ) if present)
        candidates.append(GoodinfoListCandidate(
            display_title=title,
            detail_url=detail_url,
            list_url=final_url,
            list_raw_payload_hash=list_hash,
            report_period_hints=periods,
            report_scope_hints=scopes,
            scheduled_meeting="預計召開" in title or "召開日期" in title,
        ))
        seen.add(detail_url)
    return tuple(candidates)


def parse_captured_goodinfo_candidates(
    capture: AnnouncementListCapture,
) -> tuple[GoodinfoListCandidate, ...]:
    """Read a Step-34 capture only if its raw bytes match stored provenance."""

    body = Path(capture.body_path).read_bytes()
    metadata = json.loads(Path(capture.metadata_path).read_text(encoding="utf-8"))
    digest = f"sha256:{hashlib.sha256(body).hexdigest()}"
    if (
        digest != capture.raw_payload_hash
        or digest != metadata["response"]["raw_payload_hash"]
        or len(body) != metadata["response"]["size_bytes"]
        or metadata["query"] != {
            "stock_id": capture.query.stock_id,
            "start_date": capture.query.start_date.isoformat(),
            "end_date": capture.query.end_date.isoformat(),
            "url": capture.query.url,
        }
    ):
        raise ValueError("Goodinfo capture provenance does not match raw list bytes")
    return parse_goodinfo_candidates(
        body,
        query=capture.query,
        final_url=metadata["response"]["final_url"],
        content_type=metadata["response"]["content_type"],
    )
