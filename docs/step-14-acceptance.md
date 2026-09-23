# Step-14 驗收 — 保留修訂歷史

## RED

先新增 regression tests，驗證同一 task、source、locator 的不同 payload 可同時保存；
source evidence 的 UPDATE 與 DELETE 會被拒絕；既有資料套用 migration 後保持不變；
目前 12 份 MOPS fixture 的 `ReportType` 只能對應 `unknown`，且 `filing_kind` 不得繞過
Step-3 source-evidence gate 進 production schema。

測試先因保護 trigger、domain enum、分類契約與文件尚未存在而失敗。

## GREEN

新增 `migrations/0006_preserve_evidence_history.sql`，以資料庫 trigger 禁止覆寫或刪除
來源證據；保留 Step-54 後續所需的 `verification_state` 更新空間。新增
`contracts/revision-kinds.json` 與 domain enum，定義 `original`、`amendment`、
`supplemental`、`unknown`。來源分類仍未驗證，現有 MOPS fixture 的唯一安全值是
`unknown`。

本 Step 不新增 `filing_kind` 欄位，因 source matrix 仍是 `not_verified`。待真實來源
案例建立可重播的分類規則後，才以新 migration 儲存分類與修訂關係。
