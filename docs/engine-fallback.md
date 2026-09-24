# Step-28 — 固定 engine 順序

固定來源順序為 `mops → goodinfo → yahoo → google → grounded_ai`，由
`xbrlswarm.domain.next_engine()` 表達。`not_found` 與 `rejected` 只表示目前
engine 沒有可信答案，具備未來轉到下一來源的資格。

目前跨來源 fallback **尚未啟用**。ROADMAP Step-33 要求 MOPS 的來源契約、
fixtures、parser、失敗語意穩定且試點完成稽核後，才可啟用 Goodinfo 備援。
因此在 gate 尚未通過時，下一次 `POST /lease` 仍保留 MOPS 的語意耗盡狀態，
不會把 task 派給 Goodinfo。其他跨來源轉移也先保留原 engine；未來啟用時
須依各來源的 worker 與驗收進度加入明確 gate。固定順序本身不等於啟用權限。

若已有 `grounded_ai` task 回報語意耗盡，下一次 `/lease` 會在
`BEGIN IMMEDIATE` 交易內把它設為 `terminal_unresolved`，不再派發，
也不捏造來源證據或確認時間。`/status` 會顯示此狀態的數量；
`engine`、`attempts`、`fail_count` 保持不變。

`rate_limited`、`transport_error`、`temporary_error` 仍依 Step-27 的
`retry_at` 等待，回到同一 engine；`completed` 任務不會轉移。
本 Step 不新增 migration，沿用 task 的既有 `state`、`engine` 欄位。
機器可讀契約見 `contracts/engine-fallback.json`。
