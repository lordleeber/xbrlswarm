# MOPS 來源欄位可取得性矩陣

此矩陣刻意採保守策略。只有在實際擷取的原始來源與決定性規則能支持某個狀態時，欄位才能離開 `not_verified`。

允許的狀態：`direct`、`derived`、`optional`、`not_available`、`not_verified`。

| 欄位 | 狀態 | 證據 | 備註 |
| --- | --- | --- | --- |
| `stock_id` | `direct` | discovery/mops_field_observations.json：12/12 captures 的 tifrs-notes:CompanyID | iXBRL fact 直接提供公司代號，且逐筆與 capture case 一致。 |
| `company_name` | `direct` | discovery/mops_field_observations.json：12/12 captures 的 tifrs-notes:CompanyChineseName | iXBRL fact 直接提供公司中文法定全名；不等同案例使用的簡稱。 |
| `fiscal_year` | `direct` | discovery/mops_field_observations.json：12/12 captures 的 tifrs-notes:Year | iXBRL fact 直接提供西元會計年度，且逐筆與 capture case 一致。 |
| `report_period` | `derived` | discovery/mops_field_observations.json：12/12 captures 的 tifrs-notes:Quarter 與 period_rule | 決定性映射為 1→Q1、2→Q2、3→Q3、4→FY；4 是 MOPS request / fact 值，領域模型仍維持 FY != Q4。 |
| `report_scope` | `direct` | discovery/mops_field_observations.json：12/12 captures 的 tifrs-notes:ReportCategory=Consolidated report | 來源直接表示本組 fixtures 為合併報告；本組未擷取個體報告，因此不能據此判定兩種 scope 是否同時存在。 |
| `filing_identifier` | `not_available` | discovery/mops_field_observations.json：Step-3 對 12 個 payload 的語意欄位盤點 | 本次 XBRL download endpoint 與 payload 未提供可辨識為穩定 filing identifier 的欄位。 |
| `filing_date` | `not_available` | discovery/mops_field_observations.json：Step-3 cautions 與 not_observed | payload 中的 DateAndProceduresOfAuthorisationForIssueOfFinancialStatements 是董事會核准／通過發布日期，不是申報日期；retrieved_at 亦不得替代。 |
| `filing_time` | `not_available` | discovery/mops_field_observations.json：Step-3 cautions 與 not_observed | 本次 endpoint 未提供申報時間；不得用董事會日期、retrieved_at 或 HTTP metadata 代替。 |
| `xbrl_confirmed_at` | `not_verified` | discovery/mops_field_observations.json：12 個 payload 均未觀察到 confirmation timestamp<br>docs/historical-xbrl-confirmed-at.md：公開歷史來源契約 | 本 endpoint 不提供 confirmation timestamp；但單一 endpoint 的缺失不足以證明所有公開歷史來源皆不可得，因此維持 NOT PUBLICLY VERIFIED。 |
| `filing_kind` | `not_available` | discovery/mops_field_observations.json：12/12 captures 僅有 tifrs-notes:ReportType=Financial report (general) | ReportType 不足以區分 original / amendment / correction / supplemental。 |
| `source_locator` | `derived` | discovery/mops_field_observations.json：12/12 request URLs<br>src/xbrlswarm/discovery/mops.py：build_mops_xbrl_capture 的決定性 query rule | 可由官方 endpoint 加上 functionName、step、co_id、year、season、report_id 決定性重建；它是 source locator，不是 filing identifier。 |

## 歷史 `xbrl_confirmed_at`

`historical xbrl_confirmed_at = NOT PUBLICLY VERIFIED`

不得由公告時間、文章時間、爬蟲擷取時間或 HTTP metadata 推導。
