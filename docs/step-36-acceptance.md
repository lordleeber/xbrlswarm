# Step-36 驗收 — Goodinfo 清單候選項目

`parse_captured_goodinfo_candidates` 讀取 Step-34 保存的原始 HTML 與 metadata，
先核對 byte 長度、SHA-256 與查詢條件，再從清單連結抽取**待驗候選項目**。
它不寫入 evidence、不完成 task，也不推導 `announcement_at` 或 XBRL 確認時間。

候選項目須有同站 `StockAnnounceDetail.asp` 連結，URL 的 `STOCK_ID` 與本次
查詢一致，`CLAIM_TIME` 的日期落在查詢區間內，且帶有非空 `SUBJECT`。
顯示標題另須包含「財務報告」，以及「第1／2／3季」或「年度」。解析器保留
原顯示標題、完整 detail URL、清單 URL 與原始 hash；期別和「合併／個體」
只作**提示**。未出現範圍字樣時，提示為空，不猜測。像「董事會預計召開日期」
這種清單項目會標記 `scheduled_meeting=true`，交由 Step-37 詳細頁驗證，
不能視為已發布的財報。重複 detail URL 只列一次。

Goodinfo 的[公開公告清單](https://goodinfo.tw/tw/StockAnnounceList.asp)
可觀察到財務報告公告與董事會預計召開日期並列，並連向帶上述參數的
[公告詳細頁](https://goodinfo.tw/tw/StockAnnounceDetail.asp?CLAIM_TIME=2026%2F08%2F06+13%3A55%3A00&STOCK_ID=6152&SUBJECT=%E5%85%AC%E5%91%8A%E6%9C%AC%E5%85%AC%E5%8F%B8%E8%91%A3%E4%BA%8B%E6%9C%83%E6%B1%BA%E8%AD%B0%E9%80%9A%E9%81%8E115%E5%B9%B4%E7%AC%AC2%E5%AD%A3%E5%90%88%E4%BD%B5%E8%B2%A1%E5%8B%99%E5%A0%B1%E5%91%8A)。
但本環境仍收到 HTTP 403 challenge，無法取得可提交的真實 raw list HTML；
目前的 DOM 回歸案例是**合成版面**，不能宣稱已驗證網站實際 DOM、歷史
涵蓋率或分頁。沒有候選項目只表示本次解析沒有找到匹配連結，不代表公告
或財報不存在。版面若改用 JS 動態連結，需取得原始 fixture 後擴充解析規則。

`contracts/goodinfo-list-candidates.json` 定義機器可讀邊界。本 Step 無 migration。
