# MOPS 來源欄位可取得性矩陣

此矩陣刻意採保守策略。只有在實際擷取的原始來源與決定性規則能支持某個狀態時，欄位才能離開 `not_verified`。

允許的狀態：`direct`、`derived`、`optional`、`not_available`、`not_verified`。

| 欄位 | 狀態 | 證據 | 備註 |
| --- | --- | --- | --- |
| `stock_id` | `not_verified` | — | 在實際擷取的回應證明此欄位是直接存在，或只是 request context 以前，不得提升狀態。 |
| `company_name` | `not_verified` | — | 等待具代表性的 MOPS fixture。 |
| `fiscal_year` | `not_verified` | — | 可能由來源直接提供，也可能可由 source locator 決定性推導；完成來源探索後才能定版。 |
| `report_period` | `not_verified` | — | 必須區分 Q1/Q2/Q3/FY；沒有經測試的來源規則時，絕不能推定 FY=Q4。 |
| `report_scope` | `not_verified` | — | 研究同一公司 / 期別是否會同時存在 consolidated 與 individual 報告。 |
| `filing_identifier` | `not_verified` | — | 研究是否存在穩定的公開 filing identifier 或 locator。 |
| `filing_date` | `not_verified` | — | 不得用 announcement date 或 retrieval date 代替。 |
| `filing_time` | `not_verified` | — | 不得用 announcement time、article time 或 HTTP metadata 代替。 |
| `xbrl_confirmed_at` | `not_verified` | — | 公開歷史 confirmation timestamp 仍屬 NOT PUBLICLY VERIFIED。 |
| `filing_kind` | `not_verified` | — | 研究 original / amendment / supplemental filing 的表示方式。 |
| `source_locator` | `not_verified` | — | 研究歷史 filing 是否存在穩定、可重播的 locator。 |

## 歷史 `xbrl_confirmed_at`

`historical xbrl_confirmed_at = NOT PUBLICLY VERIFIED`

不得由公告時間、文章時間、爬蟲擷取時間或 HTTP metadata 推導。
