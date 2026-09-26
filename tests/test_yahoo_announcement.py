"""Step-46 MOPS-form Yahoo announcement mirrors: parsing, identity and preference."""

from __future__ import annotations

import gzip
import json
from datetime import date
from pathlib import Path

import pytest

from xbrlswarm.domain import ReportPeriod, RetryableFailure, SemanticExhaustion
from xbrlswarm.yahoo_announcement import (
    NotMopsForm,
    YahooArticleLayoutError,
    parse_yahoo_announcement,
    review_yahoo_article,
    review_yahoo_article_capture,
    select_yahoo_announcements,
    verify_yahoo_announcement,
)
from xbrlswarm.yahoo_search import (
    ReportScope,
    YahooTarget,
    classify_yahoo_serp_capture,
    yahoo_search_plan,
)


FIXTURES = Path(__file__).parent / "fixtures" / "yahoo"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
CASES = {case["scenario"]: case for case in MANIFEST["cases"]}
CONTRACT = json.loads(
    (Path(__file__).parents[1] / "contracts" / "yahoo-mops-form-mirror.json").read_text(
        encoding="utf-8"
    )
)
FY_TARGET = YahooTarget("8119", "公信", 2024, ReportPeriod.FY, ReportScope.CONSOLIDATED)
MOPS_FORM_CASES = [
    "valid_result", "wrong_year", "wrong_quarter", "wrong_company", "wrong_scope",
    "article_other_wording", "article_q3_other_wording",
]


def _raw(scenario: str) -> tuple[str, bytes]:
    case = CASES[scenario]
    metadata = json.loads((FIXTURES / case["metadata"]).read_text(encoding="utf-8"))
    return metadata["request"]["url"], gzip.decompress((FIXTURES / case["body"]).read_bytes())


def _target(identity: dict) -> YahooTarget:
    scope = identity["report_scope"]
    return YahooTarget(
        identity["stock_id"], identity["company"], identity["fiscal_year"],
        identity["report_period"], scope if scope in {"consolidated", "individual"} else None,
    )


URL = "https://tw.stock.yahoo.com/news/%E5%85%AC%E5%91%8A-x-012345678.html"


def _page(*lines: str, body_wrapper: bool = True) -> bytes:
    paragraphs = "".join(f"<p class=\"mb-module-gap\">{line}</p>" for line in lines)
    body = f'<div class="atoms" data-component="blocks">{paragraphs}</div>' if body_wrapper else paragraphs
    return (
        "<html><head><title>t</title></head><body><article>"
        f"<h1>【公告】測試</h1>{body}</article></body></html>"
    ).encode("utf-8")


HEADER = (
    "日　　期：2025年03月12日",
    "公司名稱：公信 (8119)",
    "主　　旨：公信董事會通過113年度合併財務報告",
    "發言人：李立群",
    "說　　明：",
)
PERIOD = "3.財務報告報導期間起訖日期(XXX/XX/XX~XXX/XX/XX):113/01/01~113/12/31"


# --- parser -------------------------------------------------------------------------


def test_valid_mirror_exposes_the_mops_form_fields() -> None:
    url, body = _raw("valid_result")
    announcement = parse_yahoo_announcement(body, url=url)

    assert announcement.url == url
    assert announcement.headline == "【公告】公信董事會通過113年度合併財務報告"
    assert (announcement.stock_id, announcement.company) == ("8119", "公信")
    assert announcement.subject == "公信董事會通過113年度合併財務報告"
    assert announcement.announcement_date == date(2025, 3, 12)
    assert (announcement.period_start, announcement.period_end) == (
        date(2024, 1, 1), date(2024, 12, 31)
    )


@pytest.mark.parametrize("scenario", MOPS_FORM_CASES)
def test_every_live_mops_form_mirror_parses_to_its_observed_identity(scenario) -> None:
    url, body = _raw(scenario)
    identity = CASES[scenario]["observed_identity"]
    announcement = parse_yahoo_announcement(body, url=url)

    assert announcement.stock_id == identity["stock_id"]
    assert announcement.company == identity["company"]
    assert announcement.period_end.year == identity["fiscal_year"]
    assert "財務報告" in announcement.subject


def test_quarter_mirror_reports_the_cumulative_period() -> None:
    url, body = _raw("wrong_quarter")
    announcement = parse_yahoo_announcement(body, url=url)
    assert (announcement.period_start, announcement.period_end) == (
        date(2024, 1, 1), date(2024, 6, 30)
    )


@pytest.mark.parametrize("scenario", ["wrong_company", "article_other_wording"])
def test_period_label_split_over_two_lines_is_read(scenario) -> None:
    url, body = _raw(scenario)
    announcement = parse_yahoo_announcement(body, url=url)
    assert announcement.period_end == date(announcement.period_end.year, 12, 31)


def test_news_article_without_header_fields_is_not_mops_form() -> None:
    url, body = _raw("article_not_mops_form")
    with pytest.raises(NotMopsForm) as error:
        parse_yahoo_announcement(body, url=url)
    assert set(error.value.missing) == {"公司代號", "公司名稱", "主旨"}


def test_old_template_without_report_period_is_not_mops_form() -> None:
    url, body = _raw("article_without_report_period")
    with pytest.raises(NotMopsForm) as error:
        parse_yahoo_announcement(body, url=url)
    # The body's own 「2.公司名稱:公信電子股份有限公司」 is not a header field.
    assert error.value.missing == ("財務報告期間",)


def test_page_without_article_body_is_a_layout_error() -> None:
    url, body = _raw("unexpected_page")
    with pytest.raises(YahooArticleLayoutError):
        parse_yahoo_announcement(body, url=url)


def test_fields_outside_the_article_body_are_ignored() -> None:
    """The meta description and related-news cards repeat 公司名稱／主旨 of other pages."""

    url, body = _raw("valid_result")
    text = body.decode("utf-8")
    start = text.index('<div class="atoms"')
    end = text.index("</p>", text.index("3.財務報告報導期間", start)) + len("</p>")
    stripped = (text[:start] + text[end:]).encode("utf-8")
    assert "公司名稱：" in stripped.decode("utf-8")
    with pytest.raises(YahooArticleLayoutError):
        parse_yahoo_announcement(stripped, url=url)


def test_fullwidth_tilde_and_individual_synonym_are_normalized() -> None:
    body = _page(
        *HEADER[:2], "主　　旨：公信董事會通過113年度個別財務報告", *HEADER[3:],
        "3.財務報告報導期間起訖日期(XXX/XX/XX～XXX/XX/XX):113/01/01～113/12/31",
    )
    announcement = parse_yahoo_announcement(body, url=URL)
    assert announcement.period_end == date(2024, 12, 31)
    target = YahooTarget("8119", "公信", 2024, ReportPeriod.FY, ReportScope.INDIVIDUAL)
    assert verify_yahoo_announcement(announcement, target) == ()


@pytest.mark.parametrize("lines,match", [
    ((*HEADER[:2], "公司名稱：公信 (9999)", *HEADER[2:], PERIOD), "公司名稱"),
    ((*HEADER, PERIOD, "9.財務報告報導期間起訖日期:113/01/01~113/06/30"), "報導期間"),
    ((*HEADER, "3.財務報告報導期間起訖日期:113/13/01~113/12/31"), "報導期間"),
    ((*HEADER, "3.財務報告報導期間起訖日期:113/12/31~113/01/01"), "報導期間"),
    (("日　　期：2025年02月30日", *HEADER[1:], PERIOD), "日期"),
])
def test_conflicting_or_invalid_fields_are_layout_errors(lines, match) -> None:
    with pytest.raises(YahooArticleLayoutError, match=match):
        parse_yahoo_announcement(_page(*lines), url=URL)


def test_header_fields_after_the_explanation_do_not_count() -> None:
    body = _page(
        HEADER[0], "說　　明：", "公司名稱：公信 (8119)",
        "主　　旨：公信董事會通過113年度合併財務報告", PERIOD,
    )
    with pytest.raises(NotMopsForm) as error:
        parse_yahoo_announcement(body, url=URL)
    assert set(error.value.missing) == {"公司代號", "公司名稱", "主旨"}


# --- identity -----------------------------------------------------------------------


@pytest.mark.parametrize("scenario", ["valid_result", "wrong_year", "wrong_quarter",
                                      "wrong_company", "wrong_scope"])
def test_step_44_single_dimension_mismatches_are_named(scenario) -> None:
    url, body = _raw(scenario)
    announcement = parse_yahoo_announcement(body, url=url)
    identity = CASES[scenario]["observed_identity"]
    expected = {
        field for field in MANIFEST["target_task"]
        if identity[field] != MANIFEST["target_task"][field]
    }
    assert set(verify_yahoo_announcement(announcement, FY_TARGET)) == expected


def test_other_wording_mirror_matches_its_own_target() -> None:
    url, body = _raw("article_other_wording")
    announcement = parse_yahoo_announcement(body, url=url)
    target = _target(CASES["article_other_wording"]["observed_identity"])
    assert verify_yahoo_announcement(announcement, target) == ()


def test_scope_is_unchecked_only_when_the_target_leaves_it_open() -> None:
    url, body = _raw("wrong_scope")
    announcement = parse_yahoo_announcement(body, url=url)
    open_scope = YahooTarget("8119", "公信", 2024, ReportPeriod.FY, None)
    assert verify_yahoo_announcement(announcement, open_scope) == ()

    unscoped = parse_yahoo_announcement(
        _page(*HEADER[:2], "主　　旨：公信董事會通過113年度財務報告", *HEADER[3:], PERIOD),
        url=URL,
    )
    assert verify_yahoo_announcement(unscoped, FY_TARGET) == ("report_scope",)
    assert verify_yahoo_announcement(unscoped, open_scope) == ()


def test_company_name_must_agree_even_when_the_code_does() -> None:
    url, body = _raw("valid_result")
    announcement = parse_yahoo_announcement(body, url=url)
    target = YahooTarget("8119", "公信電子", 2024, ReportPeriod.FY, ReportScope.CONSOLIDATED)
    assert verify_yahoo_announcement(announcement, target) == ("company",)


@pytest.mark.parametrize("period_line,expected", [
    ("3.財務報告報導期間起訖日期:113/04/01~113/06/30", ()),
    ("3.財務報告報導期間起訖日期:113/01/01~113/06/30", ()),
    ("3.財務報告報導期間起訖日期:113/02/01~113/06/30", ("report_period",)),
    ("3.財務報告報導期間起訖日期:112/07/01~113/06/30", ("report_period",)),
    ("3.財務報告報導期間起訖日期:113/01/01~113/09/30", ("report_period",)),
])
def test_quarter_period_start_must_be_january_or_quarter_start(period_line, expected) -> None:
    body = _page(
        *HEADER[:2], "主　　旨：公信董事會通過113年第二季合併財務報告", *HEADER[3:],
        period_line,
    )
    announcement = parse_yahoo_announcement(body, url=URL)
    target = YahooTarget("8119", "公信", 2024, ReportPeriod.Q2, ReportScope.CONSOLIDATED)
    assert verify_yahoo_announcement(announcement, target) == expected


def test_subject_must_be_a_financial_report() -> None:
    body = _page(*HEADER[:2], "主　　旨：公信董事會通過113年度合併盈餘分配", *HEADER[3:], PERIOD)
    announcement = parse_yahoo_announcement(body, url=URL)
    assert verify_yahoo_announcement(announcement, FY_TARGET) == ("financial_report_subject",)


# --- article review and preference --------------------------------------------------


def _review(scenario: str, target: YahooTarget = FY_TARGET, status: int = 200):
    url, body = _raw(scenario)
    return review_yahoo_article(target, url=url, final_url=url, status=status, body=body)


def test_review_outcomes_for_live_articles() -> None:
    assert _review("valid_result").outcome == "accepted"
    assert _review("article_not_mops_form").outcome == "not_mops_form"
    assert _review("article_without_report_period").outcome == "not_mops_form"
    review = _review("wrong_year")
    assert (review.outcome, review.mismatches) == ("identity_mismatch", ("fiscal_year",))
    # A news URL answering with a page that has no article body is a layout problem.
    _, quote_body = _raw("unexpected_page")
    review = review_yahoo_article(FY_TARGET, url=URL, final_url=URL, status=200, body=quote_body)
    assert review.outcome is RetryableFailure.TEMPORARY_ERROR
    assert _review("unexpected_page").outcome == "not_article_page"  # /quote/ URL


@pytest.mark.parametrize("status,expected", [
    (404, "article_unavailable"),
    (410, "article_unavailable"),
    (429, RetryableFailure.RATE_LIMITED),
    (500, RetryableFailure.TEMPORARY_ERROR),
    (307, RetryableFailure.TEMPORARY_ERROR),
])
def test_review_status_handling(status, expected) -> None:
    review = review_yahoo_article(FY_TARGET, url=URL, final_url=URL, status=status, body=b"")
    assert review.outcome == expected
    assert review.announcement is None


@pytest.mark.parametrize("final_url", [
    "https://tw.stock.yahoo.com/",
    "https://tw.stock.yahoo.com/quote/8119.TWO",
    "https://example.test/news/x.html",
])
def test_redirect_off_a_news_article_is_not_accepted(final_url) -> None:
    url, body = _raw("valid_result")
    review = review_yahoo_article(FY_TARGET, url=url, final_url=final_url, status=200, body=body)
    assert review.outcome == "not_article_page"


def test_mops_form_mirror_is_preferred_over_an_earlier_non_mops_article() -> None:
    target_2020 = _target(CASES["article_not_mops_form"]["observed_identity"])
    news = _review("article_not_mops_form", target_2020)
    selection = select_yahoo_announcements((news, _review("valid_result")))
    assert selection.outcome is None
    assert [item.url for item in selection.accepted] == [_raw("valid_result")[0]]


def test_only_non_mops_or_mismatched_articles_are_rejected() -> None:
    selection = select_yahoo_announcements((
        _review("article_not_mops_form"), _review("wrong_year"), _review("wrong_scope"),
    ))
    assert selection.outcome is SemanticExhaustion.REJECTED
    assert selection.accepted == ()
    assert [review.outcome for review in selection.reviews] == [
        "not_mops_form", "identity_mismatch", "identity_mismatch",
    ]


def test_unfinished_reviews_block_rejection_but_not_acceptance() -> None:
    limited = review_yahoo_article(FY_TARGET, url=URL, final_url=URL, status=429, body=b"")
    failed = review_yahoo_article(FY_TARGET, url=URL, final_url=URL, status=500, body=b"")
    assert select_yahoo_announcements((_review("wrong_year"), failed)).outcome is (
        RetryableFailure.TEMPORARY_ERROR
    )
    assert select_yahoo_announcements((failed, limited)).outcome is RetryableFailure.RATE_LIMITED
    selection = select_yahoo_announcements((failed, _review("valid_result")))
    assert selection.outcome is None and len(selection.accepted) == 1


def test_selection_needs_at_least_one_review() -> None:
    with pytest.raises(ValueError):
        select_yahoo_announcements(())


# --- captures and the Step-45 → Step-46 chain ---------------------------------------


@pytest.mark.parametrize("serp,article", [
    ("builder_fy_consolidated", "valid_result"),
    ("builder_fy_other_wording", "article_other_wording"),
    ("builder_q3_other_wording", "article_q3_other_wording"),
])
def test_serp_candidate_leads_to_an_accepted_mirror(serp, article) -> None:
    plan = yahoo_search_plan(**CASES[serp]["query_target"])
    search = classify_yahoo_serp_capture(plan.target, FIXTURES / CASES[serp]["metadata"])
    [candidate] = search.candidates
    review = review_yahoo_article_capture(plan.target, FIXTURES / CASES[article]["metadata"])

    assert review.url == candidate.url
    assert review.outcome == "accepted"
    assert select_yahoo_announcements((review,)).accepted == (review.announcement,)


def test_capture_with_mismatched_hash_or_foreign_host_is_refused(tmp_path) -> None:
    source = FIXTURES / CASES["valid_result"]["metadata"]
    metadata = json.loads(source.read_text(encoding="utf-8"))
    (tmp_path / metadata["response"]["body_file"]).write_bytes(gzip.compress(b"tampered"))
    (tmp_path / source.name).write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="sha256"):
        review_yahoo_article_capture(FY_TARGET, tmp_path / source.name)

    metadata["request"]["url"] = "https://example.test/news/x.html"
    (tmp_path / source.name).write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="request url"):
        review_yahoo_article_capture(FY_TARGET, tmp_path / source.name)


def test_contract_matches_behaviour() -> None:
    assert CONTRACT["contract"] == "yahoo_mops_form_mirror"
    assert set(CONTRACT["required_fields"]) == {"公司代號", "公司名稱", "主旨", "財務報告期間"}
    assert CONTRACT["identity_checks"] == [
        "stock_id", "company", "fiscal_year", "report_period", "report_scope",
        "financial_report_subject",
    ]
    assert CONTRACT["non_mops_form_articles_accepted"] is False
    assert CONTRACT["writes_evidence"] is False
    assert CONTRACT["article_published_at_is_announcement_at"] is False
    assert CONTRACT["article_outcomes"]["http_404_or_410"] == _review(
        "valid_result", status=404
    ).outcome
    assert CONTRACT["article_outcomes"]["http_200_missing_required_field"] == _review(
        "article_not_mops_form"
    ).outcome
    assert not hasattr(parse_yahoo_announcement(_raw("valid_result")[1], url=URL),
                       "article_published_at")
