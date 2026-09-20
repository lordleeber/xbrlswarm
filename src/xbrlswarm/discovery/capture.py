from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Protocol
from urllib.request import Request, urlopen

from .models import DiscoveryCase

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SENSITIVE_HEADERS = {"authorization", "cookie", "proxy-authorization", "x-api-key"}


class ResponseLike(Protocol):
    status: int
    headers: object

    def read(self) -> bytes: ...

    def geturl(self) -> str: ...

    def __enter__(self) -> "ResponseLike": ...

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None: ...


OpenUrl = Callable[..., ResponseLike]


@dataclass(frozen=True, slots=True)
class CaptureRequest:
    case: DiscoveryCase
    name: str
    url: str
    method: str = "GET"
    request_headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes | None = None
    extension: str = "bin"

    def __post_init__(self) -> None:
        if not _SAFE_NAME.fullmatch(self.name):
            raise ValueError("name 只能包含英文字母、數字、句點、底線或連字號")
        if not _SAFE_NAME.fullmatch(self.extension):
            raise ValueError("extension 必須是簡單且安全的副檔名")
        method = self.method.upper()
        if method not in {"GET", "POST"}:
            raise ValueError("階段 0 擷取器只支援 GET 與 POST")
        object.__setattr__(self, "method", method)
        if not self.url.startswith("https://"):
            raise ValueError("階段 0 來源擷取要求使用 https URL")


@dataclass(frozen=True, slots=True)
class CaptureResult:
    body_path: Path
    headers_path: Path
    metadata_path: Path
    sha256: str
    size_bytes: int


def _redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {
        key: ("[REDACTED]" if key.lower() in _SENSITIVE_HEADERS else value)
        for key, value in headers.items()
    }


def _headers_to_dict(headers: object) -> dict[str, str]:
    items = getattr(headers, "items", None)
    if items is None:
        return {}
    return {str(key): str(value) for key, value in items()}


def _atomic_write(path: Path, data: bytes, *, overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(f"拒絕覆寫既有擷取檔案：{path}")

    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if not overwrite and path.exists():
            raise FileExistsError(f"拒絕覆寫既有擷取檔案：{path}")
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def capture_raw_response(
    capture: CaptureRequest,
    output_root: Path,
    *,
    opener: OpenUrl = urlopen,
    timeout: float = 30.0,
    overwrite: bool = False,
    now: Callable[[], datetime] | None = None,
) -> CaptureResult:
    """取得單一來源回應，並完整保存原始 bytes 與來源追溯資訊。

    此函式刻意不解析或解讀 MOPS 欄位。階段 0 的目標是在正式契約定版前，
    先完整保存來源實際回傳的內容。
    """

    case_root = (
        Path(output_root)
        / capture.case.stock_id
        / str(capture.case.fiscal_year)
        / capture.case.report_period.value
    )
    body_path = case_root / f"{capture.name}.{capture.extension}"
    headers_path = case_root / f"{capture.name}.headers.json"
    metadata_path = case_root / f"{capture.name}.meta.json"

    if not overwrite:
        existing = [path for path in (body_path, headers_path, metadata_path) if path.exists()]
        if existing:
            joined = ", ".join(str(path) for path in existing)
            raise FileExistsError(f"拒絕覆寫既有擷取檔案：{joined}")

    request_headers = {
        "User-Agent": "xbrlswarm-discovery/0.1 (+source-research)",
        "Accept": "*/*",
        **dict(capture.request_headers),
    }
    request = Request(
        capture.url,
        data=capture.body,
        headers=request_headers,
        method=capture.method,
    )

    with opener(request, timeout=timeout) as response:
        body = response.read()
        status = int(response.status)
        final_url = response.geturl()
        response_headers = _headers_to_dict(response.headers)

    digest = hashlib.sha256(body).hexdigest()
    retrieved_at = (now or (lambda: datetime.now(timezone.utc)))()
    if retrieved_at.tzinfo is None:
        raise ValueError("retrieved_at 必須包含時區資訊")

    request_body_hash = hashlib.sha256(capture.body).hexdigest() if capture.body is not None else None
    metadata = {
        "case": {
            "stock_id": capture.case.stock_id,
            "company_name": capture.case.company_name,
            "fiscal_year": capture.case.fiscal_year,
            "report_period": capture.case.report_period.value,
        },
        "request": {
            "method": capture.method,
            "url": capture.url,
            "headers": _redact_headers(request_headers),
            "body_sha256": request_body_hash,
            "body_size_bytes": len(capture.body) if capture.body is not None else 0,
        },
        "response": {
            "status": status,
            "final_url": final_url,
            "headers_file": headers_path.name,
            "body_file": body_path.name,
            "sha256": digest,
            "size_bytes": len(body),
        },
        "retrieved_at": retrieved_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    _atomic_write(body_path, body, overwrite=overwrite)
    _atomic_write(
        headers_path,
        (json.dumps(response_headers, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(),
        overwrite=overwrite,
    )
    _atomic_write(
        metadata_path,
        (json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(),
        overwrite=overwrite,
    )

    return CaptureResult(
        body_path=body_path,
        headers_path=headers_path,
        metadata_path=metadata_path,
        sha256=digest,
        size_bytes=len(body),
    )
