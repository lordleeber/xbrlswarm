import json
from pathlib import Path

import pytest

from xbrlswarm.discovery.matrix import FieldStatus, load_matrix, render_markdown


def test_repository_matrix_is_valid_and_keeps_confirmed_at_unverified() -> None:
    records = load_matrix(Path("discovery/source_field_matrix.json"))
    confirmed = next(record for record in records if record.field == "xbrl_confirmed_at")
    assert confirmed.status is FieldStatus.NOT_VERIFIED


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
