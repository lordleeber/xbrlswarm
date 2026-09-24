"""Capture a Goodinfo historical announcement list for an explicit date range."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen

from .discovery.capture import _acquire_capture_lock, _atomic_write, _release_capture_lock

_ENDPOINT = "https://goodinfo.tw/tw/StockAnnounceList.asp"
_STOCK_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")
_CHALLENGE_MARKERS = (
    b"cf-chl", b"cf-mitigated", b"Just a moment",
    "初始化中".encode(), "初始化中".encode("big5"),
)
_LIST_MARKERS = ("公告".encode(), "公告".encode("big5"), b"StockAnnounceList")


@dataclass(frozen=True, slots=True)
class AnnouncementListQuery:
    stock_id: str
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if not isinstance(self.stock_id, str) or not _STOCK_ID.fullmatch(self.stock_id):
            raise ValueError("stock_id must contain only letters, digits, underscores or hyphens")
        if type(self.start_date) is not date or type(self.end_date) is not date:
            raise ValueError("start_date and end_date must be dates")
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")

    @property
    def url(self) -> str:
        params = {
            "STOCK_ID": self.stock_id,
            "START_DT": self.start_date.strftime("%Y/%m/%d"),
            "END_DT": self.end_date.strftime("%Y/%m/%d"),
        }
        return f"{_ENDPOINT}?{urlencode(params)}"


@dataclass(frozen=True, slots=True)
class AnnouncementListCapture:
    query: AnnouncementListQuery
    body_path: Path
    metadata_path: Path
    raw_payload_hash: str
    size_bytes: int


def _same_query(requested: str, actual: str) -> bool:
    expected, returned = urlsplit(requested), urlsplit(actual)
    requested_fields = parse_qs(expected.query, keep_blank_values=True)
    returned_fields = parse_qs(returned.query, keep_blank_values=True)
    return (
        (returned.scheme, returned.netloc) == (expected.scheme, expected.netloc)
        and returned.path in {"/tw/StockAnnounceList.asp", "/tw2/StockAnnounceList.asp"}
        and all(returned_fields.get(key) == value for key, value in requested_fields.items())
    )


def _validate_list_response(
    query: AnnouncementListQuery,
    body: bytes,
    *,
    status: int,
    final_url: str,
    content_type: str,
    challenge: str = "",
) -> None:
    """Apply the same response acceptance rules to network and cached bytes."""

    if status != 200:
        raise ValueError(f"Goodinfo list returned HTTP {status}")
    if not _same_query(query.url, final_url):
        raise ValueError("Goodinfo list redirected away from the requested stock/date range")
    if challenge or any(marker.lower() in body[:20_000].lower() for marker in _CHALLENGE_MARKERS):
        raise ValueError("Goodinfo list returned an access challenge")
    if "html" not in content_type.lower() or b"<html" not in body[:20_000].lower():
        raise ValueError("Goodinfo list did not return HTML")
    if not any(marker in body for marker in _LIST_MARKERS):
        raise ValueError("Goodinfo response is not an announcement list")


def capture_announcement_list(
    query: AnnouncementListQuery,
    output_root: Path,
    *,
    opener: Callable = urlopen,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> AnnouncementListCapture:
    """Fetch and store raw list HTML without interpreting announcement rows.

    A rejected or challenged response is not an empty announcement list.
    Existing captures are never overwritten.
    """

    root = Path(output_root) / query.stock_id
    name = f"{query.start_date.isoformat()}_{query.end_date.isoformat()}"
    body_path = root / f"{name}.html"
    metadata_path = root / f"{name}.json"
    lock_path = root / f".{name}.capture.lock"
    lock_fd = _acquire_capture_lock(lock_path)
    try:
        return _capture_locked(query, body_path, metadata_path, opener=opener, clock=clock)
    finally:
        _release_capture_lock(lock_fd, lock_path)


def _capture_locked(
    query: AnnouncementListQuery,
    body_path: Path,
    metadata_path: Path,
    *,
    opener: Callable,
    clock: Callable[[], datetime],
) -> AnnouncementListCapture:
    if body_path.exists() or metadata_path.exists():
        raise FileExistsError(f"announcement list capture already exists: {body_path.name}")

    request = Request(
        query.url,
        headers={
            "Accept": "text/html",
            "User-Agent": "xbrlswarm/0.1 (+historical-announcement-research)",
        },
    )
    with opener(request, timeout=30) as response:
        body = response.read()
        status = int(response.status)
        final_url = response.geturl()
        content_type = response.headers.get("Content-Type", "")
        challenge = response.headers.get("cf-mitigated", "")

    _validate_list_response(
        query, body, status=status, final_url=final_url,
        content_type=content_type, challenge=challenge,
    )

    retrieved_at = clock()
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise ValueError("clock must return a timezone-aware datetime")
    digest = hashlib.sha256(body).hexdigest()
    metadata = {
        "source_type": "goodinfo",
        "query": {
            "stock_id": query.stock_id,
            "start_date": query.start_date.isoformat(),
            "end_date": query.end_date.isoformat(),
            "url": query.url,
        },
        "response": {
            "http_status": status,
            "final_url": final_url,
            "content_type": content_type,
            "raw_payload_hash": f"sha256:{digest}",
            "size_bytes": len(body),
        },
        "retrieved_at": retrieved_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    _atomic_write(body_path, body, overwrite=False)
    _atomic_write(metadata_path, (json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode(), overwrite=False)
    return AnnouncementListCapture(query, body_path, metadata_path, f"sha256:{digest}", len(body))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m xbrlswarm.goodinfo_list")
    parser.add_argument("--stock-id", required=True)
    parser.add_argument("--start-date", required=True, type=date.fromisoformat)
    parser.add_argument("--end-date", required=True, type=date.fromisoformat)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        query = AnnouncementListQuery(args.stock_id, args.start_date, args.end_date)
        from .goodinfo_operations import GoodinfoOperationalClient
        capture = GoodinfoOperationalClient(args.output_root).capture_list(query)
    except (ValueError, FileExistsError, HTTPError, URLError) as error:
        parser.error(str(error))
    print(json.dumps({"body_path": str(capture.body_path), "metadata_path": str(capture.metadata_path), "raw_payload_hash": capture.raw_payload_hash}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
