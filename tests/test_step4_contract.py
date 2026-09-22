import json
from pathlib import Path


HISTORICAL_CONTRACT = Path("docs/historical-xbrl-confirmed-at.md")
STEP4_ACCEPTANCE = Path("docs/step-4-acceptance.md")


def test_historical_confirmed_at_contract_records_the_unresolved_status() -> None:
    contract = HISTORICAL_CONTRACT.read_text(encoding="utf-8")

    assert "historical xbrl_confirmed_at = NOT PUBLICLY VERIFIED" in contract
    assert "公開可存取" in contract
    assert "具有歷史資料" in contract
    assert "可重播" in contract
    assert "可批次查詢" in contract


def test_historical_confirmed_at_contract_rejects_semantic_substitutes() -> None:
    contract = HISTORICAL_CONTRACT.read_text(encoding="utf-8")

    for forbidden_substitute in (
        "announcement_at",
        "文章發布時間",
        "retrieved_at",
        "HTTP `Date`",
        "Last-Modified",
    ):
        assert forbidden_substitute in contract


def test_step4_acceptance_keeps_confirmed_at_out_of_required_schema() -> None:
    acceptance = STEP4_ACCEPTANCE.read_text(encoding="utf-8")
    matrix = json.loads(
        Path("discovery/source_field_matrix.json").read_text(encoding="utf-8")
    )
    confirmed = next(
        record for record in matrix["fields"] if record["field"] == "xbrl_confirmed_at"
    )

    assert confirmed["status"] == "not_verified"
    assert "不得成為正式 Schema 的必填欄位" in acceptance
    assert "不建立 production Schema" in acceptance
    assert "historical xbrl_confirmed_at = NOT PUBLICLY VERIFIED" in acceptance
