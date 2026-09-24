"""Run a fixed, low-volume Goodinfo Q1 discovery pilot without accepting evidence.

With ``offline=True`` the pilot replays only verified local captures, such
as browser-saved pages imported by ``goodinfo_manual``, and never contacts
Goodinfo.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Sequence
from urllib.error import HTTPError, URLError

from .domain import ReportPeriod, calendar_year_period_end
from .goodinfo_candidates import GoodinfoListCandidate, parse_captured_goodinfo_candidates
from .goodinfo_detail import parse_captured_goodinfo_detail
from .goodinfo_list import AnnouncementListCapture, AnnouncementListQuery
from .goodinfo_operations import GoodinfoOperationalClient


@dataclass(frozen=True, slots=True)
class GoodinfoPilotCase:
    stock_id: str
    fiscal_year: int
    report_period: ReportPeriod
    start_date: date
    end_date: date

    @property
    def key(self) -> str:
        return f"{self.stock_id}-{self.fiscal_year}-{self.report_period.value}"

    @property
    def query(self) -> AnnouncementListQuery:
        return AnnouncementListQuery(self.stock_id, self.start_date, self.end_date)


def _q1_case(stock_id: str, year: int) -> GoodinfoPilotCase:
    # Pilot observation window only, not a verified legal publication rule.
    return GoodinfoPilotCase(
        stock_id, year, ReportPeriod.Q1, date(year, 4, 1), date(year, 6, 30),
    )


PILOT_CASES = (
    _q1_case("4542", 2024),
    _q1_case("6147", 2024),
    _q1_case("2330", 2024),
    _q1_case("6147", 2022),
    _q1_case("2330", 2020),
)


def pilot_detail_candidates(
    case: GoodinfoPilotCase, capture: AnnouncementListCapture,
) -> tuple[GoodinfoListCandidate, ...]:
    """Candidates whose list title hints at the case period, in list order."""

    return tuple(candidate for candidate in parse_captured_goodinfo_candidates(capture)
                 if case.report_period in candidate.report_period_hints)


def _capture_method(metadata_path: Path) -> str:
    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    return metadata.get("capture_method", "network")


def run_goodinfo_pilot(
    output_root: Path,
    *,
    client: GoodinfoOperationalClient | None = None,
    cases: Sequence[GoodinfoPilotCase] = PILOT_CASES,
    max_details_per_case: int = 3,
    offline: bool = False,
) -> dict:
    """Return raw-capture and parse outcomes; never write evidence or tasks."""

    if max_details_per_case < 1:
        raise ValueError("max_details_per_case must be positive")
    client = client if client is not None else GoodinfoOperationalClient(output_root)
    results: list[dict] = []
    for case in cases:
        query = case.query
        row = {
            "case": case.key,
            "query_url": query.url,
            "start_date": query.start_date.isoformat(),
            "end_date": query.end_date.isoformat(),
            "status": "not_attempted",
            "capture_method": None,
            "list_raw_payload_hash": None,
            "candidate_count": None,
            "matching_candidate_count": None,
            "detail_results": [],
            "detail_limit_reached": False,
            "error": None,
        }
        results.append(row)
        try:
            capture = client.cached_list(query) if offline else client.capture_list(query)
            if capture is None:
                row["status"] = "not_captured"
                continue
            row["capture_method"] = _capture_method(capture.metadata_path)
            row["list_raw_payload_hash"] = capture.raw_payload_hash
            candidates = parse_captured_goodinfo_candidates(capture)
            matching = pilot_detail_candidates(case, capture)
            row["candidate_count"] = len(candidates)
            row["matching_candidate_count"] = len(matching)
            row["detail_limit_reached"] = len(matching) > max_details_per_case
            row["status"] = "list_captured"
        except HTTPError as error:
            row["status"] = "access_blocked" if error.code in {403, 429} else "http_error"
            row["error"] = f"HTTP {error.code}"
            continue
        except URLError as error:
            row["status"] = "transport_error"
            row["error"] = str(error.reason)
            continue
        except (ValueError, OSError, KeyError, TypeError) as error:
            row["status"] = "list_rejected"
            row["error"] = str(error)
            continue

        for candidate in matching[:max_details_per_case]:
            detail_row = {
                "detail_url": candidate.detail_url,
                "status": "not_attempted",
                "capture_method": None,
                "raw_payload_hash": None,
                "final_url": None,
                "claim_time": None,
                "subject": None,
                "period_start": None,
                "period_end": None,
                "period_matches_case": None,
                "error": None,
            }
            row["detail_results"].append(detail_row)
            try:
                capture = (client.cached_detail(candidate) if offline
                           else client.capture_detail(candidate))
                if capture is None:
                    detail_row["status"] = "not_captured"
                    continue
                detail = parse_captured_goodinfo_detail(capture)
                expected_end = calendar_year_period_end(case.fiscal_year, case.report_period)
                detail_row.update({
                    "status": "parsed",
                    "capture_method": _capture_method(capture.metadata_path),
                    "raw_payload_hash": detail.raw_payload_hash,
                    "final_url": detail.final_url,
                    "claim_time": detail.claim_time.isoformat(sep=" "),
                    "subject": detail.subject,
                    "period_start": detail.period_start.isoformat() if detail.period_start else None,
                    "period_end": detail.period_end.isoformat() if detail.period_end else None,
                    "period_matches_case": (
                        detail.period_start == date(case.fiscal_year, 1, 1)
                        and detail.period_end == expected_end
                    ),
                })
            except HTTPError as error:
                detail_row["status"] = "access_blocked" if error.code in {403, 429} else "http_error"
                detail_row["error"] = f"HTTP {error.code}"
                if detail_row["status"] == "access_blocked":
                    break
            except URLError as error:
                detail_row["status"] = "transport_error"
                detail_row["error"] = str(error.reason)
            except (ValueError, OSError, KeyError, TypeError) as error:
                detail_row["status"] = "detail_rejected"
                detail_row["error"] = str(error)

    return {
        "schema_version": 1,
        "source": "goodinfo_low_volume_pilot",
        "query_window_kind": "exploratory_not_legal_deadline",
        "capture_mode": "offline_replay" if offline else "network",
        "pilot_cases": [case.key for case in cases],
        "results": results,
        "summary": {
            "cases": len(results),
            "lists_captured": sum(row["status"] == "list_captured" for row in results),
            "access_blocked": sum(row["status"] == "access_blocked" for row in results),
            "not_captured": sum(row["status"] == "not_captured" for row in results),
            "details_parsed": sum(detail["status"] == "parsed" for row in results
                                  for detail in row["detail_results"]),
            "matching_period_details": sum(detail["period_matches_case"] is True
                                           for row in results for detail in row["detail_results"]),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m xbrlswarm.goodinfo_pilot")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--offline", action="store_true",
                        help="replay verified local captures only; never contact Goodinfo")
    args = parser.parse_args(argv)
    if args.report.exists():
        parser.error(f"pilot report already exists: {args.report}")
    report = run_goodinfo_pilot(args.output_root, offline=args.offline)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))
    return 0 if report["summary"]["lists_captured"] == report["summary"]["cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
