# Step-23 — Worker API

第一版以 Python 標準函式庫 WSGI 提供五個端點，使用已 migration 的 SQLite
`task` 表；不新增 production schema。啟動例：

```bash
xbrlswarm-worker-api --database ./xbrlswarm.sqlite --host 127.0.0.1 --port 8000
```

預設只綁 `127.0.0.1`。本 Step **沒有身分驗證、TLS 或公開網路防護**，不得直接
對外暴露；若部署到多機，須先加可信反向代理及存取控制。

| 端點 | 請求 | 回應 |
| --- | --- | --- |
| `POST /lease` | JSON `{"worker_id":"worker-1"}` | `200` 與 `task`，無可派任務時 `204` |
| `POST /result` | JSON `{"task_id":1,"worker_id":"worker-1","outcome":"success"}` | 持有 lease 時 `200`，否則 `409` |
| `GET /stats` | 無 | JSON `total`、`by_state`、`by_engine` |
| `GET /status` | 無 | 人類可讀的總數及初步 state 計數 |
| `GET /healthz` | 無 | `{"status":"ok"}`，只代表 HTTP server 存活 |

`/lease` 在交易內選取最早的 `undone` task，更新成 `dispatched`，記錄
`worker_id`、`dispatched_at`，並遞增 `attempts`。只回傳 task identity 和 engine，
不讓 worker 直接改寫 task。`/result` 第一版只接受 `success`，把該 worker
持有的 `dispatched` task 改成 `completed`，清除 lease 欄位；重複回報或錯誤
worker 回 `409`，不會再改寫 task。這是任務執行控制狀態，**不是**已驗證的
來源證據或 XBRL 確認時間；目前沒有 evidence 上傳 API。

無效 JSON、欄位、method 分別回 `400`、`405`；不存在的路徑回 `404`。
`/healthz` 不查資料庫，不能拿來宣稱 DB、外部來源或 worker 健康。

本 Step 的基礎交易避免一般重複派發，但 Step-24 將正式定義並驗證多 worker
原子 lease 契約；Step-25 處理過期 lease。失敗分類、換 engine、完整 stats／status
指標與 evidence ingestion 留待後續 Steps，不能將目前的 `success` 擴充解讀為
完成來源稽核。
