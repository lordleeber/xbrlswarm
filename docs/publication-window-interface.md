# Step-19 — 發布時間窗規則介面

`expected_publication_window(fiscal_year, report_period, company_class,
fiscal_calendar, *, rule_provider=...)` 接受四個業務輸入，回傳
`PublicationWindow(earliest_date, latest_date, rule_id)`。日期是 `datetime.date`，
`earliest_date <= latest_date`，且 `rule_id` 必須非空，讓結果可追溯到提供者的規則。

本 Step **只建立介面，不內建任何法定天數、發布日期或歷史規則**。
規則由明確注入的 `PublicationWindowRuleProvider.resolve(query)` 提供；未注入或
找不到符合條件的規則時，拋出 `PublicationRuleUnavailable`，不得拿 Step-18 的
期末日期加固定天數、拿現行規則回推歷史，或默認為某個發布窗口。

第一版只接受已確認的 `fiscal_calendar="calendar_year"`，其他年度曆會拒絕，
待 Step-21 來源研究完成再擴充。`company_class` 目前只要求非空，不預設分類
或法規適用範圍。`report_period` 沿用 Q1／Q2／Q3／FY，Q4 不接受。

測試中的 `TEST-ONLY-NOT-LAW` 與日期只是模擬 provider 回傳資料，**不代表法規**。
真實 provider 必須先有可稽核來源與適用範圍；Step-20 再定義
`valid_from`、`valid_to`、`rule_id` 的歷史版本契約。
此介面不變更 evidence schema，也不會把預期時間窗當作來源已發生的發布事件。
