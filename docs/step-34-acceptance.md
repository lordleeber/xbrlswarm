# Step-34 驗收 — Goodinfo 公告清單查詢

`xbrlswarm.goodinfo_list.AnnouncementListQuery` 以明確提供的公司代號、開始及結束
日期建構 Goodinfo 的 `StockAnnounceList.asp` URL；query 只含 `STOCK_ID`、
`START_DT`、`END_DT`。公司代號保留文字形式與前導零，日期採西元 `YYYY/MM/DD`。
反向日期區間及不安全公司代號會被拒絕。此 Step 不推測各季搜尋時間窗；Step-35
才定義時間窗規則。

`capture_announcement_list` 發出單次 GET，保存**原始 HTML bytes**、SHA-256、
查詢 URL、日期範圍、HTTP status、final URL、content type 與擷取時間。呼叫者可
用以下 CLI 建立一筆歷史區間公告清單的原始 capture：

```bash
python -m xbrlswarm.goodinfo_list \
  --stock-id 2330 --start-date 2024-01-01 --end-date 2024-12-31 \
  --output-root ./goodinfo-captures
```

輸出到 `<output-root>/<stock-id>/<start>_<end>.html` 和同名 `.json`；既有檔案
不覆寫。允許同站 `/tw2/` 路徑及附加分頁參數，但必須保留原公司與日期範圍。
HTTP 失敗、查詢條件被改寫、Cloudflare challenge、初始化頁或非公告
HTML 都不會被當成空清單，也不會建立有效 capture。原始回應仍須經 Step-36
解析候選列、Step-37 解析詳細頁面，才能產生 evidence。這個查詢結果本身不
宣稱公告時間或 XBRL 確認時間，也不會改寫 task 狀態。

2026-09-24 在本執行環境以 2330／2024 全年範圍請求，Goodinfo 回傳
HTTP 403 且 `cf-mitigated: challenge`，因此未保存真實歷史清單 fixture，亦未
宣稱已驗證歷史涵蓋率。離線 regression tests 以注入的回應驗證 URL、原始 bytes
與 metadata、重複擷取防護及異常回應拒絕。此 Step 無 migration。
