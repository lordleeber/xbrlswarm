# Step-25 驗收 — 延遲回收 lease

`POST /lease` 在同一個 `BEGIN IMMEDIATE` 交易中回收逾期租約並重新派發。
期限前不回收，期限邊界開始回收；`attempts` 保留且新租約遞增。
逾期結果在回收前後均被拒絕，包含同一 worker 重新取得任務的情形。
並行 worker 只有一個能取得回收後的任務；派發失敗時回收也 rollback。
完整 pytest suite 通過。使用方式與限制見 `docs/lazy-lease-recovery.md`。
