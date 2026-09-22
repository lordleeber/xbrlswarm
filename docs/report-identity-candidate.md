# 報告識別候選方案

## 決策

第一版 provisional task identity 採用有順序的 tuple：

```text
(stock_id, fiscal_year, report_period)
```

三個欄位在 Step-3 的來源矩陣中皆為 `direct` 或具有決定性規則的 `derived`。本文件定義的是後續 task 建模的候選 identity；Step-5 不建立資料表、unique constraint 或 production Schema。

機器可讀契約位於 `contracts/report-identity-candidate.json`。

## `report_scope` 決策

`report_scope` 暫時不納入 task identity。

目前 2330、6147、4542 × 2024 Q1/Q2/Q3/FY 的 12 個 fixtures 全部直接觀察到 `consolidated`。研究尚未擷取 `individual`，因此既不能宣稱個體報告不存在，也不能證實同一組 `(stock_id, fiscal_year, report_period)` 會同時存在兩種 scope。

只有下列兩項同時成立，才把候選 identity 擴充為：

```text
(stock_id, fiscal_year, report_period, report_scope)
```

必要條件：

1. 原始來源證據證實同一公司、同一 fiscal year、同一 report period 同時存在 `consolidated` 與 `individual`。
2. 產品範圍決定兩種 scope 都必須分別追蹤。

只觀察到某一筆 `individual`，但未證實與 `consolidated` 在同一期共存，不足以改變 identity。若日後兩項條件成立，必須先更新契約、fixtures、tests 與 schema migration，再讓兩種 scope 進入正式任務；不得把它們靜默合併成同一份報告。

## Identity 邊界

這個 tuple 只定義 task identity，不是：

- 官方 filing identifier
- 可重播請求的 source locator
- 原始／更正／補充申報的 evidence identity

同一 task 可以在後續步驟連結多筆不同來源或不同版本的 evidence。重新抓取是否為同一邏輯證據，應由證據冪等性契約判定，不能只依 task identity 覆蓋舊資料。

本 Step 也不定義 tuple 的字串串接格式。儲存與傳輸時應保留欄位邊界，避免 delimiter 或型別正規化造成碰撞；各欄位的正式值域由後續領域契約與 schema 步驟定義。

## 證據與限制

採用依據：

- `discovery/mops_field_observations.json`：12/12 captures 提供三個候選欄位，並只觀察到 consolidated scope。
- `docs/source-field-matrix.md`：候選欄位皆為 `direct` 或 `derived`，`report_scope` 在現有 captures 為 `direct`。
- `docs/step-3-acceptance.md`：明載未擷取個體報告，不能判定兩種 scope 是否共存。

因此此決策維持 `provisional`。它是目前證據允許的最小候選方案，不是對所有 MOPS 歷史報告形態的完整性宣稱。
