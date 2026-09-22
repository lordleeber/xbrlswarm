# Step-3 驗收 — 建立欄位可取得性矩陣

## 範圍

Step-3 對 Step-2 保存的 12 組官方 MOPS iXBRL captures 進行離線、可重播的欄位分析，並以分析結果更新來源欄位矩陣。本 Step 不建立 production Schema 或通用財報解析器。

固定證據集：

```text
2330 台積電 × 2024 Q1/Q2/Q3/FY
6147 頎邦   × 2024 Q1/Q2/Q3/FY
4542 科嶠   × 2024 Q1/Q2/Q3/FY
```

## RED

先新增測試定義：

- 12 組 captures 必須全部產生欄位 observations
- 每個 observation 必須來自已通過 Step-2 完整性驗證的 raw body
- 必要 fact 缺失、空白或同名 fact 值互相衝突時必須失敗
- `CompanyID`、`Year`、`Quarter` 必須與 capture case 一致
- `Quarter=4` 必須決定性映射為 `FY`，不得改寫成領域期別 `Q4`
- 未知 `ReportCategory` 不得自行猜測 scope
- observation artifact 必須可決定性重建
- matrix 必須保留歷史 `xbrl_confirmed_at = not_verified`

## GREEN

新增：

```text
src/xbrlswarm/discovery/mops_analysis.py
discovery/mops_field_observations.json
```

CLI：

```bash
python -m xbrlswarm.discovery analyze-mops-captures
python -m xbrlswarm.discovery render-matrix
```

分析器從每個 iXBRL payload 讀取：

```text
tifrs-notes:CompanyID
tifrs-notes:CompanyChineseName
tifrs-notes:Year
tifrs-notes:Quarter
tifrs-notes:ReportType
tifrs-notes:ReportCategory
```

每筆 observation 同時保存來源 URL 與 raw body SHA-256，使矩陣結論能回溯到確切 fixture。

分析器另彙整全部 494 個不同的 iXBRL fact names，篩出與 filing、submission、confirmation、amendment、correction、supplement、authorisation 與 report type 相關的名稱供語意審查。候選只有：

```text
tifrs-notes:ApplicationOfNewlyIssuedOrAmendedStandardsAndInterpretations
tifrs-notes:DateAndProceduresOfAuthorisationForIssueOfFinancialStatements
tifrs-notes:ReportType
```

第一項是會計準則修訂揭露，第二項是董事會核准／通過發布敘述，第三項在本組資料皆為 `Financial report (general)`；三者均不提供 filing identifier、filing timestamp、confirmation timestamp 或版本種類。

## 欄位結論

| 欄位 | 狀態 | 結論 |
| --- | --- | --- |
| `stock_id` | `direct` | 12/12 由 `CompanyID` 直接提供 |
| `company_name` | `direct` | 12/12 由 `CompanyChineseName` 直接提供法定全名 |
| `fiscal_year` | `direct` | 12/12 由 `Year` 直接提供 |
| `report_period` | `derived` | `Quarter` 以 1→Q1、2→Q2、3→Q3、4→FY 映射 |
| `report_scope` | `direct` | 12/12 的 `ReportCategory` 為 `Consolidated report` |
| `filing_identifier` | `not_verified` | 本 endpoint / payload 未觀察到；不能外推整體 MOPS 來源不可得 |
| `filing_date` | `not_verified` | 本 endpoint 未觀察到；官方系統已知存在申報日期，且董事會核准日期不是申報日期 |
| `filing_time` | `not_verified` | 本 endpoint 未觀察到；官方系統已知存在申報時間 |
| `xbrl_confirmed_at` | `not_verified` | 本 endpoint 未提供，但不能外推成所有公開來源皆不可得 |
| `filing_kind` | `not_verified` | 本 endpoint 的 `Financial report (general)` 無法區分原始、更正或補充申報；其他 MOPS 來源尚未驗證 |
| `source_locator` | `derived` | 可由官方 endpoint 與固定 query rule 決定性重建 |

## 保守界線

- `DateAndProceduresOfAuthorisationForIssueOfFinancialStatements` 是董事會核准／通過發布的敘述，不是 MOPS filing timestamp。
- `retrieved_at` 與 HTTP headers 是擷取 metadata，不是 filing 或 confirmation timestamp。
- 本證據集只有 `report_id=C` 的合併報告，不能據此判定個體與合併報告是否同時存在。
- `Individual report → individual` 尚無原始 fixture 支持，不列入本 Step 的已驗證 scope rule。
- `source_locator` 是可重播請求位置，不是官方 filing identifier。
- 單一 endpoint 沒有 `xbrl_confirmed_at`，不足以證明所有公開歷史來源皆不存在該欄位。

## 不包含

本 Step 不：

- 定義 production Schema
- 實作 production MOPS parser 或 Worker
- 解析財務數值
- 擷取個體報告或研究 scope 共存
- 建立 amendment / correction / supplemental 的辨識規則
- 推導或捏造 filing / confirmation timestamp

## 800 行拆分規則

本 Step 的正式程式碼增量為：

```text
src/xbrlswarm/discovery/mops_analysis.py  +218
src/xbrlswarm/discovery/cli.py             +23
------------------------------------------------
total                                    +241
```

其餘增量為測試、決定性產生的 evidence artifact 與文件；正式程式碼低於 800 行，因此不需要拆成 Step-3-a / Step-3-b。
