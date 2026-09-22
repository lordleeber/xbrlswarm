# Step-5 驗收 — 定義報告識別候選方案

## 範圍

Step-5 依階段 0 已保存的來源證據，定義 provisional task identity：

```text
(stock_id, fiscal_year, report_period)
```

同時記錄 `report_scope` 尚不納入 identity 的證據界線，以及未來擴充成四欄位 identity 的必要條件。本 Step 不建立 production Schema、task table 或 database constraint。

## RED

先新增 repository contract tests，要求：

- identity 必須精確包含 `stock_id`、`fiscal_year`、`report_period`，並保留欄位順序。
- 三個候選欄位在來源矩陣中只能是 `direct` 或 `derived`。
- `report_scope` 必須因 scope coexistence 尚未驗證而排除，不得宣稱個體報告不存在。
- 擴充 identity 必須同時要求「同一期兩種 scope 共存」與「兩種 scope 都要追蹤」。
- 契約引用的 evidence artifacts 必須存在。
- 文件必須區分 task、filing、locator 與 evidence identity。

測試先因機器可讀契約與決策文件尚未存在而失敗。

## GREEN

新增：

```text
contracts/report-identity-candidate.json
docs/report-identity-candidate.md
```

JSON 保存可由測試及後續 schema 步驟直接檢查的決策；Markdown 解釋證據、限制、identity 邊界與 migration gate。

## 決策結果

目前只觀察到：

```text
12 / 12 captures = consolidated
individual captures = 0
same-report scope coexistence = not verified
```

所以採用最小三欄位候選 identity。這不代表 `report_scope` 不重要或 `individual` 不存在；只代表現有 evidence 不支持提前把它加入 task identity。

若未來證實同一期兩種 scope 共存，而且兩者都納入追蹤範圍，必須在建立相關正式任務前將 identity 改成：

```text
(stock_id, fiscal_year, report_period, report_scope)
```

## 不包含

本 Step 不：

- 建立 production Schema 或 task table
- 定義 database unique constraint
- 定義 `report_period` 的完整正規化規則（Step-6）
- 定義 evidence types（Step-7）
- 將 task identity 當成 filing identifier、source locator 或 evidence identity

本 Step 只有契約 artifact、文件與測試，正式程式碼增量為 0 行，低於 800 行，因此不需要拆分。
