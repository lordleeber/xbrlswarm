# Evidence 重複資料防護

## 實作

Step-13 的 `migrations/0005_add_evidence_deduplication.sql` 依 Step-12 source profile 建立兩個
partial unique indexes：

| Index | 套用範圍 | Identity projection |
| --- | --- | --- |
| `evidence_mops_logical_identity_unique` | locator 與 payload hash 完整的 MOPS evidence | task、source、locator、evidence type、event tuple、payload hash |
| `evidence_goodinfo_logical_identity_unique` | locator、CLAIM_TIME 與 SUBJECT 完整的 Goodinfo evidence | task、source、locator、evidence type、event tuple、SUBJECT、optional payload hash |

Nullable comparison fields 使用 `COALESCE(field, X'')` 建立無碰撞的 NULL sentinel。Evidence
欄位是 `TEXT`，sentinel 是 BLOB，因此來源提供的空字串不會與 `NULL` 合併。

Step-17 的 `0007_enforce_event_precision.sql` 對 Goodinfo `event_precision` 有一項
明確的 legacy 相容例外：Step-15 已保存完整發言日期／時間但精度為 `NULL` 的公告，
在 Goodinfo unique index 中等價於新寫入的 `second`。其他 nullable identity 欄位
仍使用原本的 NULL sentinel；原始列不會被回填或覆寫。

Crawler 寫入已解析 identity 時使用：

```sql
INSERT INTO evidence (...)
VALUES (...)
ON CONFLICT DO NOTHING;
```

第一次 crawl 寫入一列；相同 logical evidence 第二次 crawl 命中 unique index，不新增資料。
直接使用沒有 conflict clause 的重複 `INSERT` 則得到 unique constraint error，不可能靜默建立
第二筆重複列。

## 必須保留的新證據

- MOPS `raw_payload_hash` 不同時是不同 evidence，因此可能代表 amendment 的 payload 會保留。
- Goodinfo locator、CLAIM_TIME、SUBJECT 或兩邊皆存在的 payload hash 不同時會新增 evidence。
- 不同 task、不同 source 或不同 evidence type 分別保存。
- Step-14 已定義 original／amendment／supplemental／unknown；目前缺少來源規則，不能將新 payload 自動分類為 amendment。

## Unresolved identity

Partial index 只涵蓋 profile 必要欄位完整的 evidence。必要欄位缺失、comparison field 單邊
缺值，或 source 尚無 profile 時，identity 是 `unresolved`，不得自動折疊。這些資料仍可
append；後續稽核或 source-specific contract 可以再處理，不能把未知當成相同。

SQLite unique index 無法跨既有重複資料建立。Migration 先用與 indexes 相同的 projection
檢查 MOPS 與 Goodinfo；若發現重複，以 `INSERT OR ROLLBACK` 中止整個 transaction，保留
原資料且不留下部分建立的 index。

## 邊界

- Step-13 不更新或覆蓋既有 evidence。
- Step-13 不建立通用 fuzzy matching、URL canonicalization 或 source fallback。
- Step-13 不替尚無 profile 的 Yahoo、Google mirrors 或 Grounded AI 猜測 identity。
- Step-13 不分類修訂關係；Step-14 定義分類值並保護修訂歷史，具體來源對應仍待驗證。
