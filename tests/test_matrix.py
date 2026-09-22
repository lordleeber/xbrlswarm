import json
from pathlib import Path

import pytest

from xbrlswarm.discovery.matrix import FieldStatus, load_matrix, render_markdown


def test_repository_matrix_is_valid_and_keeps_confirmed_at_unverified() -> None:
    records = load_matrix(Path("discovery/source_field_matrix.json"))
    statuses = {record.field: record.status for record in records}

    assert statuses["stock_id"] is FieldStatus.DIRECT
    assert statuses["company_name"] is FieldStatus.DIRECT
    assert statuses["fiscal_year"] is FieldStatus.DIRECT
    assert statuses["report_period"] is FieldStatus.DERIVED
    assert statuses["report_scope"] is FieldStatus.DIRECT
    assert statuses["filing_identifier"] is FieldStatus.NOT_VERIFIED
    assert statuses["filing_date"] is FieldStatus.NOT_VERIFIED
    assert statuses["filing_time"] is FieldStatus.NOT_VERIFIED
    assert statuses["filing_kind"] is FieldStatus.NOT_VERIFIED
    assert statuses["source_locator"] is FieldStatus.DERIVED
    confirmed = next(record for record in records if record.field == "xbrl_confirmed_at")
    assert confirmed.status is FieldStatus.NOT_VERIFIED

    for record in records:
        assert record.evidence


def test_matrix_rejects_premature_confirmed_at_claim(tmp_path: Path) -> None:
    path = tmp_path / "matrix.json"
    path.write_text(
        json.dumps(
            {
                "fields": [
                    {
                        "field": "xbrl_confirmed_at",
                        "status": "direct",
                        "evidence": ["some-url"],
                        "notes": "unproven",
                    }
                ]
            }
        )
    )
    with pytest.raises(ValueError, match="歷史 xbrl_confirmed_at"):
        load_matrix(path)


def test_rendered_matrix_contains_contract_statement() -> None:
    records = load_matrix(Path("discovery/source_field_matrix.json"))
    markdown = render_markdown(records)
    assert "historical xbrl_confirmed_at = NOT PUBLICLY VERIFIED" in markdown
    assert "`not_verified`" in markdown
    assert markdown == Path("docs/source-field-matrix.md").read_text(encoding="utf-8")
