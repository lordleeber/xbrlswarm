# Step-27 — 可重試的基礎設施失敗

`rate_limited`、`transport_error`、`temporary_error` 表示目前 engine 的請求
因基礎設施條件失敗，不能推論來源沒有可信答案，也不能因此切換 engine。
Worker 透過 `POST /result` 回報其中一種 outcome 時，API 只接受目前、未逾期的
lease；在同一交易內將 task state 設為該 outcome、清除 lease 欄位、
使 `fail_count` 加一，並設定 UTC 毫秒精度的 `retry_at`。`engine` 保持不變，
`attempts` 在回報時不變。重複或過期回報返回 `409 lease_not_current`，
不會再次增加 `fail_count`。

預設等待 60 秒；伺服器啟動時可用 `--retry-delay-seconds` 指定正整數秒數。
等待從接受結果的時間開始。`POST /lease` 在 SQLite `BEGIN IMMEDIATE` 交易內
回收 `retry_at <= now` 的三種待重試狀態，使其成為 `undone`，清除 `retry_at`，
再按 task ID 派發。到期前不會重新派發，也不阻擋其他可派任務；不需要背景排程器。
新 lease 會使 `attempts` 遞增，舊結果因此不能命中新 lease。
`fail_count` 保留累計基礎設施失敗次數，成功或語意耗盡不重設它。

`migrations/0008_add_retry_at.sql` 為既有 STRICT task 表新增 nullable `retry_at`。
既有任務的值為 NULL，不改變任務資料或原有約束。時間窗由資料庫持久保存，
伺服器重啟後仍可按期限回收。共用資料庫的伺服器應使用一致的等待設定與
同步的時鐘。機器可讀契約見 `contracts/retryable-failures.json`。
