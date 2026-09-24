# Step-44 Yahoo worker fixtures

`manifest.json` 固定 Yahoo worker 後續開發使用的九個 raw response 案例。共同的
目標任務是 **公信 (8119)、2024 年 FY、合併財務報告**。五篇公告鏡像均由
`tw.stock.yahoo.com` 在 2026-09-25（台灣時間）實際回傳 HTTP 200；
「wrong」案例各自只與目標任務相差一個條件（公司名稱與代號視為同一條件）。

| 案例 | 來源性質 | 頁面可觀察的差異 |
| --- | --- | --- |
| `valid_result` | 真實 Yahoo 公告頁 | 公信、113 年度、合併，報導期間至 113/12/31 |
| `wrong_year` | 真實 Yahoo 公告頁 | 公信、114 年度、合併 |
| `wrong_quarter` | 真實 Yahoo 公告頁 | 公信、113 年第二季、合併，報導期間至 113/06/30 |
| `wrong_company` | 真實 Yahoo 公告頁 | 友達 (2409)、113 年度、合併 |
| `wrong_scope` | 真實 Yahoo 公告頁 | 公信、113 年度、**個體** |
| `unexpected_page` | 真實 Yahoo 個股頁 | HTTP 200，但頁面標題是個股走勢圖，並非公告文章 |
| `search_redirect` | 真實 Yahoo 搜尋回應 | HTTP 307、空 body、`Location` 指向 `/_bv/v.gif`；追隨時在此環境重複轉址 |
| `no_result` | **合成** | HTTP 200 的空搜尋結果控制流程樣本；不是 Yahoo 實際版型 |
| `rate_limit` | **合成** | HTTP 429、`Retry-After: 60` 的控制流程樣本；不是觀察到的 Yahoo 限流回應 |

每筆 `.html.gz` 只對 response bytes 做無損 gzip。對應的 `.meta.json` 保存
request URL、method、可重現的 request headers、HTTP status、final URL、
擷取時間、解壓後 body 的 SHA-256 與位元組長度；`.headers.json` 保存與重播
有關的 response headers，排除 cookie。`origin` 明確區分 `live` 和 `synthetic`。
合成回應的 `retrieved_at` 為 `null`，不能引用為 Yahoo 的實際觀察。

舊專案 `revswarm/worker/yahoo_worker.py` 實際使用 `curl --http1.1` 向
`tw.search.yahoo.com/search` 查詢，並把非 HTTP 200 或過短的回應列為可重試的
抓取失敗，而非「查無結果」。本次以相同的 HTTP/1.1 設定查詢公信財報，
仍得到 HTTP 307 與空 body；`search_redirect` 保存此回應。這**不能**解讀成
沒有相關公告，也不能單憑 307 判定 Yahoo 已限流。舊 worker 針對的是
**月營收**；其月份查詢字串與次月日期窗不能直接用於財務報告。

Yahoo 搜尋在本環境未提供可用的真實 SERP，包括命中與零結果頁。因此合成
`no_result` 只能測試控制流程，**不能作為 Step-45 的搜尋版型解析依據**。
目前的真實 HTTP 200 fixture 可驗證 Step-46 的文章內容，不能驗證 SERP 候選
擷取。後續取得可重播的真實 SERP 或限流頁時，須新增真實 fixture，
並保留來源性質標記；在此之前搜尋解析不能宣稱已由真實頁面驗證。

五篇公告的標題、公司名稱／代號、主旨與財務報告報導期間可以供 Step-46
驗證候選 identity。Yahoo 頁面的 `datePublished` 是**文章發布時間**；內文
「提報董事會或經董事會決議日期」僅提供日期，兩者都不是有秒精度的
MOPS 公告發言時間。Step-47 不能直接把文章時間存成 `announcement_at`。
頁面提及財務報告，也不能據此推導 XBRL 申報或確認時間。
