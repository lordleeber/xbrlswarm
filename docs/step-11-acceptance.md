# Step-11 驗收 — 可選的解析後 metadata

## 範圍

Step-11 以 `migrations/0004_add_evidence_metadata.sql` 在 evidence table 加入：

```text
period_start
period_end
board_approved_date
audit_committee_date
company_name
```

這些欄位都是 nullable `TEXT`，只有來源明確提供時才填寫。來源未提供或尚未解析時
保留 `NULL`，不得從 task、其他 evidence 或外部假設補值。

## RED

先新增 SQLite regression tests，要求：

- 五個 Step-11 欄位存在，型別為 nullable `TEXT`。
- 來源未提供 metadata 時，五欄預設為 `NULL`。
- 來源提供的日期與公司名稱可以不失真地寫入並讀回。
- migration 保留既有 evidence 的所有欄位值，新增欄位為 `NULL`。
- evidence schema 文件明定來源忠實性與 nullability 契約。

測試先因 `migrations/0004_add_evidence_metadata.sql`、五個欄位及本驗收文件尚未存在而失敗。

## GREEN

新增 migration，以單一 transaction 執行五個 `ALTER TABLE ... ADD COLUMN`，不重建
evidence table。既有資料與 foreign key 宣告不變；新增欄位不設 default，因此既有與
未提供 metadata 的新資料列都保持 `NULL`。

同步更新 `docs/evidence-schema.md` 與 README，記錄欄位語意、來源限制及 Step 邊界。

## 不包含

本 Step 不：

- 從 fiscal year 或 report period 推導 `period_start`／`period_end`
- 正規化或補齊 `company_name`
- 定義日期格式或跨欄位日期順序 constraint
- 實作來源 parser、repository 或 worker result flow
- 定義 Step-12 logical evidence identity 或 unique constraint
