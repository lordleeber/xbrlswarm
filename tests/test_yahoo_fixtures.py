"""Step-44 raw Yahoo fixture provenance and scenario coverage."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest


FIXTURES = Path(__file__).parent / "fixtures" / "yahoo"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
ARTICLE_CASES = {
    "valid_result": ("公信董事會通過113年度合併財務報告", "113/12/31"),
    "wrong_year": ("公信董事會通過114年度合併財務報告", "114/12/31"),
    "wrong_quarter": ("公信董事會通過113年第二季合併財務報告", "113/06/30"),
    "wrong_company": ("友達董事會通過113年度合併財務報告", "113/12/31"),
    "wrong_scope": ("公信董事會通過113年度個體財務報告", "113/12/31"),
}


SEARCH_CASES = {"search_results", "no_result"}


class _Head(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.description = ""
        self._title_open = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "title":
            self._title_open = True
        if tag == "meta" and attributes.get("name") == "description":
            self.description = attributes.get("content") or ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._title_open = False

    def handle_data(self, data: str) -> None:
        if self._title_open:
            self.title += data


class _SerpResults(HTMLParser):
    """Collect organic result targets from Yahoo `rd.search.yahoo.com` redirect links."""

    def __init__(self) -> None:
        super().__init__()
        self.targets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag != "a" or attributes.get("data-matarget") != "algo":
            return
        href = attributes.get("href") or ""
        marker = "/RU="
        start = href.index(marker) + len(marker)
        self.targets.append(unquote(href[start:href.index("/", start)]))


def _serp_targets(body: bytes) -> list[str]:
    parser = _SerpResults()
    parser.feed(body.decode("utf-8"))
    return parser.targets


def _raw(case: dict) -> tuple[dict, dict, bytes]:
    metadata = json.loads((FIXTURES / case["metadata"]).read_text(encoding="utf-8"))
    headers = {
        key.lower(): value for key, value in json.loads(
            (FIXTURES / case["headers"]).read_text(encoding="utf-8")
        ).items()
    }
    body = gzip.decompress((FIXTURES / case["body"]).read_bytes())
    return metadata, headers, body


def test_manifest_has_required_scenarios_and_single_dimension_mismatches() -> None:
    assert MANIFEST["schema_version"] == 1
    assert MANIFEST["source"] == "yahoo_tw_stock_and_search"
    cases = {case["scenario"]: case for case in MANIFEST["cases"]}
    assert len(cases) == len(MANIFEST["cases"])
    assert set(cases) == set(ARTICLE_CASES) | SEARCH_CASES | {
        "rate_limit", "unexpected_page", "search_redirect"
    }

    target = MANIFEST["target_task"]
    for scenario in ARTICLE_CASES:
        identity = cases[scenario]["observed_identity"]
        differences = {
            field for field in target if identity[field] != target[field]
        }
        expected = {
            "valid_result": set(),
            "wrong_year": {"fiscal_year"},
            "wrong_quarter": {"report_period"},
            "wrong_company": {"stock_id", "company"},
            "wrong_scope": {"report_scope"},
        }[scenario]
        assert differences == expected


def test_page_kind_matches_observed_response() -> None:
    kinds = {case["scenario"]: case["page_kind"] for case in MANIFEST["cases"]}
    assert kinds == {
        **{scenario: "article" for scenario in ARTICLE_CASES},
        "unexpected_page": "quote_page",
        "search_redirect": "search_redirect",
        "search_results": "search_results",
        "no_result": "search_results",
        "rate_limit": "rate_limit",
    }
    for case in MANIFEST["cases"]:
        metadata, _, _ = _raw(case)
        if case["page_kind"] in {"article", "quote_page", "search_results"}:
            assert metadata["response"]["status"] == 200
    unexpected = next(case for case in MANIFEST["cases"] if case["scenario"] == "unexpected_page")
    metadata, _, _ = _raw(unexpected)
    assert urlparse(metadata["request"]["url"]).path == "/quote/8119.TWO"


@pytest.mark.parametrize("case", MANIFEST["cases"], ids=lambda case: case["scenario"])
def test_raw_response_and_metadata_are_replayable(case: dict) -> None:
    metadata, headers, body = _raw(case)
    response = metadata["response"]
    assert metadata["origin"] == case["origin"]
    assert metadata["request"]["method"] == "GET"
    assert response["body_file"] == case["body"]
    assert response["headers_file"] == case["headers"]
    assert response["content_encoding"] == "gzip"
    assert response["size_bytes"] == len(body)
    assert response["stored_size_bytes"] == (FIXTURES / case["body"]).stat().st_size
    assert response["sha256"] == case["sha256"] == hashlib.sha256(body).hexdigest()
    assert urlparse(metadata["request"]["url"]).hostname in {
        "tw.stock.yahoo.com", "tw.search.yahoo.com"
    }
    assert urlparse(response["final_url"]).hostname in {
        "tw.stock.yahoo.com", "tw.search.yahoo.com"
    }
    assert "set-cookie" not in headers
    assert (metadata["retrieved_at"] is not None) == (case["origin"] == "live")
    if case["origin"] == "synthetic":
        assert "not an observed Yahoo layout" in metadata["synthetic_purpose"]


@pytest.mark.parametrize("scenario", ARTICLE_CASES)
def test_live_article_identity_is_visible_in_raw_html(scenario: str) -> None:
    case = next(case for case in MANIFEST["cases"] if case["scenario"] == scenario)
    metadata, headers, body = _raw(case)
    identity = case["observed_identity"]
    head = _Head()
    head.feed(body.decode("utf-8"))

    assert case["origin"] == "live"
    assert metadata["response"]["status"] == 200
    assert headers["content-type"].startswith("text/html")
    assert head.title == "【公告】" + ARTICLE_CASES[scenario][0]
    assert f"公司名稱：{identity['company']}({identity['stock_id']})" in head.description
    assert f"主 旨：{ARTICLE_CASES[scenario][0]}" in head.description
    assert "財務報告" in head.description
    assert ARTICLE_CASES[scenario][1] in head.description
    assert '"datePublished"' in body.decode("utf-8")


def test_negative_transport_and_page_cases_are_distinct() -> None:
    cases = {case["scenario"]: case for case in MANIFEST["cases"]}

    metadata, headers, _ = _raw(cases["rate_limit"])
    assert metadata["origin"] == "synthetic"
    assert metadata["response"]["status"] == 429
    assert headers["retry-after"] == "60"

    metadata, headers, body = _raw(cases["search_redirect"])
    assert metadata["origin"] == "live"
    assert metadata["response"]["status"] == 307
    assert body == b""
    assert headers["location"].startswith("/_bv/v.gif?")

    metadata, _, body = _raw(cases["unexpected_page"])
    head = _Head()
    head.feed(body.decode("utf-8"))
    assert metadata["origin"] == "live"
    assert metadata["response"]["status"] == 200
    assert "走勢圖" in head.title
    assert not head.title.startswith("【公告】")


@pytest.mark.parametrize("scenario", sorted(SEARCH_CASES))
def test_live_serp_passed_bot_validation_redirect(scenario: str) -> None:
    case = next(case for case in MANIFEST["cases"] if case["scenario"] == scenario)
    metadata, headers, body = _raw(case)
    chain = metadata["redirect_chain"]
    request_url = metadata["request"]["url"]

    assert case["origin"] == "live"
    assert case["page_kind"] == "search_results"
    assert "Playwright" in metadata["client"]
    assert "cookie" not in metadata["request"]["headers"]
    assert [hop["status"] for hop in chain] == [307, 307, 200]
    assert chain[0]["url"] == request_url
    assert chain[0]["location"].startswith("/_bv/v.gif?")
    assert urlparse(chain[1]["url"]).path == "/_bv/v.gif"
    assert chain[1]["location"] == request_url
    assert chain[2]["url"] == metadata["response"]["final_url"] == request_url
    assert metadata["response"]["status"] == 200
    assert headers["content-type"].startswith("text/html")
    assert "- Yahoo 網頁搜尋</title>" in body.decode("utf-8")


def test_live_serp_hit_lists_target_stock_candidates() -> None:
    case = next(case for case in MANIFEST["cases"] if case["scenario"] == "search_results")
    _, _, body = _raw(case)
    targets = _serp_targets(body)

    assert len(targets) == 7
    assert all("8119" in target for target in targets)
    assert (
        "https://goodinfo.tw/tw/StockFinDetail.asp?RPT_CAT=IS_M_YEAR&STOCK_ID=8119"
        in targets
    )
    assert not any(urlparse(target).hostname == "tw.stock.yahoo.com" for target in targets)


def test_live_no_result_serp_has_filler_results_without_target_candidates() -> None:
    case = next(case for case in MANIFEST["cases"] if case["scenario"] == "no_result")
    metadata, _, body = _raw(case)
    targets = _serp_targets(body)
    text = body.decode("utf-8")

    assert "qzxwvkjqpfmtlbrgx" in metadata["request"]["url"]
    assert targets
    assert not any("8119" in target or "公信" in unquote(target) for target in targets)
    assert "找不到符合搜尋條件的結果" not in text


def test_serp_capture_tool_keeps_fixture_header_format() -> None:
    tool = (Path(__file__).parents[1] / "tools" / "yahoo_serp_capture.js").read_text(
        encoding="utf-8"
    )
    kept = re.search(r"KEPT_RESPONSE_HEADERS = \[([^\]]*)\]", tool)
    assert kept is not None
    kept_headers = set(re.findall(r"'([a-z-]+)'", kept.group(1)))
    assert "set-cookie" not in kept_headers
    assert "key !== 'cookie'" in tool
    for scenario in sorted(SEARCH_CASES):
        case = next(case for case in MANIFEST["cases"] if case["scenario"] == scenario)
        headers = json.loads((FIXTURES / case["headers"]).read_text(encoding="utf-8"))
        assert set(headers) <= kept_headers
    assert "tools/yahoo_serp_capture.js" in (FIXTURES / "README.md").read_text(
        encoding="utf-8"
    )
