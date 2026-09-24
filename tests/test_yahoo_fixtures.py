"""Step-44 raw Yahoo fixture provenance and scenario coverage."""

from __future__ import annotations

import gzip
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

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
    assert set(cases) == set(ARTICLE_CASES) | {
        "no_result", "rate_limit", "unexpected_page", "search_redirect"
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

    metadata, _, body = _raw(cases["no_result"])
    assert metadata["origin"] == "synthetic"
    assert metadata["response"]["status"] == 200
    assert "找不到符合搜尋條件的結果" in body.decode("utf-8")

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
