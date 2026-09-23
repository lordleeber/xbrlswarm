# Step-9 驗收 — 定義 engine 列舉

## 範圍

Step-9 建立共用 `Engine` domain enum、machine-readable contract，並以新的 SQLite migration 將同一值域套用到 `task.engine`。

## RED

先新增測試，要求：

- `Engine` 必須精確包含 `mops`、`goodinfo`、`yahoo`、`google`、`grounded_ai`。
- parser 可正規化大小寫，並拒絕其他值。
- JSON contract 必須與 domain enum 一致。
- `engine` 必須與 evidence `source_type` 維持不同維度。
- migration 後的 `task.engine` 只接受正式值。
- `0002_define_engine_enum.sql` 必須保留既有 task 與 Step-8 的 `STRICT` typing。
- 遇到既有的未知 engine 時，migration 必須自行回滾：不得造成資料遺失、留下暫存 table 或繼續持有 write transaction。

測試先因 `xbrlswarm.domain.Engine` 尚未存在而在 collection 階段失敗。

## GREEN

新增：

```text
src/xbrlswarm/domain/engine.py
contracts/engines.json
migrations/0002_define_engine_enum.sql
docs/engines.md
```

Migration 在單一 transaction 內重建 task table，複製既有資料後才取代舊 table。因此合法 task 會完整保留；非法 engine 會觸發 `INSERT OR ROLLBACK`，由 migration 自行恢復失敗前狀態。

## 不包含

本 Step 不：

- 實作 engine fallback 或失敗狀態機
- 實作 MOPS／Goodinfo／Yahoo／Google／Grounded AI worker
- 建立 evidence table
- 根據 enum 順序自動改變 task state 或 engine
