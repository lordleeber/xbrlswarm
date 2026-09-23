# Step-20 驗收 — 歷史規則版本化

## RED

先新增 regression tests，要求 `valid_from`／`valid_to`／`rule_id`，
歷史與現行查詢選到不同版本；生效日期邊界含首尾，空窗不回退到現行規則。
也測試重疊版本、重複 ID、缺少來源識別或反轉日期會被拒絕。
測試先因版本化 provider 與契約文件不存在而失敗。

## GREEN

新增 `VersionedPublicationRule` 與 `VersionedPublicationRuleProvider`，
由呼叫端明確注入選版日期語意與來源支援的日期計算器。
本 Step 不提供真實法規日期、不建立 production 資料表，因此不需要 migration。

## Code review regression

機器可讀契約必須記錄 `rule_id` 在同一 provider 內全域唯一；不同適用範圍
也不得重用 ID，與 runtime 檢查及回傳值的可追溯性保持一致。
