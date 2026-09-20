from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from email.message import Message
from pathlib import Path

import pytest

from xbrlswarm.discovery.capture import CaptureRequest, capture_raw_response
from xbrlswarm.discovery.models import DiscoveryCase, ReportPeriod


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body
        self.status = 200
        headers = Message()
        headers["Content-Type"] = "text/html; charset=utf-8"
        headers["X-Test"] = "fixture"
        headers["Set-Cookie"] = "a=1"
        headers["Set-Cookie"] = "b=2"
        self.headers = headers

    def read(self) -> bytes:
        return self._body

    def geturl(self) -> str:
        return "https://mops.twse.com.tw/final"

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


def test_capture_preserves_exact_bytes_and_provenance(tmp_path: Path) -> None:
    raw = b"<html>\x00raw-mops-bytes</html>\n"
    seen: dict[str, object] = {}

    def opener(request, timeout: float):
        seen["request"] = request
        seen["timeout"] = timeout
        return FakeResponse(raw)

    case = DiscoveryCase("2330", "台積電", 2024, ReportPeriod.Q1)
    request = CaptureRequest(
        case=case,
        name="listing",
        url="https://mops.twse.com.tw/example",
        request_headers={"Cookie": "session=secret", "X-Research": "phase0"},
        extension="html",
    )
    result = capture_raw_response(
        request,
        tmp_path,
        opener=opener,
        now=lambda: datetime(2026, 9, 20, 4, 0, tzinfo=timezone.utc),
    )

    assert result.body_path.read_bytes() == raw
    assert result.sha256 == hashlib.sha256(raw).hexdigest()
    assert result.size_bytes == len(raw)
    assert seen["timeout"] == 30.0

    headers = json.loads(result.headers_path.read_text())
    assert {"name": "Content-Type", "value": "text/html; charset=utf-8"} in headers
    assert [item["value"] for item in headers if item["name"] == "Set-Cookie"] == ["a=1", "b=2"]

    meta = json.loads(result.metadata_path.read_text())
    assert meta["case"] == {
        "stock_id": "2330",
        "company_name": "台積電",
        "fiscal_year": 2024,
        "report_period": "Q1",
    }
    assert meta["response"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert meta["response"]["final_url"] == "https://mops.twse.com.tw/final"
    assert meta["retrieved_at"] == "2026-09-20T04:00:00Z"
    assert meta["request"]["headers"]["Cookie"] == "[REDACTED]"
    assert meta["request"]["headers"]["X-Research"] == "phase0"


def test_capture_refuses_to_overwrite_by_default(tmp_path: Path) -> None:
    def opener(request, timeout: float):
        return FakeResponse(b"first")

    request = CaptureRequest(
        case=DiscoveryCase("6147", "頎邦", 2024, ReportPeriod.FY),
        name="document-list",
        url="https://mops.twse.com.tw/example",
        extension="html",
    )
    capture_raw_response(request, tmp_path, opener=opener)

    with pytest.raises(FileExistsError):
        capture_raw_response(request, tmp_path, opener=opener)


def test_capture_requires_timezone_aware_retrieval_time(tmp_path: Path) -> None:
    def opener(request, timeout: float):
        return FakeResponse(b"data")

    request = CaptureRequest(
        case=DiscoveryCase("4542", "科嶠", 2024, ReportPeriod.Q3),
        name="source",
        url="https://mops.twse.com.tw/example",
    )
    with pytest.raises(ValueError, match="時區資訊"):
        capture_raw_response(
            request,
            tmp_path,
            opener=opener,
            now=lambda: datetime(2026, 9, 20, 12, 0),
        )


def test_capture_rejects_unsafe_name_extension_and_non_https_url() -> None:
    case = DiscoveryCase("2330", "台積電", 2024, ReportPeriod.Q2)
    with pytest.raises(ValueError):
        CaptureRequest(case=case, name="../escape", url="https://mops.twse.com.tw/example")
    with pytest.raises(ValueError):
        CaptureRequest(
            case=case,
            name="safe",
            url="https://mops.twse.com.tw/example",
            extension="headers.json",
        )
    with pytest.raises(ValueError):
        CaptureRequest(case=case, name="safe", url="http://mops.twse.com.tw/example")


def test_capture_preflight_prevents_partial_fixture_when_sibling_exists(tmp_path: Path) -> None:
    case = DiscoveryCase("2330", "台積電", 2024, ReportPeriod.Q1)
    case_root = tmp_path / "2330" / "2024" / "Q1"
    case_root.mkdir(parents=True)
    sibling = case_root / "listing.headers.json"
    sibling.write_text("{}\n")

    called = False

    def opener(request, timeout: float):
        nonlocal called
        called = True
        return FakeResponse(b"must-not-be-written")

    request = CaptureRequest(
        case=case,
        name="listing",
        url="https://mops.twse.com.tw/example",
        extension="html",
    )
    with pytest.raises(FileExistsError):
        capture_raw_response(request, tmp_path, opener=opener)

    assert called is False
    assert not (case_root / "listing.html").exists()
    assert not (case_root / "listing.meta.json").exists()


def test_capture_lock_prevents_concurrent_writers(tmp_path: Path) -> None:
    case = DiscoveryCase("2330", "台積電", 2024, ReportPeriod.Q1)
    request = CaptureRequest(
        case=case,
        name="listing",
        url="https://mops.twse.com.tw/example",
        extension="html",
    )
    entered = threading.Event()
    release = threading.Event()
    errors: list[BaseException] = []
    calls = 0

    def opener(request, timeout: float):
        nonlocal calls
        calls += 1
        entered.set()
        assert release.wait(2)
        return FakeResponse(b"first")

    def first_capture() -> None:
        try:
            capture_raw_response(request, tmp_path, opener=opener)
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=first_capture)
    thread.start()
    assert entered.wait(2)
    try:
        with pytest.raises(FileExistsError, match="另一個擷取程序"):
            capture_raw_response(
                request,
                tmp_path,
                opener=lambda request, timeout: FakeResponse(b"second"),
                overwrite=True,
            )
    finally:
        release.set()
        thread.join(2)

    assert errors == []
    assert calls == 1
    case_root = tmp_path / "2330" / "2024" / "Q1"
    assert (case_root / "listing.html").read_bytes() == b"first"
    assert not (case_root / ".listing.capture.lock").exists()
