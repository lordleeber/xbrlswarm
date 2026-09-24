"""Import browser-saved Goodinfo pages through the network acceptance rules.

Goodinfo answers automated clients with a Cloudflare challenge. A person may
open the same page in a browser and save its HTML; this module accepts those
bytes only when they pass the same list or detail validation as a network
response, and stores them as ``manual_browser`` captures in the Step-40 cache
layout. It never contacts Goodinfo and never writes evidence or tasks.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence, TypeVar

from .goodinfo_candidates import GoodinfoListCandidate
from .goodinfo_detail import GoodinfoDetailCapture, _locator, capture_goodinfo_detail
from .goodinfo_list import (
    AnnouncementListCapture,
    AnnouncementListQuery,
    _same_query,
    capture_announcement_list,
)
from .goodinfo_operations import GoodinfoOperationalClient
from .goodinfo_pilot import PILOT_CASES, GoodinfoPilotCase, pilot_detail_candidates

MANUAL_CAPTURE_METHOD = "manual_browser"
_META_CHARSET = re.compile(rb"<meta[^>]+charset\s*=\s*[\"']?([A-Za-z0-9_-]+)", re.I)
_SAVED_FROM = re.compile(rb"<!--\s*saved from url=\(\d+\)(\S+?)\s*-->", re.I)
_T = TypeVar("_T")


class _SavedPage:
    """Present saved bytes as the successful response the user's browser saw."""

    status = 200

    def __init__(self, url: str, body: bytes, content_type: str) -> None:
        self.url, self.body = url, body
        self.headers = {"Content-Type": content_type}

    def __enter__(self) -> _SavedPage:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self.body

    def geturl(self) -> str:
        return self.url


@dataclass(frozen=True, slots=True)
class ManualCaptureItem:
    kind: str
    case: str
    url: str
    save_as: str


def _saved_page(
    path: Path, url: str, same_page: Callable[[str], bool],
) -> tuple[_SavedPage, datetime]:
    body = Path(path).read_bytes()
    saved_from = _SAVED_FROM.search(body[:4096])
    if saved_from is not None and not same_page(saved_from.group(1).decode("latin-1")):
        raise ValueError(f"{Path(path).name} was saved from a different Goodinfo page")
    charset = _META_CHARSET.search(body[:4096])
    encoding = charset.group(1).decode("ascii").lower() if charset else "utf-8"
    saved_at = datetime.fromtimestamp(Path(path).stat().st_mtime, timezone.utc)
    return _SavedPage(url, body, f"text/html; charset={encoding}"), saved_at


def _provenance(path: Path, imported_at: datetime) -> dict[str, str]:
    if imported_at.tzinfo is None or imported_at.utcoffset() is None:
        raise ValueError("clock must return a timezone-aware datetime")
    return {
        "capture_method": MANUAL_CAPTURE_METHOD,
        "source_file": Path(path).name,
        "retrieved_at_basis": "saved_file_mtime",
        "imported_at": imported_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _import_once(
    path: Path, cached: Callable[[], _T | None], existing_hash: Callable[[_T], str],
    store: Callable[[], _T],
) -> tuple[_T, bool]:
    existing = cached()
    if existing is None:
        return store(), True
    digest = f"sha256:{hashlib.sha256(Path(path).read_bytes()).hexdigest()}"
    if existing_hash(existing) != digest:
        raise ValueError(f"a different capture already exists for {Path(path).name}")
    return existing, False


def import_manual_list(
    client: GoodinfoOperationalClient,
    query: AnnouncementListQuery,
    html_path: Path,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> tuple[AnnouncementListCapture, bool]:
    """Store a browser-saved list page; return (capture, newly_imported)."""

    def store() -> AnnouncementListCapture:
        page, saved_at = _saved_page(
            html_path, query.url, lambda url: _same_query(query.url, url),
        )
        return capture_announcement_list(
            query, client.root, opener=lambda _request, **_: page,
            clock=lambda: saved_at, extra_metadata=_provenance(html_path, clock()),
        )

    return client._locked(lambda: _import_once(
        html_path, lambda: client._cached_list(query),
        lambda capture: capture.raw_payload_hash, store,
    ))


def _same_detail(expected_url: str, saved_url: str) -> bool:
    try:
        return _locator(saved_url) == _locator(expected_url)
    except ValueError:
        return False


def import_manual_detail(
    client: GoodinfoOperationalClient,
    candidate: GoodinfoListCandidate,
    html_path: Path,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> tuple[GoodinfoDetailCapture, bool]:
    """Store a browser-saved detail page for a candidate from an imported list."""

    _locator(candidate.detail_url)

    def store() -> GoodinfoDetailCapture:
        page, saved_at = _saved_page(
            html_path, candidate.detail_url,
            lambda url: _same_detail(candidate.detail_url, url),
        )
        return capture_goodinfo_detail(
            candidate, client.root / "details", opener=lambda _request, **_: page,
            clock=lambda: saved_at, extra_metadata=_provenance(html_path, clock()),
        )

    return client._locked(lambda: _import_once(
        html_path, lambda: client._cached_detail(candidate),
        lambda capture: capture.raw_payload_hash, store,
    ))


def _list_file(case: GoodinfoPilotCase) -> str:
    return f"list_{case.key}.html"


def _detail_file(case: GoodinfoPilotCase, index: int) -> str:
    return f"detail_{case.key}_{index}.html"


def manual_capture_plan(
    client: GoodinfoOperationalClient,
    *,
    cases: Sequence[GoodinfoPilotCase] = PILOT_CASES,
    max_details_per_case: int = 3,
) -> list[ManualCaptureItem]:
    """List pages still to be saved; details appear once their list is imported."""

    items: list[ManualCaptureItem] = []
    for case in cases:
        capture = client.cached_list(case.query)
        if capture is None:
            items.append(ManualCaptureItem("list", case.key, case.query.url, _list_file(case)))
            continue
        candidates = pilot_detail_candidates(case, capture)[:max_details_per_case]
        for index, candidate in enumerate(candidates, 1):
            if client.cached_detail(candidate) is None:
                items.append(ManualCaptureItem(
                    "detail", case.key, candidate.detail_url, _detail_file(case, index),
                ))
    return items


def import_manual_inbox(
    client: GoodinfoOperationalClient,
    inbox: Path,
    *,
    cases: Sequence[GoodinfoPilotCase] = PILOT_CASES,
    max_details_per_case: int = 3,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> list[dict]:
    """Import every expected file present in ``inbox``; report each outcome.

    One rejected page does not stop the others. A list must be imported
    before its detail files can be matched to candidates.
    """

    inbox = Path(inbox)
    outcomes: list[dict] = []
    expected: set[str] = set()

    def attempt(name: str, action: Callable[[Path], tuple[object, bool]]) -> None:
        expected.add(name)
        path = inbox / name
        if not path.is_file():
            return
        try:
            _, imported = action(path)
            outcomes.append({"file": name, "status": "imported" if imported else "already_imported"})
        except (ValueError, OSError) as error:
            outcomes.append({"file": name, "status": "rejected", "error": str(error)})

    for case in cases:
        attempt(_list_file(case), lambda path: import_manual_list(
            client, case.query, path, clock=clock,
        ))
        try:
            capture = client.cached_list(case.query)
        except (ValueError, OSError):
            continue
        if capture is None:
            continue
        candidates = pilot_detail_candidates(case, capture)[:max_details_per_case]
        for index, candidate in enumerate(candidates, 1):
            attempt(_detail_file(case, index), lambda path: import_manual_detail(
                client, candidate, path, clock=clock,
            ))
    for path in sorted(inbox.glob("*.html")):
        if path.name not in expected:
            outcomes.append({"file": path.name, "status": "unexpected"})
    return outcomes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m xbrlswarm.goodinfo_manual")
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="list pages still to save in a browser")
    plan.add_argument("--output-root", type=Path, required=True)
    imports = commands.add_parser("import", help="import saved pages from an inbox")
    imports.add_argument("--output-root", type=Path, required=True)
    imports.add_argument("--inbox", type=Path, required=True)
    args = parser.parse_args(argv)
    client = GoodinfoOperationalClient(args.output_root)
    if args.command == "plan":
        for item in manual_capture_plan(client):
            print(json.dumps({"kind": item.kind, "case": item.case, "save_as": item.save_as,
                              "url": item.url}, ensure_ascii=False))
        return 0
    if not args.inbox.is_dir():
        parser.error(f"inbox is not a directory: {args.inbox}")
    outcomes = import_manual_inbox(client, args.inbox)
    for outcome in outcomes:
        print(json.dumps(outcome, ensure_ascii=False))
    return 1 if any(outcome["status"] == "rejected" for outcome in outcomes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
