# Step-14 修訂歷史

## 已驗證的範圍

來源探索的 12 份 MOPS XBRL fixture 都帶有 `ReportType=Financial report (general)`。
此值無法區分 `original`、`amendment` 或 `supplemental`。canonical source matrix 仍將
`filing_kind` 標為 `not_verified`；這些 fixture 的修訂類型只能是 `unknown`。不同
`raw_payload_hash` 表示不同 evidence，卻不能單獨證明第二份是更正申報。

`contracts/revision-kinds.json` 與 domain `RevisionKind` 定義四個可用分類；若沒有可稽核的
來源規則，分類維持 `unknown`。目前不在 production evidence schema 增加 `filing_kind`，
也不建立猜測性的 original／amendment 關聯。日後必須先取得涵蓋實際更正、補充與原始
申報的 raw evidence，更新 observation、source matrix 與決定性來源規則，才能新增儲存欄位。

## 保存方式

Step-13 的 identity index 讓同一 locator 的不同 payload 追加為不同 evidence。Step-14 的
`migrations/0006_preserve_evidence_history.sql` 以 `immutable source evidence` trigger 保護
已保存的 source、event、payload 與 retrieval metadata：更正申報只能新增 evidence，不能
覆蓋或刪除原始證據。這也保存了未來可供修訂分類的完整歷史。

SQLite 的 `REPLACE` 在 unique 衝突時會先刪除舊列；只有啟用 `recursive_triggers` 才會呼叫
DELETE trigger。Migration 會啟用此設定，正式執行時須使用
`xbrlswarm.storage.connect_database` 開啟每個 runtime connection。它同時開啟 foreign keys，
並拒絕沒有完整 immutability guard 的既有 evidence schema。因此 `INSERT OR REPLACE`、
`REPLACE INTO` 與直接 DELETE 都無法移除原始 evidence。

UPDATE trigger 目前逐欄比較來源欄位，刻意排除可更新的 `verification_state`。日後任何
migration 新增 source-backed evidence 欄位時，必須在同一 migration 重建 trigger，並加上
regression test。Runtime connection 會比對 `PRAGMA table_info(evidence)` 與 trigger 涵蓋欄位；
若發現未受保護的欄位（例如新加的 `filing_kind`），會拒絕開啟該資料庫。

`verification_state` 屬於後續驗證流程，允許單獨更新；其正式值域與轉移規則由 Step-54
定義。來源聲稱與擷取 metadata 一經保存則不得改寫，須以新 evidence 記錄新的來源回應。

## 尚未宣稱的事項

- 新 payload 不一定是 amendment，也可能是來源格式變更或其他差異。
- 目前沒有公開歷史來源規則可將 12 份 MOPS fixture 判為 original。
- 目前沒有可驗證的 `filing_kind` schema 值或 revision-to-original 指向關係。
