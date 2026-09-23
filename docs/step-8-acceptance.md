# Step-8 驗收 — 建立 task 資料表

## 範圍

Step-8 新增第一個 production SQLite migration，建立最小 `task` 資料表。Schema 採用 Step-5 的 provisional task identity 與 Step-6 的正式 report-period 值域，但不提前實作 Step-9 的 engine enum 或後續的任務狀態機。

## RED

先新增 SQLite contract tests，要求：

- task table 精確包含 ROADMAP Step-8 欄位。
- `report_scope` 不得在研究條件尚未成立前進入 schema。
- `(stock_id, fiscal_year, report_period)` 必須唯一。
- `stock_id` 必須保存為文字，不得遺失前導零。
- `report_period` 接受 `Q1 / Q2 / Q3 / FY` 並拒絕 `Q4`。
- `attempts` 與 `fail_count` 預設為 0 且不得為負數。
- 新任務的 lease 欄位為空，建立／更新時間有預設值。

測試先因 `migrations/0001_create_task.sql` 尚不存在而失敗。

## GREEN

新增 `migrations/0001_create_task.sql`。Migration 可由 SQLite 直接執行，建立 primary key、task identity unique constraint、report-period check、非負計數器，以及 task／lease metadata 欄位。

## 不包含

本 Step 不：

- 將 `report_scope` 加入 task identity
- 定義 engine enum
- 定義完整 state enum 或 transition
- 實作原子 lease／lease recovery
- 建立 evidence table
- 建立 task repository 或 Worker API
