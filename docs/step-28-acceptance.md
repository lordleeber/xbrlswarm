# Step-28 驗收 — 固定 engine 順序

`not_found`、`rejected` 在下一次 lease 請求依序從 MOPS 轉至 Goodinfo、
Yahoo、Google、Grounded AI。最後一層耗盡時進入 `terminal_unresolved`，
不再派發。轉移與派發在同一交易內，保留任務識別、`attempts` 與
`fail_count`；舊 generation 不得完成新 lease。基礎設施失敗與成功狀態
不能觸發來源轉移。完整 pytest suite 通過。
