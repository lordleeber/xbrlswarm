from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any


class FieldStatus(StrEnum):
    DIRECT = "direct"
    DERIVED = "derived"
    OPTIONAL = "optional"
    NOT_AVAILABLE = "not_available"
    NOT_VERIFIED = "not_verified"


@dataclass(frozen=True, slots=True)
class FieldRecord:
    field: str
    status: FieldStatus
    evidence: tuple[str, ...]
    notes: str


def load_matrix(path: Path) -> tuple[FieldRecord, ...]:
    raw: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("fields"), list):
        raise ValueError("matrix 必須是包含 fields 陣列的物件")

    records: list[FieldRecord] = []
    names: set[str] = set()
    for item in raw["fields"]:
        if not isinstance(item, dict):
            raise ValueError("matrix 的每個欄位都必須是物件")
        name = str(item.get("field", "")).strip()
        if not name:
            raise ValueError("matrix 欄位名稱不得為空白")
        if name in names:
            raise ValueError(f"重複的 matrix 欄位：{name}")
        names.add(name)
        try:
            status = FieldStatus(str(item["status"]))
        except (KeyError, ValueError) as exc:
            raise ValueError(f"欄位 {name} 的狀態無效") from exc
        evidence_raw = item.get("evidence", [])
        if not isinstance(evidence_raw, list) or not all(isinstance(x, str) for x in evidence_raw):
            raise ValueError(f"欄位 {name} 的 evidence 必須是字串陣列")
        records.append(
            FieldRecord(
                field=name,
                status=status,
                evidence=tuple(evidence_raw),
                notes=str(item.get("notes", "")),
            )
        )

    confirmed = next((record for record in records if record.field == "xbrl_confirmed_at"), None)
    if confirmed is None:
        raise ValueError("matrix 必須包含 xbrl_confirmed_at")
    if confirmed.status is not FieldStatus.NOT_VERIFIED:
        raise ValueError(
            "歷史 xbrl_confirmed_at 必須維持 not_verified，直到已有公開、具歷史資料、可重播、"
            "可批次查詢的證據被記錄為止"
        )
    return tuple(records)


def render_markdown(records: tuple[FieldRecord, ...]) -> str:
    lines = [
        "# MOPS 來源欄位可取得性矩陣",
        "",
        "此矩陣刻意採保守策略。只有在實際擷取的原始來源與決定性規則能支持某個狀態時，欄位才能離開 `not_verified`。",
        "",
        "允許的狀態：`direct`、`derived`、`optional`、`not_available`、`not_verified`。",
        "",
        "| 欄位 | 狀態 | 證據 | 備註 |",
        "| --- | --- | --- | --- |",
    ]
    for record in records:
        evidence = "<br>".join(record.evidence) if record.evidence else "—"
        notes = record.notes.replace("|", "\\|") or "—"
        lines.append(f"| `{record.field}` | `{record.status.value}` | {evidence} | {notes} |")
    lines.extend(
        [
            "",
            "## 歷史 `xbrl_confirmed_at`",
            "",
            "`historical xbrl_confirmed_at = NOT PUBLICLY VERIFIED`",
            "",
            "不得由公告時間、文章時間、爬蟲擷取時間或 HTTP metadata 推導。",
            "",
        ]
    )
    return "\n".join(lines)
