# Step-13 驗收 — 加入重複資料防護

## 範圍

Step-13 以 `migrations/0005_add_evidence_deduplication.sql` 建立與 Step-12 contract 一致的
MOPS／Goodinfo partial unique indexes。已解析 identity 可用 `ON CONFLICT DO NOTHING`
進行冪等寫入；`unresolved` evidence 不自動折疊。

## RED

先新增 regression tests，要求：

- `crawl once → 1 logical evidence`、`crawl twice → still 1 logical evidence`。
- 即使 retrieval／描述／驗證 metadata 不同，相同 identity 仍不重複新增。
- 沒有 conflict handling 的直接重複 insert 由 database constraint 拒絕。
- MOPS 新 payload、Goodinfo 新公告或 payload、不同 source 都保留為新 evidence。
- Goodinfo 沒有 raw payload hash 時仍能依 locator + CLAIM_TIME + SUBJECT 去重。
- Profile 必要欄位缺失或 source 尚無 profile 時保持 `unresolved`，不自動折疊。
- Migration 保留既有 evidence；若已有重複資料則整體 rollback，不留下部分 index。

測試先因 migration、unique indexes、asymmetric optional NULL 契約與文件尚未實作而失敗。

## GREEN

Migration 先執行 source-specific duplicate preflight，再以同一 projection 建立兩個 partial
unique indexes。Nullable comparison fields 使用與 TEXT 值不衝突的 BLOB sentinel，使兩次
相同的 NULL event／payload metadata 能命中同一 index。

同步將 Step-12 contract 升為 version 2：profile comparison field 單邊缺值為 `unresolved`，
讓 `same` 保持可安全實作的等價關係。

## 不包含

- 不新增 revision kind 或分類 amendment。
- 不修改、合併或刪除既有 evidence。
- 不為 unresolved identity 建立推測性 deduplication。
- 不實作 Worker 或完整 database repository。
