"""Step-45 Yahoo query builder, SERP parser and search outcome regressions."""

from __future__ import annotations

import gzip
import json
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

from xbrlswarm.domain import ReportPeriod, RetryableFailure, SemanticExhaustion
from xbrlswarm.yahoo_search import (
    ReportScope,
    SerpResult,
    YahooSerpLayoutError,
    YahooTarget,
    classify_yahoo_serp_capture,
    classify_yahoo_serp_response,
    is_target_candidate,
    parse_yahoo_serp,
    yahoo_search_plan,
)


FIXTURES = Path(__file__).parent / "fixtures" / "yahoo"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
CASES = {case["scenario"]: case for case in MANIFEST["cases"]}
CONTRACT = json.loads(
    (Path(__file__).parents[1] / "contracts" / "yahoo-search-query.json").read_text(
        encoding="utf-8"
    )
)
FY_TARGET = YahooTarget("8119", "公信", 2024, ReportPeriod.FY, ReportScope.CONSOLIDATED)
VALID_MIRROR = json.loads(
    (FIXTURES / CASES["valid_result"]["metadata"]).read_text(encoding="utf-8")
)["request"]["url"]


def _raw(scenario: str) -> tuple[dict, dict, bytes]:
    case = CASES[scenario]
    metadata = json.loads((FIXTURES / case["metadata"]).read_text(encoding="utf-8"))
    headers = {
        key.lower(): value for key, value in json.loads(
            (FIXTURES / case["headers"]).read_text(encoding="utf-8")
        ).items()
    }
    return metadata, headers, gzip.decompress((FIXTURES / case["body"]).read_bytes())


def _mirror(title: str, slug: str | None = None, snippet: str = "") -> SerpResult:
    path = "/news/" + (slug if slug is not None else "公告-" + title) + "-012345678.html"
    return SerpResult(
        title=f"【公告】{title} - Yahoo奇摩股市",
        url="https://tw.stock.yahoo.com" + path,
        snippet=snippet,
    )


# --- query builder -----------------------------------------------------------------


@pytest.mark.parametrize("period,scope,query", [
    ("FY", "consolidated",
     "site:tw.stock.yahoo.com 8119 公信 董事會通過 113年度 合併財務報告"),
    ("Q1", "consolidated",
     "site:tw.stock.yahoo.com 8119 公信 董事會通過 113年第一季 合併財務報告"),
    ("Q2", "individual",
     "site:tw.stock.yahoo.com 8119 公信 董事會通過 113年第二季 個體財務報告"),
    ("Q3", None,
     "site:tw.stock.yahoo.com 8119 公信 董事會通過 113年第三季 財務報告"),
])
def test_query_uses_announcement_title_wording(period, scope, query) -> None:
    plan = yahoo_search_plan("8119", "公信", 2024, period, scope)
    assert plan.query == query
    assert plan.target == YahooTarget(
        "8119", "公信", 2024, ReportPeriod(period),
        None if scope is None else ReportScope(scope),
    )
    split = urlsplit(plan.url)
    assert (split.scheme, split.hostname, split.path) == ("https", "tw.search.yahoo.com", "/search")
    assert parse_qs(split.query) == {"p": [query]}


def test_query_carries_every_roadmap_field() -> None:
    query = yahoo_search_plan("8119", "公信", 2024, "Q2", "consolidated").query
    for part in ("8119", "公信", "113年", "第二季", "財務報告", "合併", "董事會通過"):
        assert part in query
    assert "2024" not in query  # announcement titles use the ROC year


@pytest.mark.parametrize("scenario", sorted(
    scenario for scenario, case in CASES.items() if "query_target" in case
))
def test_builder_url_is_the_url_the_browser_actually_requested(scenario) -> None:
    metadata, _, _ = _raw(scenario)
    target = CASES[scenario]["query_target"]
    plan = yahoo_search_plan(**target)
    # The capture tool encodes with encodeURIComponent; the two must agree byte for byte.
    assert plan.url == metadata["request"]["url"]


@pytest.mark.parametrize("kwargs,match", [
    ({"stock_id": ""}, "stock_id"),
    ({"stock_id": "81 19"}, "stock_id"),
    ({"stock_id": "8119 site:x"}, "stock_id"),
    ({"company": ""}, "company"),
    ({"company": "  "}, "company"),
    ({"company": "公 信"}, "company"),
    ({"company": '"公信"'}, "company"),
    ({"fiscal_year": 1911}, "fiscal_year"),
    ({"fiscal_year": True}, "fiscal_year"),
    ({"fiscal_year": "2024"}, "fiscal_year"),
    ({"report_period": "Q4"}, "Q4"),
    ({"report_scope": "both"}, "report_scope"),
])
def test_invalid_targets_are_rejected(kwargs, match) -> None:
    arguments = {
        "stock_id": "8119", "company": "公信", "fiscal_year": 2024,
        "report_period": "FY", "report_scope": "consolidated", **kwargs,
    }
    with pytest.raises(ValueError, match=match):
        yahoo_search_plan(**arguments)


def test_contract_matches_builder() -> None:
    assert CONTRACT["contract"] == "yahoo_search_query"
    assert CONTRACT["search_url"] == "https://tw.search.yahoo.com/search?p="
    assert CONTRACT["site_restriction"] == "tw.stock.yahoo.com"
    assert CONTRACT["announcement_wording"] == "董事會通過"
    assert CONTRACT["fiscal_year_format"] == "roc_year"
    assert CONTRACT["period_wording"] == {
        "FY": "年度", "Q1": "年第一季", "Q2": "年第二季", "Q3": "年第三季",
    }
    assert CONTRACT["scope_wording"] == {
        "consolidated": "合併", "individual": "個體", "unspecified": "",
    }
    assert CONTRACT["default_fetch_client"] == "real_browser"
    assert CONTRACT["no_result_means"] == "no_serp_candidate_matches_target_identity"
    assert CONTRACT["empty_serp_text_means_absence"] is False
    assert CONTRACT["outcomes"] == {
        "http_200_serp_with_candidates": "candidates",
        "http_200_serp_without_candidates": "not_found",
        "http_200_unrecognized_page": "temporary_error",
        "http_429": "rate_limited",
        "bot_validation_redirect_or_other_status": "temporary_error",
        "capture_without_http_200_document": "temporary_error",
    }
    for period, scope in (("Q2", "individual"), ("FY", None)):
        plan = yahoo_search_plan("0050", "元大台灣50", 2020, period, scope)
        rendered = CONTRACT["query_template"].format(
            site_restriction=CONTRACT["site_restriction"],
            stock_id="0050",
            company="元大台灣50",
            announcement_wording=CONTRACT["announcement_wording"],
            roc_year=109,
            period_wording=CONTRACT["period_wording"][period],
            scope_wording=CONTRACT["scope_wording"][scope or "unspecified"],
        )
        assert plan.query == rendered
        assert plan.url.startswith(CONTRACT["search_url"])


# --- SERP parser --------------------------------------------------------------------


@pytest.mark.parametrize("scenario", sorted(
    case["scenario"] for case in MANIFEST["cases"] if case["page_kind"] == "search_results"
))
def test_parser_reads_every_organic_result_of_live_serps(scenario) -> None:
    _, _, body = _raw(scenario)
    results = parse_yahoo_serp(body)

    assert len(results) == body.decode("utf-8").count('data-matarget="algo"') == 7
    for result in results:
        split = urlsplit(result.url)
        assert split.scheme in {"http", "https"} and split.hostname
        assert "search.yahoo.com" not in split.hostname
        assert result.title and "<" not in result.title
        assert "Yahoo奇摩股市tw.stock.yahoo.com ›" not in result.title


def test_parser_decodes_redirect_target_and_snippet_of_mirror() -> None:
    _, _, body = _raw("builder_fy_consolidated")
    first = parse_yahoo_serp(body)[0]

    assert first.url == VALID_MIRROR
    assert first.title == "【公告】公信董事會通過113年度合併財務報告 - Yahoo奇摩股市"
    assert "公司名稱：公信 (8119)" in first.snippet
    assert "主 旨：公信董事會通過113年度合併財務報告" in first.snippet


def test_parser_keeps_direct_links_and_third_party_targets() -> None:
    _, _, body = _raw("search_results")
    urls = [result.url for result in parse_yahoo_serp(body)]
    assert "https://goodinfo.tw/tw/StockFinDetail.asp?RPT_CAT=IS_M_YEAR&STOCK_ID=8119" in urls


@pytest.mark.parametrize("scenario", ["unexpected_page", "valid_result", "rate_limit"])
def test_non_serp_pages_are_layout_errors(scenario) -> None:
    _, _, body = _raw(scenario)
    with pytest.raises(YahooSerpLayoutError):
        parse_yahoo_serp(body)


@pytest.mark.parametrize("body", [
    b"",
    b"<html><head><title>x - Yahoo \xe7\xb6\xb2\xe9\xa0\x81\xe6\x90\x9c\xe5\xb0\x8b</title></head></html>",
    "<title>q - Yahoo 網頁搜尋</title><a data-matarget=\"algo\" href=\"/relative\"><h3>t</h3></a>".encode(),
    "<title>q - Yahoo 網頁搜尋</title><a data-matarget=\"algo\" href=\"https://x.test/\"></a>".encode(),
])
def test_serp_without_parseable_results_is_a_layout_error(body) -> None:
    with pytest.raises(YahooSerpLayoutError):
        parse_yahoo_serp(body)


# --- target identity ----------------------------------------------------------------


def test_only_the_matching_mirror_is_a_candidate_on_the_live_fy_serp() -> None:
    _, _, body = _raw("builder_fy_consolidated")
    results = parse_yahoo_serp(body)
    candidates = [result for result in results if is_target_candidate(result, FY_TARGET)]

    assert [result.url for result in candidates] == [VALID_MIRROR]
    # The same page also lists other years and a same-suffix company (輔信).
    titles = " ".join(result.title for result in results)
    assert "輔信" in titles and "111" in titles and "107" in titles


@pytest.mark.parametrize("title", [
    "公信董事會通過114年度合併財務報告",       # wrong year
    "公信董事會通過1113年度合併財務報告",      # year only as a digit suffix
    "公信董事會通過113年第二季合併財務報告",    # wrong quarter
    "公信董事會通過113年度第二季合併財務報告",  # quarter written with 年度
    "友達董事會通過113年度合併財務報告",       # wrong company
    "公信董事會通過113年度個體財務報告",       # wrong scope
    "公信董事會決議召開股東常會",              # not a report
    "公信董事會通過113年度盈餘分配案",         # right period, not a financial report
])
def test_single_dimension_mismatches_are_not_candidates(title) -> None:
    assert not is_target_candidate(_mirror(title), FY_TARGET)


@pytest.mark.parametrize("title,target", [
    ("公信董事會通過113年度合併財務報告", FY_TARGET),
    ("公信董事會通過民國113年度合併財務報告", FY_TARGET),
    ("公信董事會通過113年度合併及個體財務報告", FY_TARGET),
    ("公信董事會通過113年第二季合併財務報告",
     YahooTarget("8119", "公信", 2024, ReportPeriod.Q2, ReportScope.CONSOLIDATED)),
    ("公信董事會通過113年度第2季合併財務報告",
     YahooTarget("8119", "公信", 2024, ReportPeriod.Q2, ReportScope.CONSOLIDATED)),
    ("公信董事會通過１１３年第二季個體財務報告",
     YahooTarget("8119", "公信", 2024, ReportPeriod.Q2, ReportScope.INDIVIDUAL)),
    ("公信董事會通過113年度個體財務報告",
     YahooTarget("8119", "公信", 2024, ReportPeriod.FY, None)),
])
def test_matching_titles_are_candidates(title, target) -> None:
    assert is_target_candidate(_mirror(title), target)


def test_identity_can_come_from_the_url_slug_when_the_title_is_truncated() -> None:
    result = SerpResult(
        title="【公告】公信董事會通過113... - Yahoo奇摩股市",
        url=VALID_MIRROR,
        snippet="",
    )
    assert is_target_candidate(result, FY_TARGET)


def test_snippet_company_code_must_match_the_stock_id() -> None:
    title = "公信董事會通過113年度合併財務報告"
    assert is_target_candidate(
        _mirror(title, snippet="日 期：2025年03月12日 公司名稱：公信 (8119) 主 旨：..."), FY_TARGET
    )
    assert not is_target_candidate(
        _mirror(title, snippet="日 期：2025年03月12日 公司名稱：公信 (9999) 主 旨：..."), FY_TARGET
    )


@pytest.mark.parametrize("url", [
    "https://tw.stock.yahoo.com/quote/8119.TWO",
    "https://goodinfo.tw/tw/公告-公信董事會通過113年度合併財務報告",
    "https://tw.news.yahoo.com/news/公告-公信董事會通過113年度合併財務報告.html",
    "http://tw.stock.yahoo.com.evil.test/news/公告-公信董事會通過113年度合併財務報告.html",
])
def test_only_yahoo_stock_news_pages_are_candidates(url) -> None:
    result = SerpResult("【公告】公信董事會通過113年度合併財務報告", url, "")
    assert not is_target_candidate(result, FY_TARGET)


# --- search outcomes ----------------------------------------------------------------


def test_live_fy_serp_yields_the_mirror_candidate() -> None:
    outcome = classify_yahoo_serp_capture(
        FY_TARGET, FIXTURES / CASES["builder_fy_consolidated"]["metadata"]
    )
    assert outcome.outcome is None
    assert [candidate.url for candidate in outcome.candidates] == [VALID_MIRROR]


def test_live_q2_serp_without_the_mirror_is_not_found() -> None:
    target = YahooTarget("8119", "公信", 2024, ReportPeriod.Q2, ReportScope.CONSOLIDATED)
    outcome = classify_yahoo_serp_capture(
        target, FIXTURES / CASES["builder_q2_consolidated"]["metadata"]
    )
    assert outcome.outcome is SemanticExhaustion.NOT_FOUND
    assert outcome.candidates == ()


@pytest.mark.parametrize("scenario", ["search_results", "no_result"])
def test_filler_and_third_party_serps_are_not_found(scenario) -> None:
    metadata, _, body = _raw(scenario)
    outcome = classify_yahoo_serp_response(FY_TARGET, metadata["response"]["status"], body)
    assert outcome.outcome is SemanticExhaustion.NOT_FOUND


@pytest.mark.parametrize("scenario,expected", [
    ("rate_limit", RetryableFailure.RATE_LIMITED),
    ("search_redirect", RetryableFailure.TEMPORARY_ERROR),
    ("unexpected_page", RetryableFailure.TEMPORARY_ERROR),
    ("valid_result", RetryableFailure.TEMPORARY_ERROR),
])
def test_non_serp_responses_are_retryable_not_absence(scenario, expected) -> None:
    metadata, _, body = _raw(scenario)
    outcome = classify_yahoo_serp_response(FY_TARGET, metadata["response"]["status"], body)
    assert outcome.outcome is expected
    assert outcome.candidates == ()


@pytest.mark.parametrize("status", [500, 503, 403, 302])
def test_bot_validation_failures_and_other_statuses_are_retryable(status) -> None:
    outcome = classify_yahoo_serp_response(FY_TARGET, status, b"")
    assert outcome.outcome is RetryableFailure.TEMPORARY_ERROR


def test_capture_for_a_different_query_is_refused(tmp_path) -> None:
    q2 = YahooTarget("8119", "公信", 2024, ReportPeriod.Q2, ReportScope.CONSOLIDATED)
    with pytest.raises(ValueError, match="query"):
        classify_yahoo_serp_capture(q2, FIXTURES / CASES["builder_fy_consolidated"]["metadata"])


def test_capture_with_mismatched_body_hash_is_refused(tmp_path) -> None:
    source = FIXTURES / CASES["builder_fy_consolidated"]["metadata"]
    metadata = json.loads(source.read_text(encoding="utf-8"))
    body_file = metadata["response"]["body_file"]
    (tmp_path / body_file).write_bytes(gzip.compress(b"tampered"))
    (tmp_path / source.name).write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="sha256"):
        classify_yahoo_serp_capture(FY_TARGET, tmp_path / source.name)


def test_capture_rejects_non_yahoo_search_final_url(tmp_path) -> None:
    source = FIXTURES / CASES["builder_fy_consolidated"]["metadata"]
    metadata = json.loads(source.read_text(encoding="utf-8"))
    metadata["response"]["final_url"] = "https://example.test/search"
    body_file = metadata["response"]["body_file"]
    (tmp_path / body_file).write_bytes((FIXTURES / body_file).read_bytes())
    (tmp_path / source.name).write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="final_url"):
        classify_yahoo_serp_capture(FY_TARGET, tmp_path / source.name)


def test_mirror_titles_from_step_44_articles_agree_with_candidate_rule() -> None:
    """Cross-check against the observed identities of the Step-44 article fixtures."""

    for scenario in ("valid_result", "wrong_year", "wrong_quarter", "wrong_company", "wrong_scope"):
        metadata, _, _ = _raw(scenario)
        url = metadata["request"]["url"]
        slug = unquote(urlsplit(url).path)
        title = slug.removeprefix("/news/公告-").rsplit("-", 1)[0]
        result = SerpResult(f"【公告】{title} - Yahoo奇摩股市", url, "")
        identity = CASES[scenario]["observed_identity"]
        assert is_target_candidate(result, FY_TARGET) == (identity == MANIFEST["target_task"])


def test_live_serp_with_other_announcement_wording_still_finds_the_mirror() -> None:
    """頎邦 titles its reports 「民國113年度合併財務報告業經董事會決議」, not 「董事會通過」."""

    case = CASES["builder_fy_other_wording"]
    plan = yahoo_search_plan(**case["query_target"])
    outcome = classify_yahoo_serp_capture(plan.target, FIXTURES / case["metadata"])

    assert outcome.outcome is None
    assert [unquote(candidate.url) for candidate in outcome.candidates] == [
        "https://tw.stock.yahoo.com/news/"
        "公告-頎邦民國113年度合併財務報告業經董事會決議-063850033.html"
    ]
    _, _, body = _raw("builder_fy_other_wording")
    titles = [result.title for result in parse_yahoo_serp(body)]
    assert any("民國113年第3季合併財務報告" in title for title in titles)
