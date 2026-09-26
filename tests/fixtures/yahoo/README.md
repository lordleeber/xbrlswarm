# Step-44／45 Yahoo worker fixtures

`manifest.json` 固定 Yahoo worker 後續開發使用的 raw response 案例：Step-44 的十個
案例、Step-45／46 的 `builder_*` SERP，以及 Step-46 的 `article_*` 文章頁。Step-44 案例共同的目標任務是 **公信 (8119)、2024 年 FY、合併財務報告**。五篇公告鏡像均由
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
| `search_redirect` | 真實 Yahoo 搜尋回應 | HTTP 307、空 body、`Location` 指向 `/_bv/v.gif`：bot 驗證轉址的第一跳 |
| `search_results` | 真實 Yahoo SERP（瀏覽器） | 目標查詢通過 `/_bv/` 後的 HTTP 200 結果頁；7 筆自然結果均為 8119 的第三方財報頁 |
| `no_result` | 真實 Yahoo SERP（瀏覽器） | 亂碼查詢的 HTTP 200 結果頁；Yahoo 仍給出無關的填充結果，沒有任何 8119／公信候選 |
| `rate_limit` | **合成** | HTTP 429、`Retry-After: 60` 的控制流程樣本；不是觀察到的 Yahoo 限流回應 |
| `builder_fy_consolidated` | 真實 Yahoo SERP（瀏覽器） | Step-45 builder 的 8119 FY 查詢；第 1 筆即 `valid_result` 公告 |
| `builder_q2_consolidated` | 真實 Yahoo SERP（瀏覽器） | Step-45 builder 的 8119 Q2 查詢；7 筆 Yahoo 結果都不是 113 年第二季公告 |
| `builder_fy_other_wording` | 真實 Yahoo SERP（瀏覽器） | Step-45 builder 的 6147 頎邦 FY 查詢；公告標題用「業經董事會決議」 |
| `builder_q3_other_wording` | 真實 Yahoo SERP（瀏覽器） | Step-46 擷取的 6147 頎邦 Q3 查詢；唯一候選即 `article_q3_other_wording` |
| `article_other_wording` | 真實 Yahoo 公告頁 | 頎邦、113 年度、合併；期間標籤拆成兩行 |
| `article_q3_other_wording` | 真實 Yahoo 公告頁 | 頎邦、113 年第 3 季、合併，期間 113/01/01~113/09/30 |
| `article_not_mops_form` | 真實 Yahoo 新聞頁 | 「興櫃：公信(8119)109年度合併財報…」：有期間，沒有公司名稱與主旨標頭 |
| `article_without_report_period` | 真實 Yahoo 公告頁 | 2019 年舊版重大訊息格式，公信 107 年度個體及合併；沒有報導期間欄位 |

`builder_*` 案例於 2026-09-26 擷取，manifest 的 `query_target`
記錄各自的查詢對象（不一定是上方的 `target_task`），其 request URL 必須等於
`xbrlswarm.yahoo_search.yahoo_search_plan()` 對該對象產生的 URL。`article_*` 案例
由 Step-46 以與 Step-44 相同的一般 HTTP 請求擷取，`observed_identity` 記錄頁面
可見的身分。

每筆 `.html.gz` 只對 response bytes 做無損 gzip。對應的 `.meta.json` 保存
request URL、method、可重現的 request headers、HTTP status、final URL、
擷取時間、解壓後 body 的 SHA-256 與位元組長度；`.headers.json` 保存與重播
有關的 response headers，排除 cookie。`origin` 明確區分 `live` 和 `synthetic`。
合成回應的 `retrieved_at` 為 `null`，不能引用為 Yahoo 的實際觀察。SERP 的
`.meta.json` 另外記錄 `client`（擷取用的瀏覽器）與 `redirect_chain`（每一跳的
status、URL、`Location`）；request headers 是瀏覽器實際送出的內容，但排除 cookie。

## Yahoo 搜尋的 bot 驗證

2026-09-26 以 Playwright 開啟有畫面的 Chromium 查詢時，每個新查詢都先經過：

```text
GET /search?p=...           → 307, Location: /_bv/v.gif?orig=...&_bvc=...
GET /_bv/v.gif?...          → 307, 設定 YBV cookie, Location: 原搜尋 URL
GET /search?p=...           → 200, 真實 SERP
```

所有 SERP fixture 都是第三跳的 response bytes。同一瀏覽器 session
內連續查詢時，`/_bv/v.gif` 偶爾回 HTTP 500（Playwright 取得的 body 是 Chromium
自己的錯誤頁，不是 Yahoo 回傳的內容；curl 遇到的 500 則是空 body），換下一個
查詢又恢復 200；因此 500
應視為可重試的抓取失敗，不是「查無結果」，也未證實是限流。此回應未保存成
fixture。

舊專案 `revswarm/worker/yahoo_worker.py` 使用 `curl --http1.1` 向
`tw.search.yahoo.com/search` 查詢，並把非 HTTP 200 或過短的回應列為可重試的
抓取失敗。本環境的 curl 試驗全部失敗：不保存 cookie 時在 307 間重複轉址
（`search_redirect` 保存第一跳）；使用 cookie jar 雖取得 `YBV`，最後仍是
HTTP 500、空 body；補上完整瀏覽器 headers 也是 500。樣本少，且瀏覽器同樣會
間歇遇到 500，所以不能斷言 curl 永遠無法通過，但 **Step-45 之後的 Yahoo
worker 應以真實瀏覽器（或能完成 `/_bv/` 流程的 client）作為預設抓取方式**。
舊 worker 針對的是**月營收**；其月份查詢字串與次月日期窗不能直接用於財務報告。

## 重新擷取 SERP

`tools/yahoo_serp_capture.js` 以有畫面的 Chromium 完成 `/_bv/` 流程，直接輸出
與上述格式相同的 `.html.gz`、`.headers.json`、`.meta.json`，並印出 manifest
項目供人工審閱後加入（`page_kind` 須自行確認）：

```text
PLAYWRIGHT_MODULE=/path/to/node_modules/playwright \
  node tools/yahoo_serp_capture.js <scenario> '<查詢字串>' [--out DIR]
```

未指定 `--out` 時寫入本目錄並覆蓋同名檔案，試驗時請先輸出到暫存目錄。
沒有取得 HTTP 200 文件（例如 `/_bv/` 回 500）時不寫任何檔案、以非零碼結束，
應視為可重試的抓取失敗。請低頻率使用，連續查詢之間保留間隔。

## SERP 的觀察與限制

- 自然結果位於 `algo-sr` 區塊，標題連結帶 `data-matarget="algo"`，`href` 是
  `rd.search.yahoo.com/.../RU=<URL 編碼的目標網址>/...`，真正目標網址須從
  `RU=` 解碼一次。正式 parser 是 Step-45 的 `xbrlswarm.yahoo_search.parse_yahoo_serp()`；
  `tests/test_yahoo_fixtures.py` 的 `_serp_targets()` 只驗證 fixture 本身。
- `search_results` 的 7 筆自然結果是 Goodinfo、財報狗、treelazy、自由財經、
  HiStock、鉅亨網等**第三方財報頁**，沒有任何 `tw.stock.yahoo.com` 公告鏡像。
  對這個查詢字串，Yahoo 搜尋不會直接帶出 Step-46 要優先採用的公告頁。
  Step-45 改用民國年、公告用語與 `site:tw.stock.yahoo.com`，驗證見
  `docs/step-45-acceptance.md`。
- Yahoo 對亂碼查詢也回傳填充結果（本次為愛奇藝、Wikipedia、LiTV 等），
  **沒有觀察到空白的零結果頁**。因此 worker 的「查無結果」應定義為「SERP 中
  沒有任何符合目標 identity 的候選」，不能靠「找不到結果」之類的字樣判斷。
- `rate_limit` 仍是**合成**的控制流程樣本；目前沒有觀察到 Yahoo 的真實限流頁。
  日後取得時須新增真實 fixture，並保留來源性質標記。

## 公告頁的 identity 與時間

五篇公告的標題、公司名稱／代號、主旨與財務報告報導期間可以供 Step-46
驗證候選 identity。Yahoo 頁面的 `datePublished` 是**文章發布時間**；內文
「提報董事會或經董事會決議日期」僅提供日期，兩者都不是有秒精度的
MOPS 公告發言時間。Step-47 不能直接把文章時間存成 `announcement_at`。
頁面提及財務報告，也不能據此推導 XBRL 申報或確認時間。
