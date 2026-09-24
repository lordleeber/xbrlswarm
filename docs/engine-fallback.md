# Step-28 — 固定 engine 順序

固定來源順序為 `mops → goodinfo → yahoo → google → grounded_ai`，由
`xbrlswarm.domain.next_engine()` 表達。`not_found` 與 `rejected` 只表示目前
engine 沒有可信答案，具備未來轉到下一來源的資格。

Step-33 已通過限定範圍的 MOPS gate（稽核見 `docs/step-33-acceptance.md`）。
MOPS task 由有效 lease 回報 `not_found` 或 `rejected` 後，下一次 `POST /lease`
在同一個 `BEGIN IMMEDIATE` 交易內改為 `state=undone, engine=goodinfo`，
再選取並派發任務。轉移保留 `attempts`、`fail_count` 與既有 evidence；若派發
失敗，轉移一併回滾。即使指定其他 `task_id`，轉移也會發生，該 MOPS task
之後仍可被定向 lease。其他跨來源轉移仍關閉，須待其來源 gate 驗收。

Gate 僅涵蓋已驗證的 MOPS 合併 XBRL 下載路徑。個體 XBRL、修訂分類、申報
時間及 XBRL 確認時間仍未驗證；對未知版面或變更的 payload 回報可重試的
`temporary_error`，不得把它們當成 `not_found` 以觸發備援。Goodinfo 查詢與
解析由後續 Step-34 起實作；目前 Worker API 只提供任務狀態轉移與租約。

若已有 `grounded_ai` task 回報語意耗盡，下一次 `/lease` 會在
`BEGIN IMMEDIATE` 交易內把它設為 `terminal_unresolved`，不再派發，
也不捏造來源證據或確認時間。`/status` 會顯示此狀態的數量；
`engine`、`attempts`、`fail_count` 保持不變。

`rate_limited`、`transport_error`、`temporary_error` 仍依 Step-27 的
`retry_at` 等待，回到同一 engine；`completed` 任務不會轉移。
本 Step 不新增 migration，沿用 task 的既有 `state`、`engine` 欄位。
機器可讀契約見 `contracts/engine-fallback.json`。
