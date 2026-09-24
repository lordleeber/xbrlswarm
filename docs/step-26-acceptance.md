# Step-26 驗收 — 語意耗盡

`not_found` 與 `rejected` 是目前 engine 沒有可信答案的結果，會結束目前
有效 lease，保留 engine 並記錄對應 task state。舊 lease、逾期 lease、
錯誤 worker 及重複結果不能改寫 task。基礎設施錯誤尚不接受為語意耗盡。
本 Step 不新增 migration，也不決定下一個 engine 的順序。
