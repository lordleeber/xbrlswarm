"""Step-39 source-specific locator construction from Goodinfo URL identity."""

import json
from pathlib import Path
from urllib.parse import quote, urlencode

import pytest

from xbrlswarm.goodinfo_locator import goodinfo_announcement_locator


def _url(*, stock: str = "2330", time: str = "2024/05/10 14:48:53",
         subject: str = "公告本公司113年第1季合併財務報告",
         path: str = "/tw/StockAnnounceDetail.asp", reverse: bool = False) -> str:
    params = [("STOCK_ID", stock), ("CLAIM_TIME", time), ("SUBJECT", subject)]
    if reverse:
        params.reverse()
    encoded = urlencode(params, quote_via=quote) if reverse else urlencode(params)
    return "https://goodinfo.tw" + path + "?" + encoded


def test_path_order_encoding_and_observed_year_rendering_share_locator() -> None:
    original = _url()
    variant = _url(
        subject="公告本公司 ２０２４年第1季合併財務報告",
        path="/tw2/StockAnnounceDetail.asp", reverse=True,
    ) + "&PAGE=2"
    assert goodinfo_announcement_locator(original) == goodinfo_announcement_locator(variant)
    assert goodinfo_announcement_locator(original).startswith(
        "goodinfo:announcement:STOCK_ID=2330&CLAIM_TIME=2024%2F05%2F10+14%3A48%3A53&SUBJECT="
    )


@pytest.mark.parametrize("changes", [
    {"stock": "2317"},
    {"time": "2024/05/10 14:48:54"},
    {"subject": "公告本公司113年第2季合併財務報告"},
])
def test_identity_component_change_changes_locator(changes: dict) -> None:
    assert goodinfo_announcement_locator(_url()) != goodinfo_announcement_locator(_url(**changes))


def test_invalid_or_repeated_identity_parameter_is_rejected() -> None:
    with pytest.raises(ValueError):
        goodinfo_announcement_locator(_url().replace("goodinfo.tw", "other.example"))
    with pytest.raises(ValueError):
        goodinfo_announcement_locator(_url() + "&STOCK_ID=2330")


def test_contract_preserves_payload_and_subject_as_identity_dimensions() -> None:
    contract = json.loads(Path("contracts/goodinfo-idempotency.json").read_text())
    assert contract["identity_fields"] == ["STOCK_ID", "CLAIM_TIME", "SUBJECT"]
    assert "raw_payload_hash" in contract["evidence_identity_comparison_fields"]
    assert "source_subject" in contract["evidence_identity_comparison_fields"]
    assert contract["new_capture_requires_raw_payload_hash"] is True
    assert contract["missing_locator_policy"] == "never_infer_from_source_url"
