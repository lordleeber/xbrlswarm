# Step-35 驗收 — 保守搜尋時間窗

`goodinfo_search_plan(stock_id, fiscal_year, report_period, company_class,
fiscal_calendar)` 先透過 Step-19／20 的版本化法規 provider 取得發布時間窗，再
建構 Step-34 的 `AnnouncementListQuery`。回傳的 `GoodinfoSearchPlan` 保留
`rule_id`，讓查詢日期能追溯。沒有適用規則時回報
`PublicationRuleUnavailable`，不以固定月份猜測。

內建規則**僅供 2024 會計年度**，且呼叫者須先獨立確認公司適用
`securities_act_article_36_general` 與 `calendar_year`。本模組不從股票代號
推論公司類別、會計年度曆或是否獲展延。規則來源是臺灣證券交易所保存的
[2023-05-10 版《證券交易法》第 36 條](https://twse-regulation.twse.com.tw/TW/law/DAT06.aspx?FLCODE=FL007009&FLDATE=20230510&LSER=001)
（涵蓋 2024 Q1／Q2 期末）及
[2024-08-07 版第 36 條](https://twse-regulation.twse.com.tw/TW/law/DAT07.aspx?FLCODE=FE396664&LDATE=20240807&LSID=FL007009&TY=E)
（涵蓋 Q3／FY 期末）。兩版均規定前三季期末後 45 日內、年度期末後
3 個月內公告申報。版本選擇使用期末日，規則限於 2024 年期末；其他年度
須另提供已驗證的 provider。

搜尋起日採**期末翌日**，是保守查詢政策，並非法規規定的最早公告日。
搜尋迄日採上述一般規則的公告申報期限，含首尾：

| 2024 期別 | Goodinfo `START_DT` | `END_DT` | 規則 ID |
| --- | --- | --- | --- |
| Q1 | 2024/04/01 | 2024/05/15 | `TW-SEA36-2024-Q1` |
| Q2 | 2024/07/01 | 2024/08/14 | `TW-SEA36-2024-Q2` |
| Q3 | 2024/10/01 | 2024/11/14 | `TW-SEA36-2024-Q3` |
| FY | 2025/01/01 | 2025/03/31 | `TW-SEA36-2024-FY` |

這些是**一般規則下按時公告的搜尋區間**，不是個別公司的法定期限判定。
特殊適用範圍、個案核准展延、遲報、更正或晚於期限的公告可能落在區間外；
區間內查不到資料也不能回報財報不存在。對第一／第二上市、金融類、未知
曆年制及其他未證實適用一般規則的公司，不使用內建區間。
`contracts/goodinfo-search-window.json` 保存機器可讀範圍和來源。此 Step
不新增 migration，也不改變 Goodinfo 的 403 即時存取限制。
