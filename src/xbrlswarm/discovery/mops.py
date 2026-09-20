from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode
from urllib.request import urlopen

from .capture import (
    CaptureRequest,
    CaptureResult,
    OpenUrl,
    _atomic_write,
    capture_raw_response,
)
from .cases import DISCOVERY_CASES
from .models import DiscoveryCase, ReportPeriod

_MOPS_XBRL_DOWNLOAD = "https://mopsov.twse.com.tw/server-java/FileDownLoad"
_MOPS_XBRL_REFERER = "https://mopsov.twse.com.tw/mops/web/t203sb01"
_CAPTURE_NAME = "xbrl-consolidated"
_CAPTURE_EXTENSION = "bin"
_STORED_BODY_SUFFIX = ".bin.gz"
_SEASON = {
    ReportPeriod.Q1: 1,
    ReportPeriod.Q2: 2,
    ReportPeriod.Q3: 3,
    ReportPeriod.FY: 4,
}
_XBRL_MARKERS = (
    b"ix:nonfraction",
    b"ix:nonnumeric",
    b"<xbrli:xbrl",
)
_CONTENT_DISPOSITION_FILENAME = re.compile(
    r'filename\s*=\s*(?:"([^"]+)"|([^;\s]+))',
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class VerifiedMopsCapture:
    case: DiscoveryCase
    body_path: Path
    headers_path: Path
    metadata_path: Path
    sha256: str
    size_bytes: int


def build_mops_xbrl_capture(case: DiscoveryCase, *, report_id: str = "C") -> CaptureRequest:
    if report_id not in {"C", "A"}:
        raise ValueError("report_id 必須為 C（合併）或 A（個體）")
    query = urlencode(
        {
            "functionName": "t164sb01",
            "step": "9",
            "co_id": case.stock_id,
            "year": str(case.fiscal_year),
            "season": str(_SEASON[case.report_period]),
            "report_id": report_id,
        }
    )
    return CaptureRequest(
        case=case,
        name=_CAPTURE_NAME if report_id == "C" else "xbrl-individual",
        url=f"{_MOPS_XBRL_DOWNLOAD}?{query}",
        request_headers={
            "Referer": _MOPS_XBRL_REFERER,
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/140.0 Safari/537.36 "
                "xbrlswarm-discovery/0.1"
            ),
        },
        extension=_CAPTURE_EXTENSION,
    )


def _case_root(output_root: Path, case: DiscoveryCase) -> Path:
    return Path(output_root) / case.stock_id / str(case.fiscal_year) / case.report_period.value


def _raw_body_path(output_root: Path, case: DiscoveryCase) -> Path:
    return _case_root(output_root, case) / f"{_CAPTURE_NAME}.{_CAPTURE_EXTENSION}"


def _expected_paths(output_root: Path, case: DiscoveryCase) -> tuple[Path, Path, Path]:
    root = _case_root(output_root, case)
    return (
        root / f"{_CAPTURE_NAME}{_STORED_BODY_SUFFIX}",
        root / f"{_CAPTURE_NAME}.headers.json",
        root / f"{_CAPTURE_NAME}.meta.json",
    )


def _capture_lock_path(output_root: Path, case: DiscoveryCase) -> Path:
    return _case_root(output_root, case) / f".{_CAPTURE_NAME}.capture.lock"


def _preflight_batch_targets(output_root: Path, *, overwrite: bool) -> None:
    locked = [
        _capture_lock_path(output_root, case)
        for case in DISCOVERY_CASES
        if _capture_lock_path(output_root, case).exists()
    ]
    if locked:
        joined = ", ".join(str(path) for path in locked)
        raise FileExistsError(f"已有另一個擷取程序正在處理固定案例：{joined}")

    if overwrite:
        return

    existing = [
        path
        for case in DISCOVERY_CASES
        for path in (*_expected_paths(output_root, case), _raw_body_path(output_root, case))
        if path.exists()
    ]
    if existing:
        joined = ", ".join(str(path) for path in existing)
        raise FileExistsError(f"拒絕部分覆寫固定 MOPS capture set：{joined}")


def _compress_capture_result(result: CaptureResult, *, overwrite: bool) -> CaptureResult:
    raw = result.body_path.read_bytes()
    compressed_path = result.body_path.with_suffix(result.body_path.suffix + ".gz")
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    _atomic_write(compressed_path, compressed, overwrite=overwrite)

    metadata = json.loads(result.metadata_path.read_text(encoding="utf-8"))
    response = metadata["response"]
    response["body_file"] = compressed_path.name
    response["content_encoding"] = "gzip"
    response["stored_size_bytes"] = len(compressed)
    _atomic_write(
        result.metadata_path,
        (json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(),
        overwrite=True,
    )
    result.body_path.unlink()

    return CaptureResult(
        body_path=compressed_path,
        headers_path=result.headers_path,
        metadata_path=result.metadata_path,
        sha256=result.sha256,
        size_bytes=result.size_bytes,
    )


def capture_mops_discovery_cases(
    output_root: Path,
    *,
    overwrite: bool = False,
    opener: OpenUrl = urlopen,
    now: Callable[[], datetime] | None = None,
) -> tuple[CaptureResult, ...]:
    _preflight_batch_targets(output_root, overwrite=overwrite)

    results: list[CaptureResult] = []
    for case in DISCOVERY_CASES:
        captured = capture_raw_response(
            build_mops_xbrl_capture(case),
            output_root,
            opener=opener,
            overwrite=overwrite,
            now=now,
        )
        results.append(_compress_capture_result(captured, overwrite=overwrite))
    return tuple(results)


def _contains_xbrl_markup(body: bytes) -> bool:
    sample = body[:2_000_000].lower()
    return any(marker in sample for marker in _XBRL_MARKERS)


def _looks_like_xbrl(body: bytes) -> bool:
    if _contains_xbrl_markup(body):
        return True

    stream = io.BytesIO(body)
    if not zipfile.is_zipfile(stream):
        return False

    stream.seek(0)
    try:
        with zipfile.ZipFile(stream) as archive:
            for item in archive.infolist():
                if item.is_dir() or item.file_size > 5_000_000:
                    continue
                if not item.filename.lower().endswith((".xbrl", ".xml", ".html", ".htm")):
                    continue
                with archive.open(item) as member:
                    if _contains_xbrl_markup(member.read(2_000_000)):
                        return True
    except (OSError, RuntimeError, zipfile.BadZipFile):
        return False
    return False


def _header_value(headers: list[dict[str, str]], name: str) -> str | None:
    expected = name.lower()
    for item in headers:
        if item["name"].lower() == expected:
            return item["value"]
    return None


def _content_disposition_filename(headers: list[dict[str, str]]) -> str | None:
    value = _header_value(headers, "Content-Disposition")
    if value is None:
        return None
    match = _CONTENT_DISPOSITION_FILENAME.search(value)
    if match is None:
        return None
    return match.group(1) or match.group(2)


def _expected_mops_filename_suffix(case: DiscoveryCase) -> str:
    quarter = "Q4" if case.report_period is ReportPeriod.FY else case.report_period.value
    return f"-{case.stock_id}-{case.fiscal_year}{quarter}.html"


def _read_stored_body(case: DiscoveryCase, body_path: Path) -> bytes:
    try:
        return gzip.decompress(body_path.read_bytes())
    except (OSError, EOFError) as exc:
        raise ValueError(f"{case.key} 的 gzip raw payload 損壞") from exc


def verify_mops_capture_set(output_root: Path) -> tuple[VerifiedMopsCapture, ...]:
    verified: list[VerifiedMopsCapture] = []
    for case in DISCOVERY_CASES:
        body_path, headers_path, metadata_path = _expected_paths(output_root, case)
        missing = [path.name for path in (body_path, headers_path, metadata_path) if not path.exists()]
        if missing:
            raise FileNotFoundError(
                f"{case.key} 缺少 MOPS capture 檔案：{', '.join(missing)}"
            )

        stored_body = body_path.read_bytes()
        body = _read_stored_body(case, body_path)
        digest = hashlib.sha256(body).hexdigest()
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        headers = json.loads(headers_path.read_text(encoding="utf-8"))

        if not isinstance(headers, list) or not all(
            isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and isinstance(item.get("value"), str)
            for item in headers
        ):
            raise ValueError(f"{case.key} 的 response headers 格式無效")

        filename = _content_disposition_filename(headers)
        expected_suffix = _expected_mops_filename_suffix(case)
        if filename is None or not filename.lower().endswith(expected_suffix.lower()):
            raise ValueError(
                f"{case.key} 的 Content-Disposition filename 不符合預期案例"
            )

        expected_case = {
            "stock_id": case.stock_id,
            "company_name": case.company_name,
            "fiscal_year": case.fiscal_year,
            "report_period": case.report_period.value,
        }
        if metadata.get("case") != expected_case:
            raise ValueError(f"{case.key} 的 metadata case 不一致")

        expected_request = build_mops_xbrl_capture(case)
        request = metadata.get("request")
        response = metadata.get("response")
        if not isinstance(request, dict) or request.get("url") != expected_request.url:
            raise ValueError(f"{case.key} 的 request URL 不是預期的官方 MOPS URL")
        if not isinstance(response, dict):
            raise ValueError(f"{case.key} 缺少 response metadata")
        if response.get("status") != 200:
            raise ValueError(f"{case.key} 的 HTTP status 不是 200")
        if response.get("final_url") != expected_request.url:
            raise ValueError(f"{case.key} 的 final URL 不是預期的官方 MOPS URL")
        if response.get("body_file") != body_path.name:
            raise ValueError(f"{case.key} 的 body_file metadata 不一致")
        if response.get("headers_file") != headers_path.name:
            raise ValueError(f"{case.key} 的 headers_file metadata 不一致")
        if response.get("content_encoding") != "gzip":
            raise ValueError(f"{case.key} 的 raw body storage encoding 不是 gzip")
        if response.get("sha256") != digest:
            raise ValueError(f"{case.key} 的 SHA-256 與 raw body 不一致")
        if response.get("size_bytes") != len(body):
            raise ValueError(f"{case.key} 的 size_bytes 與 raw body 不一致")
        if response.get("stored_size_bytes") != len(stored_body):
            raise ValueError(f"{case.key} 的 stored_size_bytes 與 gzip body 不一致")
        if not _looks_like_xbrl(body):
            raise ValueError(f"{case.key} 的 raw payload 不是可辨識的 XBRL / iXBRL / ZIP")

        verified.append(
            VerifiedMopsCapture(
                case=case,
                body_path=body_path,
                headers_path=headers_path,
                metadata_path=metadata_path,
                sha256=digest,
                size_bytes=len(body),
            )
        )
    return tuple(verified)
