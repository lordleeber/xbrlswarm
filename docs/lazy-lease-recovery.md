# Step-25 — 延遲回收 lease

Worker API 預設租約期限為 300 秒，可用 `--lease-timeout-seconds` 設定正整數秒數。
`dispatched_at` 是租約起點，以 UTC 毫秒時間儲存；當目前時間達到
`dispatched_at + timeout` 時，租約逾期。共用同一 SQLite 資料庫的伺服器實例
應使用相同期限設定，且主機時鐘應同步。

每次 `POST /lease` 在 `BEGIN IMMEDIATE` 交易內，先把所有逾期的
`dispatched` task 回復為 `undone`，清除 `worker_id`、`dispatched_at`，更新
`updated_at`，再依 task ID 派發。回收不重設 `attempts`；新派發使它遞增，
因此舊結果即使由同一 worker 提交也會因 `lease_attempt` 不符而被拒絕。
回收與派發一起提交；任一步驟失敗則一起 rollback。沒有背景排程器，
逾期 task 會在下一次 lease 請求時回收。

`POST /result` 也檢查租約尚未逾期；在期限邊界或之後回傳
`409 lease_not_current`，即使尚無其他 worker 觸發回收也一樣。租約不可續期；
執行時間可能超過期限的 worker 須使用足夠長的 timeout。已完成的 task
不再回收。本 Step 不新增 migration。
