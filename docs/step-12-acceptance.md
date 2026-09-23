# Step-12 驗收 — 定義邏輯證據識別

## 範圍

Step-12 新增 `contracts/logical-evidence-identity.json`，正式定義 same task、same source、
same source locator、same event 與 same payload 的欄位投影、比較順序及缺值語意。

本 Step 是契約定義，不建立 unique constraint，也不實作 repository 寫入去重。

## RED

先新增 contract regression tests，要求：

- 五個 ROADMAP identity 維度映射到既有 evidence schema 欄位。
- 完全相同的 identity projection 判定為 `same`。
- task、source、locator、event 或 payload 任一不同都判定為 `different`。
- 缺少 locator 或 payload hash 時，兩筆相同的未知值只能判定為 `unresolved`。
- `retrieved_at`、來源描述、驗證狀態及 Step-11 metadata 不參與 identity。
- Step-12 不得提前加入 Step-13 unique index 或 Step-14 revision schema。

測試先因 machine-readable contract 與決策文件尚未存在而失敗。

## GREEN

新增 identity contract 與 `docs/logical-evidence-identity.md`，定義 exact-value、三態比較及
append-only 邊界。契約只引用現有 evidence 欄位，因此本 Step 不需要 migration。

## 不包含

- 不建立 unique constraint 或 identity digest 欄位。
- 不實作 crawl retry 的 database upsert。
- 不用 `source_url` 填補缺少的 `source_locator`。
- 不分類 original、amendment、supplemental 或 unknown。
- 不定義 event precision 的正式 enum。
