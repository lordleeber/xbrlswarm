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
| `POST /lease` | JSON `{"worker_id":"worker-1"}` | `200` 與含 `lease_attempt` 的 `task`，無可派任務時 `204` |
| `POST /result` | JSON `{"task_id":1,"worker_id":"worker-1","lease_attempt":1,"outcome":"success"}`；outcome 也可為 `not_found`、`rejected` | 持有未逾期 lease 時 `200`，否則 `409` |
| `GET /stats` | 無 | JSON `total`、`by_state`、`by_engine` |
| `GET /status` | 無 | 人類可讀的總數及 `undone`、`dispatched`、`completed`、`not_found`、`rejected` 計數 |
| `GET /healthz` | 無 | `{"status":"ok"}`，只代表 HTTP server 存活 |

`/lease` 在交易內選取最早的 `undone` task，更新成 `dispatched`，記錄
`worker_id`、`dispatched_at`，並遞增 `attempts`。回傳的 `lease_attempt` 是本次
lease 的 generation，等於更新後的 `attempts`；回報結果時必須原樣帶回。
只回傳 task identity、engine 與 lease metadata，
不讓 worker 直接改寫 task。`/result` 接受 `success`，將 task 改成 `completed`；
Step-26 也接受 `not_found`、`rejected`，將 task 改成同名語意耗盡狀態。
三者都要求該 worker 持有有效且 generation 相同的 `dispatched` task，並清除 lease 欄位；
重複回報、錯誤 worker、逾期租約或舊 generation 回 `409`，不會改寫 task。
Step-25 在每次 `/lease` 請求內回收逾期 task，預設 300 秒，可用
`--lease-timeout-seconds` 調整；回收保留 `attempts`，再次派發會遞增它。
即使同一 worker 重取同一 task，舊結果也不得完成新 lease。這是任務執行控制狀態，**不是**已驗證的
來源證據或 XBRL 確認時間；目前沒有 evidence 上傳 API。

無效 JSON、欄位、method 分別回 `400`、`405`；`405` 附 `Allow` header。
不存在的路徑回 `404`。
`/healthz` 不查資料庫，不能拿來宣稱 DB、外部來源或 worker 健康。

Step-24 已以條件式更新及並行測試正式驗證多 worker 原子 lease 契約，詳見
`docs/atomic-task-lease.md`；Step-25 回收語意詳見 `docs/lazy-lease-recovery.md`。
Step-26 語意耗盡詳見 `docs/semantic-exhaustion.md`。基礎設施失敗分類、換 engine、完整 stats／status
指標與 evidence ingestion 留待後續 Steps，不能將目前的 `success` 擴充解讀為
完成來源稽核。
