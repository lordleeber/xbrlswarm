"""Low-volume, cached Goodinfo retrieval for the backup source workflow."""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import random
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar
from urllib.request import urlopen

from .discovery.capture import _atomic_write
from .goodinfo_candidates import GoodinfoListCandidate
from .goodinfo_detail import (
    GoodinfoDetailCapture,
    _locator,
    capture_goodinfo_detail,
    parse_captured_goodinfo_detail,
)
from .goodinfo_list import (
    AnnouncementListCapture,
    AnnouncementListQuery,
    _validate_list_response,
    capture_announcement_list,
)

_T = TypeVar("_T")


@dataclass(frozen=True, slots=True)
class GoodinfoRequestPolicy:
    min_delay_seconds: float = 3.0
    jitter_seconds: float = 2.0

    def __post_init__(self) -> None:
        if (not math.isfinite(self.min_delay_seconds) or self.min_delay_seconds < 3.0
                or not math.isfinite(self.jitter_seconds) or self.jitter_seconds < 2.0):
            raise ValueError("Goodinfo delay must be at least 3 seconds with 2 seconds of jitter")


class GoodinfoOperationalClient:
    """Serialize Goodinfo requests across processes and reuse verified captures.

    The persistent lock and next-request timestamp are shared by list and
    detail requests under one output root. Cached responses never sleep or
    contact Goodinfo. A rejected response still consumes its request slot.
    """

    def __init__(
        self,
        output_root: Path,
        *,
        policy: GoodinfoRequestPolicy = GoodinfoRequestPolicy(),
        opener: Callable = urlopen,
        clock: Callable[[], float] = time.time,
        sleeper: Callable[[float], None] = time.sleep,
        random_value: Callable[[], float] = random.random,
        retrieval_clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.root = Path(output_root)
        self.policy = policy
        self.opener = opener
        self.clock = clock
        self.sleeper = sleeper
        self.random_value = random_value
        self.retrieval_clock = retrieval_clock

    def _next_allowed_at(self) -> float:
        path = self.root / ".goodinfo-request-state.json"
        if not path.exists():
            return 0.0
        try:
            value = json.loads(path.read_text(encoding="utf-8"))["next_allowed_at"]
        except (ValueError, KeyError, TypeError) as error:
            raise ValueError("invalid Goodinfo request state") from error
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("invalid Goodinfo request state")
        value = float(value)
        if not math.isfinite(value) or value < 0:
            raise ValueError("invalid Goodinfo request state")
        return value

    def _set_next_allowed_at(self, value: float) -> None:
        payload = json.dumps({"next_allowed_at": value}).encode() + b"\n"
        _atomic_write(self.root / ".goodinfo-request-state.json", payload, overwrite=True)

    def _locked(self, action: Callable[[], _T]) -> _T:
        self.root.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.root / ".goodinfo-request.lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            return action()
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _run(self, cached: Callable[[], _T | None], fetch: Callable[[], _T]) -> _T:
        return self._locked(lambda: self._fetch_unless_cached(cached, fetch))

    def _fetch_unless_cached(self, cached: Callable[[], _T | None], fetch: Callable[[], _T]) -> _T:
        hit = cached()
        if hit is not None:
            return hit
        wait = max(0.0, self._next_allowed_at() - self.clock())
        if wait:
            self.sleeper(wait)
        jitter = self.random_value()
        if not isinstance(jitter, (float, int)) or not 0 <= jitter < 1:
            raise ValueError("Goodinfo jitter source must return a value in [0, 1)")
        delay = self.policy.min_delay_seconds + jitter * self.policy.jitter_seconds
        self._set_next_allowed_at(self.clock() + delay)
        try:
            return fetch()
        finally:
            self._set_next_allowed_at(self.clock() + delay)

    def _cached_list(self, query: AnnouncementListQuery) -> AnnouncementListCapture | None:
        name = f"{query.start_date.isoformat()}_{query.end_date.isoformat()}"
        root = self.root / query.stock_id
        body_path, metadata_path = root / f"{name}.html", root / f"{name}.json"
        if not body_path.exists() and not metadata_path.exists():
            return None
        if not body_path.is_file() or not metadata_path.is_file():
            raise ValueError("incomplete Goodinfo list cache")
        body = body_path.read_bytes()
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        response = metadata["response"]
        digest = f"sha256:{hashlib.sha256(body).hexdigest()}"
        expected_query = {
            "stock_id": query.stock_id,
            "start_date": query.start_date.isoformat(),
            "end_date": query.end_date.isoformat(),
            "url": query.url,
        }
        if (metadata.get("source_type") != "goodinfo" or metadata.get("query") != expected_query
                or digest != response.get("raw_payload_hash")
                or len(body) != response.get("size_bytes")):
            raise ValueError("Goodinfo list cache provenance does not match raw bytes")
        _validate_list_response(
            query, body, status=response["http_status"],
            final_url=response["final_url"], content_type=response["content_type"],
        )
        return AnnouncementListCapture(query, body_path, metadata_path, digest, len(body))

    def _cached_detail(self, candidate: GoodinfoListCandidate) -> GoodinfoDetailCapture | None:
        key = hashlib.sha256(candidate.detail_url.encode()).hexdigest()
        stock_id, _, _ = _locator(candidate.detail_url)
        root = self.root / "details" / stock_id
        body_path, metadata_path = root / f"{key}.html", root / f"{key}.json"
        if not body_path.exists() and not metadata_path.exists():
            return None
        if not body_path.is_file() or not metadata_path.is_file():
            raise ValueError("incomplete Goodinfo detail cache")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if (metadata.get("source_type") != "goodinfo"
                or metadata["response"].get("http_status") != 200
                or metadata.get("detail_url") != candidate.detail_url):
            raise ValueError("Goodinfo detail cache provenance does not match request")
        original_candidate = replace(
            candidate,
            list_url=metadata["list_url"],
            list_raw_payload_hash=metadata["list_raw_payload_hash"],
        )
        capture = GoodinfoDetailCapture(
            original_candidate, body_path, metadata_path,
            metadata["response"]["raw_payload_hash"], metadata["response"]["size_bytes"],
        )
        parse_captured_goodinfo_detail(capture)
        return capture

    def cached_list(self, query: AnnouncementListQuery) -> AnnouncementListCapture | None:
        """Return a verified local list capture, or None; never contacts Goodinfo."""

        return self._locked(lambda: self._cached_list(query))

    def cached_detail(self, candidate: GoodinfoListCandidate) -> GoodinfoDetailCapture | None:
        """Return a verified local detail capture, or None; never contacts Goodinfo."""

        _locator(candidate.detail_url)
        return self._locked(lambda: self._cached_detail(candidate))

    def capture_list(self, query: AnnouncementListQuery) -> AnnouncementListCapture:
        return self._run(
            lambda: self._cached_list(query),
            lambda: capture_announcement_list(
                query, self.root, opener=self.opener, clock=self.retrieval_clock,
            ),
        )

    def capture_detail(self, candidate: GoodinfoListCandidate) -> GoodinfoDetailCapture:
        _locator(candidate.detail_url)
        return self._run(
            lambda: self._cached_detail(candidate),
            lambda: capture_goodinfo_detail(
                candidate, self.root / "details", opener=self.opener,
                clock=self.retrieval_clock,
            ),
        )
