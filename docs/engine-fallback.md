# Step-28 — 固定 engine 順序

任務使用固定順序：`mops → goodinfo → yahoo → google → grounded_ai`。
`not_found` 與 `rejected` 只表示目前 engine 沒有可信答案；下一次 `POST /lease`
會在 SQLite `BEGIN IMMEDIATE` 交易內將這些 task 轉至下一個 engine、設回
`undone`，再依 task ID 派發。轉移與派發一起提交，並行 worker 不會取得
同一個新 lease。結果回報當下仍保留語意耗盡狀態，供查詢與稽核。

如果 `grounded_ai` 也回報語意耗盡，下一次 `/lease` 會把 task 設為
`terminal_unresolved`，不再派發，且不捏造來源證據或確認時間。
`/status` 會顯示此狀態的數量。`engine` 保持 `grounded_ai`，`attempts`、
`fail_count` 不因 engine 轉移而重設。再次派發仍遞增 `attempts`，
因此前一個 engine 的舊結果不能完成新 lease。

`rate_limited`、`transport_error`、`temporary_error` 仍依 Step-27 的
`retry_at` 等待，回到同一 engine；`completed` 任務不會轉移。
本 Step 不新增 migration，沿用 task 的既有 `state`、`engine` 欄位。
機器可讀契約見 `contracts/engine-fallback.json`。
