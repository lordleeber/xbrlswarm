# Step-11 驗收 — 可選的解析後 metadata

## 範圍

ROADMAP Step-11 的 parsed metadata 候選欄位是：

```text
period_start
period_end
board_approved_date
audit_committee_date
company_name
```

依 Step-3 schema gate，只有 source matrix 中為 `direct` 或具有決定性規則的 `derived`
欄位可以進 production schema。目前只有 `company_name` 是 `direct`，因此
`migrations/0004_add_evidence_metadata.sql` 只加入 nullable `TEXT` 的 `company_name`。

`period_start`、`period_end`、`board_approved_date` 與 `audit_committee_date` 都尚未通過
gate，維持 deferred。來源未提供或尚未解析公司名稱時保留 `NULL`，不得從 task、其他
evidence 或外部假設補值。

## RED

先新增 SQLite regression tests，要求：

- production schema 中的 Step-11 欄位必須精確等於 source matrix 中通過 gate 的候選欄位。
- `company_name` 存在且型別為 nullable `TEXT`。
- 來源未提供公司名稱時預設為 `NULL`。
- raw observation 中的公司名稱可以不失真地寫入並讀回。
- migration 保留既有 evidence 的所有欄位值，新增的 `company_name` 為 `NULL`。
- evidence schema 文件明定來源忠實性與 nullability 契約。

初始 RED 先因 `migrations/0004_add_evidence_metadata.sql`、parsed metadata 欄位及本驗收文件
尚未存在而失敗。Code review regression 另確認：若 migration 將未列於 matrix 或未達
`direct`／`derived` 的候選欄位加入 schema，測試會失敗。

## GREEN

新增 migration，以單一 transaction 執行 `ALTER TABLE ... ADD COLUMN company_name TEXT`，
不重建 evidence table。既有資料與 foreign key 宣告不變；新增欄位不設 default，因此
既有與未提供公司名稱的新資料列都保持 `NULL`。

同步更新 `docs/evidence-schema.md` 與 README，記錄欄位語意、來源限制及 Step 邊界。

## 不包含

本 Step 不：

- 從 fiscal year 或 report period 推導 `period_start`／`period_end`
- 在缺少 deterministic extraction rule 與 matrix evidence 時建立 `period_start`、`period_end` 或 `board_approved_date`
- 在缺少 fixture/source evidence 時建立 `audit_committee_date`
- 正規化或補齊 `company_name`
- 定義日期格式或跨欄位日期順序 constraint
- 實作來源 parser、repository 或 worker result flow
- 定義 Step-12 logical evidence identity 或 unique constraint
