from pathlib import Path

from xbrlswarm.discovery.cli import main


def test_list_cases_prints_all_twelve_cases(capsys) -> None:
    assert main(["list-cases"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 12
    assert "2330\t台積電\t2024\tQ1" in lines
    assert "4542\t科嶠\t2024\tFY" in lines


def test_render_matrix_writes_document(tmp_path: Path) -> None:
    output = tmp_path / "matrix.md"
    assert main(["render-matrix", "--output", str(output)]) == 0
    assert output.exists()
    text = output.read_text(encoding="utf-8")
    assert "MOPS 來源欄位可取得性矩陣" in text
    assert "xbrl_confirmed_at" in text
