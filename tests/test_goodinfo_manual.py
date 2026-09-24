"""Step-41 regressions for importing browser-saved Goodinfo pages."""

import json
import os
from datetime import date, datetime, timezone
from urllib.parse import urlencode

import pytest

from xbrlswarm.goodinfo_list import AnnouncementListQuery, capture_announcement_list
from xbrlswarm.goodinfo_manual import (
    import_manual_inbox,
    import_manual_list,
    main as manual_main,
    manual_capture_plan,
)
from xbrlswarm.goodinfo_operations import GoodinfoOperationalClient
from xbrlswarm.goodinfo_pilot import PILOT_CASES, run_goodinfo_pilot


NOW = datetime(2026, 9, 25, tzinfo=timezone.utc)
SAVED_AT = datetime(2026, 9, 25, 1, 2, 3, tzinfo=timezone.utc)


def _detail_url(stock, year, time="14:48:53"):
    return "https://goodinfo.tw/tw/StockAnnounceDetail.asp?" + urlencode({
        "STOCK_ID": stock, "CLAIM_TIME": f"{year}/05/10 {time}",
        "SUBJECT": f"公告本公司{year}年第1季合併財務報告",
    })


def _list_page(stock, year, extra=""):
    href = _detail_url(stock, year).replace("https://goodinfo.tw", "").replace("&", "&amp;")
    return (f'<html><head><meta charset="utf-8"><title>公告一覽</title></head><body>{extra}'
            f'<a href="{href}">公告本公司{year}年第1季合併財務報告</a></body></html>').encode()


def _detail_page(stock, year, time="14:48:53", charset="utf-8"):
    return (f'<html><head><meta charset="{charset}"><title>{stock} 測試公司 公告訊息</title>'
            f"</head><body>發言日期 {year}/05/10 發言時間 {time} "
            f"主旨 公告本公司{year}年第1季合併財務報告 說 明 "
            f"1.財務報告報導期間起訖日期:{year}/01/01~{year}/03/31"
            "</body></html>").encode(charset)


def _no_network(request, **_):
    raise AssertionError(f"manual import must not contact Goodinfo: {request.full_url}")


def _client(root):
    def sleeper(_):
        raise AssertionError("manual import must not wait for a request slot")

    return GoodinfoOperationalClient(root, opener=_no_network, clock=lambda: 1000.0,
        sleeper=sleeper, random_value=lambda: 0, retrieval_clock=lambda: NOW)


def _save(inbox, name, body):
    inbox.mkdir(exist_ok=True)
    path = inbox / name
    path.write_bytes(body)
    os.utime(path, (SAVED_AT.timestamp(), SAVED_AT.timestamp()))
    return path


def _stock_year(case):
    return case.stock_id, case.fiscal_year


def test_plan_asks_for_lists_then_matching_details(tmp_path):
    client = _client(tmp_path / "captures")
    plan = manual_capture_plan(client)
    assert [(item.kind, item.case, item.save_as, item.url) for item in plan] == [
        ("list", case.key, f"list_{case.key}.html", case.query.url) for case in PILOT_CASES
    ]

    first = PILOT_CASES[0]
    _save(tmp_path / "inbox", f"list_{first.key}.html", _list_page(*_stock_year(first)))
    import_manual_inbox(client, tmp_path / "inbox", clock=lambda: NOW)
    plan = manual_capture_plan(client)
    assert (plan[0].kind, plan[0].case, plan[0].save_as, plan[0].url) == (
        "detail", first.key, f"detail_{first.key}_1.html", _detail_url(*_stock_year(first)),
    )
    assert [item.kind for item in plan[1:]] == ["list"] * 4


def test_imported_pages_replay_offline_as_manual_browser_captures(tmp_path):
    root, inbox = tmp_path / "captures", tmp_path / "inbox"
    client = _client(root)
    for case in PILOT_CASES:
        _save(inbox, f"list_{case.key}.html", _list_page(*_stock_year(case)))
        _save(inbox, f"detail_{case.key}_1.html", _detail_page(*_stock_year(case)))

    outcomes = import_manual_inbox(client, inbox, clock=lambda: NOW)
    assert [outcome["status"] for outcome in outcomes] == ["imported"] * 10
    assert manual_capture_plan(client) == []

    metadata = json.loads((root / "4542" / "2024-04-01_2024-06-30.json").read_text())
    assert metadata["capture_method"] == "manual_browser"
    assert metadata["source_file"] == "list_4542-2024-Q1.html"
    assert metadata["retrieved_at"] == "2026-09-25T01:02:03Z"
    assert metadata["retrieved_at_basis"] == "saved_file_mtime"
    assert metadata["imported_at"] == "2026-09-25T00:00:00Z"
    assert metadata["response"]["final_url"] == PILOT_CASES[0].query.url

    report = run_goodinfo_pilot(root, client=client, offline=True)
    assert report["summary"] == {
        "cases": 5, "lists_captured": 5, "access_blocked": 0, "not_captured": 0,
        "details_parsed": 5, "matching_period_details": 5,
    }
    assert all(row["capture_method"] == "manual_browser"
               and row["detail_results"][0]["capture_method"] == "manual_browser"
               for row in report["results"])
    assert not (root / ".goodinfo-request-state.json").exists()

    again = import_manual_inbox(client, inbox, clock=lambda: NOW)
    assert [outcome["status"] for outcome in again] == ["already_imported"] * 10


@pytest.mark.parametrize("body, message", [
    (b"<html><head><title>Just a moment...</title></head></html>", "access challenge"),
    (b"<html><title>Goodinfo</title><body>nothing here</body></html>", "not an announcement list"),
    (b'<!-- saved from url=(0080)https://goodinfo.tw/tw/StockAnnounceList.asp?STOCK_ID=2330'
     b'&START_DT=2024%2F04%2F01&END_DT=2024%2F06%2F30 -->\n' + _list_page("4542", 2024),
     "different Goodinfo page"),
])
def test_rejected_list_pages_are_not_cached(tmp_path, body, message):
    root, inbox = tmp_path / "captures", tmp_path / "inbox"
    client = _client(root)
    _save(inbox, "list_4542-2024-Q1.html", body)
    outcomes = import_manual_inbox(client, inbox, clock=lambda: NOW)
    assert outcomes[0]["status"] == "rejected"
    assert message in outcomes[0]["error"]
    assert client.cached_list(PILOT_CASES[0].query) is None


def test_saved_from_comment_for_same_query_is_accepted(tmp_path):
    query = PILOT_CASES[0].query
    comment = f"<!-- saved from url=(0080){query.url} -->\n".encode()
    path = _save(tmp_path / "inbox", "list.html", comment + _list_page("4542", 2024))
    capture, imported = import_manual_list(_client(tmp_path / "captures"), query, path,
                                           clock=lambda: NOW)
    assert imported and capture.size_bytes == path.stat().st_size


def test_detail_for_a_different_announcement_is_rejected(tmp_path):
    root, inbox = tmp_path / "captures", tmp_path / "inbox"
    client = _client(root)
    case = PILOT_CASES[0]
    _save(inbox, f"list_{case.key}.html", _list_page(*_stock_year(case)))
    _save(inbox, f"detail_{case.key}_1.html", _detail_page(case.stock_id, 2024, time="09:00:00"))
    outcomes = import_manual_inbox(client, inbox, cases=[case], clock=lambda: NOW)
    assert [outcome["status"] for outcome in outcomes] == ["imported", "rejected"]
    assert "speech time disagrees" in outcomes[1]["error"]
    assert not (root / "details").exists() or not list((root / "details").rglob("*.html"))


def test_big5_detail_is_decoded_from_its_meta_charset(tmp_path):
    root, inbox = tmp_path / "captures", tmp_path / "inbox"
    client = _client(root)
    case = PILOT_CASES[1]
    _save(inbox, f"list_{case.key}.html", _list_page(*_stock_year(case)))
    _save(inbox, f"detail_{case.key}_1.html",
          _detail_page(*_stock_year(case), charset="big5"))
    outcomes = import_manual_inbox(client, inbox, cases=[case], clock=lambda: NOW)
    assert [outcome["status"] for outcome in outcomes] == ["imported", "imported"]
    report = run_goodinfo_pilot(root, client=client, cases=[case], offline=True)
    assert report["results"][0]["detail_results"][0]["period_matches_case"] is True


def test_different_bytes_for_existing_capture_are_rejected(tmp_path):
    root, inbox = tmp_path / "captures", tmp_path / "inbox"
    client = _client(root)
    case = PILOT_CASES[0]
    _save(inbox, f"list_{case.key}.html", _list_page(*_stock_year(case)))
    import_manual_inbox(client, inbox, cases=[case], clock=lambda: NOW)
    _save(inbox, f"list_{case.key}.html", _list_page(*_stock_year(case), extra="changed"))
    outcomes = import_manual_inbox(client, inbox, cases=[case], clock=lambda: NOW)
    assert outcomes[0]["status"] == "rejected"
    assert "different capture already exists" in outcomes[0]["error"]


def test_unexpected_inbox_files_are_reported(tmp_path):
    inbox = tmp_path / "inbox"
    _save(inbox, "random.html", b"<html></html>")
    outcomes = import_manual_inbox(_client(tmp_path / "captures"), inbox, clock=lambda: NOW)
    assert outcomes == [{"file": "random.html", "status": "unexpected"}]


def test_extra_metadata_cannot_replace_capture_fields(tmp_path):
    query = AnnouncementListQuery("4542", date(2024, 4, 1), date(2024, 6, 30))

    class Response:
        status = 200
        headers = {"Content-Type": "text/html; charset=utf-8"}
        def __enter__(self): return self
        def __exit__(self, *_): return None
        def read(self): return _list_page("4542", 2024)
        def geturl(self): return query.url

    with pytest.raises(ValueError, match="cannot replace retrieved_at"):
        capture_announcement_list(query, tmp_path, opener=lambda *_, **__: Response(),
                                  clock=lambda: NOW, extra_metadata={"retrieved_at": "x"})
    assert not list(tmp_path.rglob("*.html"))


def test_cli_plan_and_import_exit_codes(tmp_path, capsys):
    root, inbox = tmp_path / "captures", tmp_path / "inbox"
    assert manual_main(["plan", "--output-root", str(root)]) == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [line["save_as"] for line in lines] == [f"list_{c.key}.html" for c in PILOT_CASES]

    _save(inbox, "list_4542-2024-Q1.html", b"<html><title>Just a moment...</title></html>")
    assert manual_main(["import", "--output-root", str(root), "--inbox", str(inbox)]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "rejected"


def test_manual_capture_contract_forbids_automatic_challenge_bypass():
    from pathlib import Path

    contract = json.loads(Path("contracts/goodinfo-manual-capture.json").read_text())
    assert contract["capture_method"] == "manual_browser"
    assert contract["challenge_policy"].startswith("never solve")
    assert contract["retrieved_at_basis"] == "saved_file_mtime"
    assert contract["network_requests"] == 0
    assert contract["evidence_and_task_effect"] == "none"
