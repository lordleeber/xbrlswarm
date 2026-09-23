# 報告期別契約

## 內部標準值

領域模型只允許：

```text
Q1 / Q2 / Q3 / FY
```

`FY` 表示年度財務報告，`FY != Q4`。`Q4` 不是內部 report period；通用的 `ReportPeriod.parse()` 必須拒絕它，避免把來源標籤誤當成領域語意。

正式 enum 位於 `xbrlswarm.domain.ReportPeriod`。原有的 `xbrlswarm.discovery.models.ReportPeriod` 是同一個 class 的相容匯入，不維護第二份值域。

## MOPS 來源正規化

Step-2 / Step-3 的 MOPS XBRL fixtures 已觀察到 `tifrs-notes:Quarter` 值 1、2、3、4，其中來源的 quarter 4 與 Q4 filename 代表年度財務報告。因此已驗證的來源專用規則是：

```text
MOPS 1 / Q1 → Q1
MOPS 2 / Q2 → Q2
MOPS 3 / Q3 → Q3
MOPS 4 / Q4 → FY
```

也就是 `MOPS Q4 → FY`，而不是在 domain enum 中新增 Q4。

此規則由 `xbrlswarm.discovery.mops_period` 集中管理。`normalize_mops_report_period()` 負責來源值轉入 domain，`mops_quarter_number()` 負責建立 MOPS request 與驗證 filename；兩個方向共用同一份 mapping。轉入函式刻意拒絕 `FY`、`annual` 或其他未經 fixtures 驗證的 MOPS aliases；來源新增表示法時，必須先補 fixture 與測試。

## 原始值與正規值

正規化不得覆蓋來源證據。MOPS observation artifact 同時保存：

```text
facts.tifrs-notes:Quarter = 4
derived.report_period = FY
```

因此稽核者仍能看見來源實際提供的值，並重播正規化結果。測試會把 `tests/fixtures/domain/report-period-normalization.json` 與 `discovery/mops_field_observations.json` 的 `period_rule` 及逐筆 observations 直接比對。

## 邊界

`Q4 → FY` 是 MOPS 已驗證語意，不是所有來源的通用猜測。未來 Goodinfo、Yahoo 或其他來源若使用 Q4，必須由各自的原始證據確認它代表年度報告後，才能建立該來源專用的 normalization rule。

本契約只定義 report period 值域與已驗證的來源映射，不定義 fiscal year-end、發布截止日或非曆年制公司的 fiscal calendar。
