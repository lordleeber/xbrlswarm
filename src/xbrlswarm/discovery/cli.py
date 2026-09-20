from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .capture import CaptureRequest, capture_raw_response
from .cases import DISCOVERY_CASES, find_case
from .matrix import load_matrix, render_markdown
from .models import DiscoveryCase, ReportPeriod


def _header(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("header 必須使用 NAME=VALUE 格式")
    name, header_value = value.split("=", 1)
    if not name.strip():
        raise argparse.ArgumentTypeError("header 名稱不得為空白")
    return name.strip(), header_value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xbrlswarm-discovery")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-cases", help="列出階段 0 固定來源探索案例")

    capture = sub.add_parser("capture", help="擷取一份完整原始來源回應")
    capture.add_argument("--stock-id", required=True)
    capture.add_argument("--company-name", required=True)
    capture.add_argument("--fiscal-year", type=int, required=True)
    capture.add_argument("--period", required=True, choices=[item.value for item in ReportPeriod])
    capture.add_argument("--name", required=True)
    capture.add_argument("--url", required=True)
    capture.add_argument("--method", default="GET", choices=["GET", "POST"])
    capture.add_argument("--header", action="append", type=_header, default=[])
    capture.add_argument("--data-file", type=Path)
    capture.add_argument("--extension", default="bin")
    capture.add_argument("--output-root", type=Path, default=Path("tests/fixtures/discovery/mops"))
    capture.add_argument("--overwrite", action="store_true")

    matrix = sub.add_parser("render-matrix", help="驗證並產生來源欄位矩陣")
    matrix.add_argument("--input", type=Path, default=Path("discovery/source_field_matrix.json"))
    matrix.add_argument("--output", type=Path, default=Path("docs/source-field-matrix.md"))

    return parser


def _list_cases() -> int:
    for case in DISCOVERY_CASES:
        print(f"{case.stock_id}\t{case.company_name}\t{case.fiscal_year}\t{case.report_period.value}")
    return 0


def _capture(args: argparse.Namespace) -> int:
    period = ReportPeriod.parse(args.period)
    known = find_case(args.stock_id, args.fiscal_year, period)
    case = known or DiscoveryCase(args.stock_id, args.company_name, args.fiscal_year, period)
    body = args.data_file.read_bytes() if args.data_file else None
    request = CaptureRequest(
        case=case,
        name=args.name,
        url=args.url,
        method=args.method,
        request_headers=dict(args.header),
        body=body,
        extension=args.extension,
    )
    result = capture_raw_response(request, args.output_root, overwrite=args.overwrite)
    print(result.body_path)
    print(f"sha256={result.sha256} 位元組數={result.size_bytes}")
    return 0


def _render_matrix(args: argparse.Namespace) -> int:
    records = load_matrix(args.input)
    content = render_markdown(records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content, encoding="utf-8")
    print(args.output)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "list-cases":
        return _list_cases()
    if args.command == "capture":
        return _capture(args)
    if args.command == "render-matrix":
        return _render_matrix(args)
    parser.error("未知指令")
    return 2


if __name__ == "__main__":
    sys.exit(main())
