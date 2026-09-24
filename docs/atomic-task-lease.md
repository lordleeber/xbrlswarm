# Step-24 — 原子化 lease

`POST /lease` 只派發 `state='undone'` 的 task，依最小 `task.id` 選取。
SQLite `BEGIN IMMEDIATE` 在查詢候選前取得寫入保留鎖；接著單一條件式
`UPDATE … RETURNING` 同時完成 `undone → dispatched` 與欄位寫入。
多個 worker 使用同一資料庫檔、各自開獨立連線時，後來的寫入者必須等待
前一交易完成，然後重新查找仍為 `undone` 的任務。因此兩個 Worker
不得取得同一 task 的同一次 lease。

每次成功派發在同一交易中寫入 `worker_id`、UTC `dispatched_at`、`updated_at`，
並使 `attempts` 遞增一次。回傳的 `lease_attempt` 等於更新後的 `attempts`；
`POST /result` 必須帶回此 generation，才能完成當次 lease。若沒有可派任務，
資料庫不變，HTTP 回 `204`。SQL 更新失敗則整筆交易 rollback，不能留下
半派發的狀態。機器可讀契約見 `contracts/atomic-task-lease.json`。

測試使用多個真正的 SQLite 連線、同步起跑的 worker threads，涵蓋單任務與
多任務競爭、任務唯一性、計數及時間欄位；另以觸發器模擬資料庫寫入失敗，
檢查回滾。這驗證的是共用同一 SQLite 檔案的交易語意，不宣稱跨互不共享的
資料庫副本可維持同一租約。

Step-25 才實作逾期回收；回收不得重設 `attempts`，以免舊結果的
`lease_attempt` 命中新租約。本 Step 不新增 migration，也不處理失敗分類、
重試排程或來源證據的驗證。
