# Step-24 驗收 — 原子化 lease

## RED

先新增並行回歸測試與契約測試：獨立連線的兩個 Worker 不能取得同一個
`undone` task；派發時的 `worker_id`、`dispatched_at`、`updated_at`、`attempts`
須一起更新，失敗時一起回滾。正式契約與文件在新增前不存在。

## GREEN

以 `BEGIN IMMEDIATE` 加單一條件式 `UPDATE … RETURNING` 實作派發，
並用多 worker 測試驗證唯一派發；不需要 migration。
逾期回收仍留給 Step-25，不能在這一步猜測 timeout 或增加背景排程器。
