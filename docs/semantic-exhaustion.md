# Step-26 — 語意耗盡

`not_found` 與 `rejected` 表示**目前 engine 已嘗試，但沒有可信答案**。
`not_found` 指本次搜尋未找到符合任務且可採信的結果；`rejected` 指取得的候選結果
經檢查後都無法採信。這兩者只描述本次 engine 嘗試，不代表財報不存在，
也不代表其他來源沒有答案。Worker 只有完成當次來源搜尋與必要檢查後才應回報。

Worker 透過 `POST /result` 回報其中一種 outcome，並帶回目前的 `task_id`、
`worker_id`、`lease_attempt`。API 僅接受仍有效、未逾期的 lease，原子地將
`task.state` 設為對應的 `not_found` 或 `rejected`，清除 lease 欄位並更新
`updated_at`。`task.engine`、`attempts`、`fail_count` 不變。重複回報、舊 lease、
錯誤 worker 或逾期結果回 `409 lease_not_current`。`success` 仍轉成 `completed`。

這兩種狀態允許後續流程轉到下一個 engine，但 Step-26 不決定來源順序，
因此不直接更改 `task.engine`，也不自動重新派發同一 engine。Step-28 將定義
來源順序與轉移；Step-27 將定義留在同一 engine 的基礎設施錯誤。
不新增 migration：既有 `task.state` 欄位可保存這兩個狀態。
機器可讀契約見 `contracts/semantic-exhaustion.json`。
