# Step-16 — 不得捏造 XBRL 確認時間

`xbrl_confirmed_at` 僅能表示來源明確提供、可稽核的 XBRL 確認事件時間。
目前公開歷史來源仍為 **NOT PUBLICLY VERIFIED**；MOPS download fixtures
未提供此事件時間，不表示事件不存在或所有公開來源皆不可得。

以下時間不能改名或推導成 `xbrl_confirmed_at`：

| 已知時間 | 實際語意 | 保存位置 |
| --- | --- | --- |
| `announcement_at` | 重大訊息發言事件 | `material_announcement` evidence 的 `event_date`／`event_time` |
| `article_published_at` | 文章或鏡像內容發布 | 其來源自己的事件語意；不能當作申報確認 |
| `retrieved_at` | 本系統擷取來源的時間 | evidence 擷取 metadata |
| `http_date` | HTTP `Date` 回應標頭時間 | HTTP response metadata |
| `http_last_modified` | HTTP `Last-Modified` 回應標頭時間 | HTTP response metadata |

即使這些時間與某筆文件事件的時間值相同，也不能從相等性推論為 XBRL 確認時間。
`xbrl_document` 的存在或其 `event_date`／`event_time` 亦不自動證明確認事件。
擷取器、匯出器及未來 schema 變更不得以 rename、fallback、coalesce 或其他推導方式
產生 `xbrl_confirmed_at`。

目前 production schema 不含此欄，來源矩陣維持 `not_verified`。
若未來有新來源，需先滿足 `docs/historical-xbrl-confirmed-at.md` 的公開、歷史、
可重播、可批次查詢與原始證據要求，再更新 source matrix、來源解析規則與測試。
本 Step 不定義事件時間精度；該規則由 Step-17 處理。
