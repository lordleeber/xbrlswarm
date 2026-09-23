# Task 資料表

## Schema

Step-8 以 SQLite migration `migrations/0001_create_task.sql` 建立 `task` 資料表。欄位如下：

| 欄位 | SQLite 型別 | 必填 | 語意 |
| --- | --- | --- | --- |
| `id` | INTEGER | 是 | SQLite row identifier／primary key |
| `stock_id` | TEXT | 是 | 股票代號；使用文字以保留前導零 |
| `fiscal_year` | INTEGER | 是 | 財務年度 |
| `report_period` | TEXT | 是 | `Q1`、`Q2`、`Q3`、`FY` 之一 |
| `state` | TEXT | 是 | 任務狀態；正式狀態機由後續步驟定義 |
| `engine` | TEXT | 是 | 執行來源；正式 enum 由 Step-9 定義 |
| `attempts` | INTEGER | 是 | 嘗試次數，預設 0，且不得為負數 |
| `fail_count` | INTEGER | 是 | 失敗次數，預設 0，且不得為負數 |
| `dispatched_at` | TEXT | 否 | 最近一次派發時間；尚未 lease 時為空 |
| `worker_id` | TEXT | 否 | 持有 lease 的 worker；尚未 lease 時為空 |
| `created_at` | TEXT | 是 | 建立時間，預設為 UTC RFC 3339 字串 |
| `updated_at` | TEXT | 是 | 最後更新時間，預設為 UTC RFC 3339 字串 |

`updated_at` 的初始值由資料庫產生；後續修改 task 的程式必須在同一交易內更新它。本 Step 不提前建立 Step-24 的 lease transition 或 trigger。

## Identity constraint

Step-5 的 provisional task identity：

```text
(stock_id, fiscal_year, report_period)
```

在資料表上以 unique constraint 保護，避免同一邏輯 task 被重複建立。`stock_id` 明確使用 `TEXT`，因此 `0050` 不會被正規化成數字 `50`。

`report_scope` 不在資料表中，因為現有研究尚未證實同一期 consolidated／individual scope 共存。若 Step-5 所列的兩項擴充條件日後同時成立，必須先新增 migration 並更新 identity contract，不得直接改寫既有 identity。

## 本 Step 的邊界

- `report_period` 沿用 Step-6 的正式值域，拒絕 `Q4`。
- `state` 與 `engine` 在此只要求為非空文字。Step-9 才定義 engine enum；任務狀態與 transition 由後續步驟定義。
- `dispatched_at` 與 `worker_id` 允許空值。本 Step 尚未實作 lease。
- 本 Step 不建立 evidence table、worker API、重試流程或狀態轉移。
