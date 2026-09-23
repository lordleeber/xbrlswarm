# Step-23 驗收 — Worker API

五個 HTTP 端點均有 request/response regression tests；`/lease` 可派發
既有 `undone` task，`/result` 僅讓 lease owner 回報成功，錯誤與重複回報
不會改寫 task。`/stats` 與 `/status` 呈現基本計數，`/healthz` 不依賴 DB。

此步不新增 migration，也不宣稱完成 Step-24 的正式多 worker 原子性驗收、
Step-25 過期回收或後續來源失敗狀態機。服務預設只綁 loopback，公開部署需
額外的驗證及傳輸安全。
