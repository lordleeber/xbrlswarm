# Step-30 驗收 — MOPS 已驗證欄位解析器

`src/xbrlswarm/mops_parser.py` 提供 `parse_mops_report(case, body, source_url=...)`。
它只接受 Step-2／Step-29 已驗證的 `FileDownLoad` 合併 XBRL URL，並重用
Step-3 的 iXBRL fact 擷取和欄位檢查。輸出為固定欄位的 `ParsedMopsReport`：

| 輸出欄位 | 依據 |
| --- | --- |
| `stock_id`、`company_name`、`fiscal_year` | `CompanyID`、`CompanyChineseName`、`Year` 原始 fact |
| `report_period` | `Quarter` 的 1→Q1、2→Q2、3→Q3、4→FY 已驗證映射 |
| `report_scope` | 僅 `ReportCategory=Consolidated report` 的已驗證映射 |
| `source_locator` | 已驗證 `FileDownLoad` endpoint 與固定 query rule |

解析器要求公司代號、年度及期別與請求 case 一致；缺少、衝突或未知的 fact
會失敗；`ReportType` 也限於已觀察的 `Financial report (general)`。URL 必須
與合併報告的決定性請求位置完全一致。更正清單／明細、
PDF 附件、個體報告錯誤頁與「查無資料」頁均不能被當作合併 XBRL。

`filing_identifier`、`filing_date`、`filing_time`、`xbrl_confirmed_at`、
`filing_kind` 仍為來源矩陣的 `not_verified`，不進入 parser 輸出。來源的
`ReportType=Financial report (general)` 也不產生 revision kind。
本 Step 不保存 evidence 或原始快照；原始回應保存屬 Step-31。

Regression tests 覆蓋全部 12 份已驗證合併 XBRL、Step-29 的四季 manifest、
八種非 XBRL 回應、錯誤 URL／scope／身份 fact，並鎖定輸出欄位集合。
