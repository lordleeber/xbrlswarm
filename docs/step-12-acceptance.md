# Step-12 驗收 — 定義邏輯證據識別

## 範圍

Step-12 新增 `contracts/logical-evidence-identity.json`，正式定義 same task、same source、
same source locator、same event 與 same payload 的欄位投影、來源 profile、比較順序及缺值語意。

本 Step 是契約定義，不建立 unique constraint，也不實作 repository 寫入去重。

## RED

先新增 contract regression tests，要求：

- 五個 ROADMAP identity 維度映射到既有 evidence schema 欄位。
- MOPS profile 在 locator 與 payload hash 完整且 projection 相同時判定為 `same`。
- task、source 或 profile 中兩邊皆已知的 locator、event、payload 值不同時判定為 `different`。
- Profile 必要欄位單邊或雙邊缺失時判定為 `unresolved`，不能把 `NULL` 當成差異。
- Goodinfo 可使用 locator + CLAIM_TIME + SUBJECT 判定同一公告，不全域要求 payload hash。
- 尚無 source profile 的 evidence 維持 `unresolved`。
- `retrieved_at`、來源描述、驗證狀態及 Step-11 metadata 不參與 identity。
- Step-12 不得提前加入 Step-13 unique index 或 Step-14 revision schema。

測試先因 machine-readable contract 與決策文件尚未存在而失敗。

## GREEN

新增 identity contract 與 `docs/logical-evidence-identity.md`，定義 exact-value、三態比較及
append-only 邊界。契約只引用現有 evidence 欄位，因此本 Step 不需要 migration。

Code review regression 進一步加入 asymmetric missing 與無 payload hash 的 Goodinfo 案例，
並將 contract 改為依 Step-31／Step-39 選擇 source-specific profile。

Step-13 實作前再確認：所有 profile comparison field 的 asymmetric missing 都必須維持
`unresolved`；否則 `same` 不具等價關係，無法安全建立 unique protection。

## 不包含

- 不建立 unique constraint 或 identity digest 欄位。
- 不實作 crawl retry 的 database upsert。
- 不用 `source_url` 猜測或填補缺少的 `source_locator`。
- 不替尚未研究完成的 Yahoo、Google mirrors 或 Grounded AI 預設 identity profile。
- 不分類 original、amendment、supplemental 或 unknown。
- 不定義 event precision 的正式 enum。
