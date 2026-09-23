# Step-15 驗收 — 公告發言時間

## RED

先新增 regression tests，驗證明確的發言日期與時間會映射為
`material_announcement` 的 `event_date`／`event_time`，缺任一欄即拒絕建立完整
`announcement_at`；並驗證儲存後仍與 `retrieved_at` 及同時刻的文件事件分開。
測試先因映射函式與契約文件不存在而失敗。

## GREEN

新增 `announcement_event_fields` 與機器可讀契約，明定只接受來源明確聲稱、
屬於同一公告的發言日期與發言時間；不以文章時間、擷取時間或
`xbrl_confirmed_at` 代替。既有 evidence schema 已有 `event_date`、`event_time`
與 `material_announcement`，因此不需要 migration。

來源專屬擷取與 event precision 的正式規則分別留待後續來源 Step 與 Step-17。
