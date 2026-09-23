# Step-20 — 歷史發布規則版本

每條候選規則都必須有 `valid_from`、`valid_to`、`rule_id` 與可追溯的
`source_ref`，並明確限定 `report_period`、`company_class`、`fiscal_calendar`。
`valid_from` 與 `valid_to` 是**含首尾**的生效區間；`valid_to=NULL` 只表示
從 `valid_from` 起開放到未來，不表示對所有過去年份都有效。

`VersionedPublicationRuleProvider` 依明確注入的
`effective_date_for_query(query)` 選取版本。選版日期不能在本 Step 偷偷假定為
期末、申報日或發布日；真實規則必須根據可稽核法規來源決定生效日期語意。
相同適用範圍若有重疊版本、或任兩條規則重用 `rule_id`，建構 provider 時就拒絕。
`rule_id` 在同一 provider 內必須全域唯一，即使兩條規則的期別、公司類別或年度曆不同；
否則 Step-19 只輸出的 `rule_id` 無法唯一追溯被選中的版本。
沒有符合區間的規則時回傳 `None`，Step-19 介面因此回報
`PublicationRuleUnavailable`；絕不把最新版本套到整個歷史。

規則的 `window_for(query)` 只提供日期對，最終的 `rule_id` 由被選中的版本產生，
避免計算器自行宣稱另一條規則。測試使用 `TEST-ONLY-NOT-LAW` 的虛構日期與
明確的測試用選版函式，**不是任何實際法規或法定期限**。
目前 repository 不內建真實規則、法規日期或其生效日映射；後續加入時必須保存
原始法規來源、適用範圍與歷史版本證據，再以 regression tests 驗證。
