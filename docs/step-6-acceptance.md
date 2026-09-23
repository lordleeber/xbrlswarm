# Step-6 驗收 — 定義報告期別

## 範圍

Step-6 將內部 report period 定版為：

```text
Q1
Q2
Q3
FY
```

並以 fixture 鎖定已由 MOPS captures 證實的 `Q4 → FY` 來源正規化。本 Step 不建立 production Schema、task table 或發布時間窗規則。

## RED

先新增 `tests/fixtures/domain/report-period-normalization.json` 與測試，要求：

- 正式 domain enum 只能有 Q1、Q2、Q3、FY。
- discovery 與 domain 必須共用同一個 `ReportPeriod` class，不得各自維護 enum。
- 通用 domain parser 必須拒絕 Q4。
- MOPS source adapter 必須將 `4` 與 `Q4` 映射為 FY。
- 未驗證的 MOPS aliases 必須失敗。
- normalization fixture 必須與 repository observation artifact 的規則及逐筆結果一致。

測試先因 `xbrlswarm.domain` 與 MOPS period adapter 尚未存在而在 collection 階段失敗。

## GREEN

新增：

```text
src/xbrlswarm/domain/report_period.py
src/xbrlswarm/discovery/mops_period.py
tests/fixtures/domain/report-period-normalization.json
```

並將 discovery models 與 MOPS analysis 改為共用正式 domain enum。現有 discovery import path 仍回傳相同 class，以保留相容性。

MOPS analysis 不再維護自己的 quarter mapping，而是呼叫 source adapter；決定性產生的 `discovery/mops_field_observations.json` 內容維持不變。

## 語意界線

- FY 是年度報告，不是第四季報告。
- Q4 只能作為已驗證來源的外部表示，不能進入內部 enum。
- 正規化後仍須保存來源原始值，不得只剩 FY 而失去來源追溯。
- MOPS 規則不得自動套用到其他來源。
- fiscal calendar 與發布時間窗由後續步驟處理。

## 800 行拆分規則

本 Step 的正式程式碼遠低於 800 行，不需要拆成 Step-6-a / Step-6-b。
