# Step-31 驗收 — 保存 MOPS 原始回應

`accept_mops_response` 接收已取得的原始 response bytes、MOPS task／case、來源 URL
及擷取時間。Step-30 parser 先驗證合併 XBRL 版面與已證實欄位；task 的公司代號、
年度、期別及 engine 再與資料庫比對。只有通過檢查的回應才新增
`evidence_type=xbrl_document`、`source_type=mops` 的 evidence。

每筆新接受的 evidence 都將**原始 response bytes**計算為
`raw_payload_hash=sha256:<64 位十六進位摘要>`；不對解析後 XML、壓縮 fixture
或正規化文字取 hash。重抓同一 locator 與 payload 時返回原 evidence；同一
locator 的不同原始 bytes 會新增 evidence，保留修訂歷史。`retrieved_at` 是
擷取 metadata，不是申報或 XBRL 確認時間。

預設快照政策關閉，`raw_snapshot_path=NULL`。呼叫時提供 `snapshot_root` 即開啟
政策：原始 bytes 會以 SHA-256 內容定址，寫到
`<root>/<前兩碼>/<次兩碼>/<digest>.bin`，並在同一筆 evidence 保存絕對路徑。
寫入使用同目錄暫存檔與原子 hard link；已存在檔案必須與本次 bytes 完全相同，
不覆寫內容。重抓已存快照時會核對路徑與內容。既有只有 hash 的不可變 evidence
不能在事後補寫快照路徑；若要保留快照，須在首次接受時啟用政策。

Migration `0009_add_raw_snapshot_path.sql` 新增 nullable 欄位，保留既有列並更新
不可覆寫 trigger。檔案系統與 SQLite 無共同交易；若快照寫入後資料庫交易失敗，
內容定址檔案可能成為無引用檔案，可由檔名 hash 安全辨識並定期清理。

Regression tests 覆蓋 hash、快照 byte-for-byte、重抓去重、不同 payload 保留、
非法回應與 task 拒絕、不可變歷史及舊資料 migration。此 Step 不啟動 MOPS
試點，也不推導未驗證的 filing metadata。
