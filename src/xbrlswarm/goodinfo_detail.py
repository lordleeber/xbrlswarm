"""Capture and parse Goodinfo announcement details without accepting evidence."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

from .discovery.capture import _acquire_capture_lock, _atomic_write, _release_capture_lock
from .goodinfo_candidates import GoodinfoListCandidate, _CHARSET, _DETAIL_PATHS
from .goodinfo_list import _CHALLENGE_MARKERS

_DATE = r"\d{4}/\d{2}/\d{2}"
_BOARD = re.compile(
    r"(?:財務報告)?提報董事會或經董事會決議日期\s*[:：]\s*(" + _DATE + r")"
)
_AUDIT = re.compile(r"審計委員會通過(?:財務報告)?日期\s*[:：]\s*(" + _DATE + r")")
_PERIOD = re.compile(
    r"(?:財務報告(?:或年度自結財務資訊)?\s*)?報導期間\s*起訖日期"
    r"(?:\([^)]*\))?\s*[:：]\s*(" + _DATE + r")\s*[~～]\s*(" + _DATE + r")"
)
_SPEECH = re.compile(r"發言日期\s*(" + _DATE + r")\s*發言時間\s*(\d{2}:\d{2}:\d{2})")
_SUBJECT = re.compile(r"主旨\s+(.+?)\s+說\s*明(?:\s|\d+\.)", re.S)
_MINGUO_YEAR = re.compile(r"(?<![0-9])([1-9][0-9]{0,2})年")


@dataclass(frozen=True, slots=True)
class GoodinfoDetail:
    stock_id: str
    claim_time: datetime
    subject: str
    period_start: date | None
    period_end: date | None
    board_date: date | None
    audit_committee_date: date | None
    detail_url: str
    final_url: str
    raw_payload_hash: str
    list_url: str
    list_raw_payload_hash: str
    scheduled_meeting: bool


@dataclass(frozen=True, slots=True)
class GoodinfoDetailCapture:
    candidate: GoodinfoListCandidate
    body_path: Path
    metadata_path: Path
    raw_payload_hash: str
    size_bytes: int


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title: list[str] = []
        self._in_title = False
        self._hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self._hidden += 1
        if tag == "title":
            self._in_title = True
        if tag in {"td", "th", "tr", "br", "p", "div"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._hidden -= 1
        if tag == "title":
            self._in_title = False
        if tag in {"td", "th", "tr", "br", "p", "div"}:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if self._hidden:
            return
        if self._in_title:
            self.title.append(data)
        else:
            self.parts.append(data)


def _locator(url: str) -> tuple[str, datetime, str]:
    parsed = urlsplit(url)
    if (parsed.scheme, parsed.netloc) != ("https", "goodinfo.tw") or parsed.path not in _DETAIL_PATHS:
        raise ValueError("invalid Goodinfo detail URL")
    params = parse_qs(parsed.query, keep_blank_values=True)
    if any(len(params.get(key, [])) != 1 or not params[key][0].strip()
           for key in ("STOCK_ID", "CLAIM_TIME", "SUBJECT")):
        raise ValueError("Goodinfo detail URL has missing or repeated identity parameters")
    try:
        claim_time = datetime.strptime(params["CLAIM_TIME"][0], "%Y/%m/%d %H:%M:%S")
    except ValueError as error:
        raise ValueError("invalid Goodinfo detail CLAIM_TIME") from error
    return params["STOCK_ID"][0], claim_time, params["SUBJECT"][0]


def _one_date(text: str, pattern: re.Pattern[str], name: str) -> date | None:
    values = pattern.findall(text)
    if not values:
        return None
    try:
        dates = {date.fromisoformat(value.replace("/", "-")) for value in values}
    except ValueError as error:
        raise ValueError(f"invalid Goodinfo {name}") from error
    if len(dates) != 1:
        raise ValueError(f"conflicting Goodinfo {name}")
    return dates.pop()


def _normalized_subject(subject: str) -> str:
    """Match Goodinfo's observed ROC-to-Gregorian year rendering in subjects."""

    compact = "".join(unicodedata.normalize("NFKC", subject).split())
    return _MINGUO_YEAR.sub(
        lambda match: f"{int(match.group(1)) + 1911}年", compact
    )


def parse_goodinfo_detail(
    body: bytes, *, candidate: GoodinfoListCandidate, final_url: str, content_type: str,
) -> GoodinfoDetail:
    """Extract only fields visible on a matching detail page; do not write evidence."""

    stock_id, claim_time, url_subject = _locator(candidate.detail_url)
    if _locator(final_url) != _locator(candidate.detail_url):
        raise ValueError("Goodinfo detail redirected to a different announcement")
    if "html" not in content_type.lower() or b"<html" not in body[:20_000].lower():
        raise ValueError("Goodinfo detail did not return HTML")
    if any(marker.lower() in body[:20_000].lower() for marker in _CHALLENGE_MARKERS):
        raise ValueError("Goodinfo detail returned an access challenge")
    charset = _CHARSET.search(content_type)
    encoding = charset.group(1).lower() if charset else "utf-8"
    if encoding not in {"utf-8", "utf8", "big5", "cp950"}:
        raise ValueError(f"unsupported Goodinfo detail charset: {encoding}")
    try:
        html = body.decode(encoding)
    except UnicodeError as error:
        raise ValueError("Goodinfo detail bytes do not match declared charset") from error

    parser = _VisibleText()
    parser.feed(html)
    title = " ".join("".join(parser.title).split())
    if not re.match(rf"^{re.escape(stock_id)}\s+.+公告訊息", title):
        raise ValueError("Goodinfo detail does not identify the requested stock")
    text = " ".join("".join(parser.parts).split())
    speech = _SPEECH.search(text)
    subject_match = _SUBJECT.search(text)
    if speech is None or subject_match is None:
        raise ValueError("Goodinfo detail lacks announcement fields")
    try:
        visible_claim_time = datetime.strptime(" ".join(speech.groups()), "%Y/%m/%d %H:%M:%S")
    except ValueError as error:
        raise ValueError("invalid Goodinfo speech date or time") from error
    if visible_claim_time != claim_time:
        raise ValueError("Goodinfo detail speech time disagrees with URL")
    subject = " ".join(subject_match.group(1).split())
    if not subject or "財務報告" not in subject:
        raise ValueError("Goodinfo detail subject is not a financial report announcement")
    if _normalized_subject(subject) != _normalized_subject(url_subject):
        raise ValueError("Goodinfo detail subject disagrees with URL SUBJECT")
    explanation = text[subject_match.end():]
    periods = _PERIOD.findall(explanation)
    if len(set(periods)) > 1:
        raise ValueError("conflicting Goodinfo report periods")
    try:
        start, end = (
            tuple(date.fromisoformat(value.replace("/", "-")) for value in periods[0])
            if periods else (None, None)
        )
    except ValueError as error:
        raise ValueError("invalid Goodinfo report period") from error
    if start is not None and start > end:
        raise ValueError("Goodinfo report period starts after it ends")
    return GoodinfoDetail(
        stock_id=stock_id, claim_time=claim_time, subject=subject,
        period_start=start, period_end=end,
        board_date=_one_date(explanation, _BOARD, "board date"),
        audit_committee_date=_one_date(explanation, _AUDIT, "audit committee date"),
        detail_url=candidate.detail_url,
        final_url=final_url,
        raw_payload_hash=f"sha256:{hashlib.sha256(body).hexdigest()}",
        list_url=candidate.list_url,
        list_raw_payload_hash=candidate.list_raw_payload_hash,
        scheduled_meeting=(
            candidate.scheduled_meeting or "預計召開" in subject or "召開日期" in subject
        ),
    )


def capture_goodinfo_detail(
    candidate: GoodinfoListCandidate, output_root: Path, *,
    opener: Callable = urlopen,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> GoodinfoDetailCapture:
    """Save raw detail bytes and provenance once per announcement URL."""

    stock_id, _, _ = _locator(candidate.detail_url)
    key = hashlib.sha256(candidate.detail_url.encode()).hexdigest()
    root = Path(output_root) / stock_id
    body_path, metadata_path = root / f"{key}.html", root / f"{key}.json"
    lock_path = root / f".{key}.capture.lock"
    lock_fd = _acquire_capture_lock(lock_path)
    try:
        if body_path.exists() or metadata_path.exists():
            raise FileExistsError(f"Goodinfo detail capture already exists: {key}")
        request = Request(candidate.detail_url, headers={
            "Accept": "text/html",
            "User-Agent": "xbrlswarm/0.1 (+historical-announcement-research)",
        })
        with opener(request, timeout=30) as response:
            body = response.read()
            status, final_url = int(response.status), response.geturl()
            content_type = response.headers.get("Content-Type", "")
            challenge = response.headers.get("cf-mitigated", "")
        if status != 200 or challenge:
            raise ValueError(f"Goodinfo detail returned HTTP {status} or an access challenge")
        detail = parse_goodinfo_detail(
            body, candidate=candidate, final_url=final_url, content_type=content_type,
        )
        retrieved_at = clock()
        if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        metadata = {
            "source_type": "goodinfo", "detail_url": candidate.detail_url,
            "list_url": candidate.list_url, "list_raw_payload_hash": candidate.list_raw_payload_hash,
            "response": {"http_status": status, "final_url": final_url, "content_type": content_type,
                         "raw_payload_hash": detail.raw_payload_hash, "size_bytes": len(body)},
            "retrieved_at": retrieved_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        _atomic_write(body_path, body, overwrite=False)
        metadata_bytes = (json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode()
        _atomic_write(metadata_path, metadata_bytes, overwrite=False)
        return GoodinfoDetailCapture(
            candidate, body_path, metadata_path, detail.raw_payload_hash, len(body)
        )
    finally:
        _release_capture_lock(lock_fd, lock_path)


def parse_captured_goodinfo_detail(capture: GoodinfoDetailCapture) -> GoodinfoDetail:
    """Reparse raw captured bytes only when stored provenance still matches."""

    body = capture.body_path.read_bytes()
    metadata = json.loads(capture.metadata_path.read_text(encoding="utf-8"))
    digest = f"sha256:{hashlib.sha256(body).hexdigest()}"
    if (digest != capture.raw_payload_hash or digest != metadata["response"]["raw_payload_hash"]
            or len(body) != capture.size_bytes or len(body) != metadata["response"]["size_bytes"]
            or metadata["detail_url"] != capture.candidate.detail_url
            or metadata["list_url"] != capture.candidate.list_url
            or metadata["list_raw_payload_hash"] != capture.candidate.list_raw_payload_hash):
        raise ValueError("Goodinfo detail capture provenance does not match raw bytes")
    return parse_goodinfo_detail(
        body, candidate=capture.candidate, final_url=metadata["response"]["final_url"],
        content_type=metadata["response"]["content_type"],
    )
