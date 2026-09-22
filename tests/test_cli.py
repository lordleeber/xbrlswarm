from pathlib import Path
from types import SimpleNamespace

import xbrlswarm.discovery.cli as cli
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


def test_capture_mops_cases_command_uses_fixed_batch_capture(monkeypatch, tmp_path: Path, capsys) -> None:
    called: dict[str, object] = {}

    def fake_capture(output_root: Path, *, overwrite: bool = False):
        called["output_root"] = output_root
        called["overwrite"] = overwrite
        return (
            SimpleNamespace(body_path=output_root / "2330/2024/Q1/xbrl-consolidated.bin"),
            SimpleNamespace(body_path=output_root / "2330/2024/Q2/xbrl-consolidated.bin"),
        )

    monkeypatch.setattr(cli, "capture_mops_discovery_cases", fake_capture)

    assert main(
        [
            "capture-mops-cases",
            "--output-root",
            str(tmp_path),
            "--overwrite",
        ]
    ) == 0

    assert called == {"output_root": tmp_path, "overwrite": True}
    output = capsys.readouterr().out
    assert "已擷取 2 個固定案例" in output


def test_verify_mops_captures_command_reports_verified_count(monkeypatch, tmp_path: Path, capsys) -> None:
    called: dict[str, object] = {}

    def fake_verify(output_root: Path):
        called["output_root"] = output_root
        return (object(), object(), object())

    monkeypatch.setattr(cli, "verify_mops_capture_set", fake_verify)

    assert main(["verify-mops-captures", "--output-root", str(tmp_path)]) == 0
    assert called == {"output_root": tmp_path}
    assert "已驗證 3 個固定案例" in capsys.readouterr().out


def test_analyze_mops_captures_command_writes_evidence(monkeypatch, tmp_path: Path, capsys) -> None:
    output = tmp_path / "observations.json"
    monkeypatch.setattr(cli, "analyze_mops_capture_set", lambda root: (object(), object()))
    monkeypatch.setattr(cli, "render_mops_field_observations", lambda items: "{\n}\n")

    assert main(
        [
            "analyze-mops-captures",
            "--output-root",
            str(tmp_path / "fixtures"),
            "--output",
            str(output),
        ]
    ) == 0

    assert output.read_text(encoding="utf-8") == "{\n}\n"
    assert "已分析 2 個固定案例" in capsys.readouterr().out
