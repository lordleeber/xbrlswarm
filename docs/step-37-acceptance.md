# Step-37 驗收 — Goodinfo 公告詳細頁

`capture_goodinfo_detail` 對 Step-36 候選的同站詳細頁 URL 發出 GET，先核對回應狀態、
redirect 後的 `STOCK_ID`／`CLAIM_TIME`／`SUBJECT` 與詳細頁內容，再保存原始 HTML、
SHA-256、byte 長度、回應 URL 和清單來源 hash。相同 URL 的 capture 由專用 lock
保護，既有檔案不覆寫。HTTP 錯誤、challenge、非 HTML、跨公告 redirect 或頁面
與 URL 不符會被拒絕，不能當成空結果。

`parse_goodinfo_detail` 從頁面可見的發言日期與時間組成 `claim_time`，並與 URL
核對；從主旨抽取 `subject`，從說明欄位抽取有明確標籤的報導期間起訖、董事會
日期和審計委員會日期。未出現的日期保留 `None`。矛盾或無效的日期會被拒絕。
清單中的期別與範圍仍只是 hint；本 Step 不把候選轉成 evidence，不改 task，
也不把 `claim_time` 當作 XBRL 確認時間。後續 Step-38 才處理公告事件。

Goodinfo 的[年程第 2 季公告](https://goodinfo.tw/tw/StockAnnounceDetail.asp?CLAIM_TIME=2026%2F08%2F07+17%3A06%3A00&STOCK_ID=3117&SUBJECT=%E5%85%AC%E5%91%8A%E6%9C%AC%E5%85%AC%E5%8F%B8%E8%91%A3%E4%BA%8B%E6%9C%83%E9%80%9A%E9%81%8E115%E5%B9%B4%E7%AC%AC2%E5%AD%A3%E5%90%88%E4%BD%B5%E8%B2%A1%E5%8B%99%E5%A0%B1%E5%91%8A)
呈現發言日期／時間、主旨、董事會與審計委員會日期、報導期間。
[迎廣第 2 季公告](https://goodinfo.tw/tw/StockAnnounceDetail.asp?CLAIM_TIME=2026%2F08%2F13+15%3A05%3A17&STOCK_ID=6117&SUBJECT=%E5%85%AC%E5%91%8A%E6%9C%AC%E5%85%AC%E5%8F%B8%E8%91%A3%E4%BA%8B%E6%9C%83%E9%80%9A%E9%81%8E115%E5%B9%B4%E7%AC%AC2%E5%AD%A3%E5%90%88%E4%BD%B5%E8%B2%A1%E5%8B%99%E5%A0%B1%E5%91%8A)
使用較短的董事會與審計委員會標籤，以及全形 `～` 期間分隔符。
回歸測試用依這些欄位建構的合成 HTML；尚未保存可重播的真實詳細頁 raw fixture，
因此網站 DOM 相容性與歷史版面涵蓋率仍待原始回應驗證。

`contracts/goodinfo-detail.json` 定義機器可讀邊界。本 Step 無 migration。
