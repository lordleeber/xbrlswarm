# Step-27 驗收 — 可重試的基礎設施失敗

三種結果 `rate_limited`、`transport_error`、`temporary_error` 都保留目前
engine，不會當作 Step-26 的語意耗盡。有效回報只增加一次 `fail_count`，
結束租約並寫入 `retry_at`；逾期或重複回報不改寫任務。`/lease` 在期限前
不派發，到期後重新派發同一 engine，並使 lease generation 遞增。
其他可派任務不受等待中的任務阻擋。Migration 保留既有 task 及 STRICT typing。
