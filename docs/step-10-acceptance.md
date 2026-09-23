# Step-10 驗收 — 建立 evidence 資料表

## 範圍

Step-10 新增 SQLite `STRICT` evidence table，只建立 ROADMAP 列出且已證實可取得或由系統產生的欄位。只有系統能保證產生的核心 metadata 為必填，其餘來源聲稱保持可缺。`filing_kind` 因 source matrix 仍是 `not_verified` 而不進入 Schema，留待 Step-14 以新 migration 加入。

## RED

先新增 SQLite contract tests，要求：

- evidence table 包含 ROADMAP Step-10 中通過 Step-3 schema gate 的 15 個欄位。
- table 必須使用 `STRICT` typing。
- `evidence_type` 值域必須與 Step-7 domain enum 一致。
- `task_id` 必須宣告 `ON DELETE RESTRICT` 外鍵，且在 SQLite foreign keys 啟用時禁止 orphan evidence 與刪除仍有 evidence 的 task。
- event、部分 source metadata 與 raw payload hash 必須允許缺值。
- source matrix 中的 `not_verified` 欄位，包含 `filing_kind`，不得進入 production schema。
- task engine、evidence type、source type 與 verification state 必須保持不同維度。
- Step-12 之前不得猜測 logical evidence unique key。
- schema 不得加入 `xbrl_confirmed_at` 或 generic `published_at`。
- migration 不得改寫既有 task。

測試先因 `evidence` table 與 `migrations/0003_create_evidence.sql` 尚未存在而失敗。

## GREEN

新增：

```text
migrations/0003_create_evidence.sql
docs/evidence-schema.md
```

Migration 只用一個 atomic `CREATE TABLE` statement 建立 evidence table，不需要重建 task，也不會對既有 task 造成部分更改。

## 不包含

本 Step 不：

- 建立 Step-11 parsed metadata
- 定義 Step-12 logical evidence identity 或去重約束
- 定義 Step-14 filing kind enum
- 定義 Step-17 event precision enum
- 定義 Step-54 verification state enum
- 實作 evidence repository 或 worker result flow
