# Step-45 驗收 — Yahoo 查詢建構器

`xbrlswarm.yahoo_search` 把 task 轉成 Yahoo 搜尋查詢、解析 SERP，並把一次抓取
結果分類成候選、`not_found` 或可重試失敗。抓取本身沿用
`tools/yahoo_serp_capture.js`（有畫面的 Chromium，完成 `/_bv/` bot 驗證）。
機器可讀契約見 `contracts/yahoo-search-query.json`。

## 查詢格式

```text
site:tw.stock.yahoo.com {stock_id} {company} 董事會通過 {民國年}{期別用語} {範圍用語}財務報告
```

| 期別 | 用語 | 範圍 | 用語 |
| --- | --- | --- | --- |
| FY | `年度` | consolidated | `合併` |
| Q1／Q2／Q3 | `年第一季`／`年第二季`／`年第三季` | individual | `個體` |
| | | 未指定 | （空字串，只留 `財務報告`） |

例：`site:tw.stock.yahoo.com 8119 公信 董事會通過 113年度 合併財務報告`。
URL 為 `https://tw.search.yahoo.com/search?p=` 加上與 `encodeURIComponent` 相同的
編碼；測試逐字比對 builder URL 與瀏覽器實際請求的 URL。

決策與理由：

- **民國年**：Yahoo 公告鏡像的標題照抄 MOPS 主旨（`公信董事會通過113年度合併財務報告`），
  用西元年查詢無法對上標題字詞。ROADMAP 要求的 `fiscal_year` 以民國年呈現。
- **公告用語「董事會通過」**：Step-44 只含基本欄位的查詢，SERP 全是第三方財報頁。
- **`site:tw.stock.yahoo.com`**：Yahoo worker 要找的是 Yahoo 股市的公告鏡像。
  未限定網域時，頎邦的查詢完全被第三方頁佔滿（見下表 F）；限定後七筆結果全是
  `tw.stock.yahoo.com`。跨站鏡像留給 Step-48 的 Google worker。
- task 資料表沒有公司名稱與範圍。`company` 由呼叫端提供；`report_scope` 可為
  `None`，此時查詢只含 `財務報告`。

## 抓取與結果分類

| 回應 | 分類 |
| --- | --- |
| HTTP 200、可辨識的 SERP、至少一筆候選 | 候選清單（`outcome=None`） |
| HTTP 200、可辨識的 SERP、沒有候選 | `not_found` |
| HTTP 200，但不是 SERP，或沒有任何一筆自然結果解得出目標網址 | `temporary_error` |
| HTTP 429 | `rate_limited` |
| 307 `/_bv/` 轉址、`/_bv/` 500、其他狀態 | `temporary_error` |
| 擷取工具沒有取得 HTTP 200 文件（非零結束碼，不寫檔） | `temporary_error` |

「可辨識的 SERP」指 `<title>` 以 `- Yahoo 網頁搜尋` 結尾，且至少有一筆能解出
目標網址的自然結果。解不出絕對目標網址的單筆結果（相對 href、沒有 `RU=` 的
Yahoo 轉址）直接略過，不讓整頁變成 `temporary_error`：查詢固定，重試會拿到
同一頁，而 Step-27 沒有重試上限，整頁失敗會讓 task 永遠重試。缺標題的結果
保留，標題為空字串，仍可由 URL slug 判斷 identity。Yahoo 對亂碼查詢仍回填充結果，因此**沒有**以
「找不到結果」字樣判斷查無結果；零筆自然結果視為版面異常而非 `not_found`。

`classify_yahoo_serp_capture()` 直接讀擷取工具的 `.meta.json`：request URL 必須
等於該 target 的 builder URL，final URL 必須是 `tw.search.yahoo.com/search`，
解壓後 body 的 SHA-256 必須與 metadata 相符，否則拒絕分類。

## SERP parser 與候選 identity

`parse_yahoo_serp()` 讀取 `data-matarget="algo"` 的自然結果：`<h3>` 內文字為標題，
同一 `<li>` 內第一個 `<p>` 為摘要，`href` 的 `/RU=` 段**只解碼一次**即為目標網址
（解出的網址本身仍保留 percent-encoded path）。轉址主機有 `r.search.yahoo.com`
與 `rd.search.yahoo.com` 兩種，parser 不依賴主機名稱。

候選須同時符合：

- 網址為 `https://tw.stock.yahoo.com/news/...`（個股頁 `/quote/...` 不算）；
- 標題或 URL slug（兩者合併、NFKC 正規化）以**完整簡稱**含公司名稱，並含
  `財務報告`。完整簡稱指名稱前面不是漢字，後面是非漢字（標點、空白、數字）、
  字串結尾，或 `董事會`／`民國`／`公告`／`本公司`，因此 `統一` 不會命中
  `統一超`，`華電` 不會命中 `中華電`；
- 含 `{民國年}年度`（後面不接 `第`）或 `{民國年}年[度]第{一|1}季` 形式的期別，
  年份前不得緊接數字；
- 指定範圍時，不能只含相反範圍字樣（`合併及個體` 可接受）；
- 摘要若出現 `公司名稱：X (代號)`，代號須等於 `stock_id`。

這是寬鬆的前置篩選，**不是**採信證據：頁面本身的公司代號、主旨與報導期間由
Step-46 驗證，文章時間與公告時間的區分由 Step-47 處理。

## 驗收證據

測試：`pytest` 由基線 473 passed 增至 **553 passed**，code review 修正後為 **566 passed**（`tests/test_yahoo_search.py`
與 `tests/test_yahoo_fixtures.py` 的新 SERP 參數）。`test_yahoo_search.py` 先以只有
介面的 stub 執行，71 項全數 FAILED 後才實作；頎邦案例的測試在 fixture 入庫前 FAILED。

新增三份真實 SERP fixture（2026-09-26，headed Chromium，均為 `307 → 307 → 200`），
manifest 以 `query_target` 記錄查詢對象：

| fixture | 查詢對象 | 自然結果 | 分類 |
| --- | --- | --- | --- |
| `builder_fy_consolidated` | 8119 公信 2024 FY 合併 | 7 筆 Yahoo；第 1 筆即 Step-44 `valid_result` 的網址。另有 111、107 年度公告、輔信公告、個股頁 | 候選 1 筆（目標公告） |
| `builder_q2_consolidated` | 8119 公信 2024 Q2 合併 | 7 筆 Yahoo；有 115、111、108 年度公告、輔信、台航，**沒有** 113 年第二季 | `not_found` |
| `builder_fy_other_wording` | 6147 頎邦 2024 FY 合併 | 標題為 `頎邦民國113年度合併財務報告業經董事會決議`，另有 `民國113年第3季` 公告與 5 個個股頁 | 候選 1 筆（目標公告） |

以 Python builder → 擷取工具 → `classify_yahoo_serp_capture()` 串接的即時端到端
重跑（未入庫）：8119 FY 與 6147 FY 均回傳上表同一篇公告為唯一候選。

查詢字串的探測紀錄（2026-09-26，每筆一次）：

| | 查詢 | 結果 |
| --- | --- | --- |
| A | `8119 公信 董事會通過 113年度 合併財務報告` | 第 1 筆為 FY 公告；其餘為 MOPS、Goodinfo、money-link、公司官網 |
| B | `8119 公信 董事會通過 113年第二季 合併財務報告` | 無 113 年第二季；出現 115 年公告 |
| C | `8119 公信董事會通過113年第二季合併財務報告` | 無 113 年第二季；出現 115 年公告、nstock 重訊 |
| D | `site:tw.stock.yahoo.com 公信 董事會通過 113年第二季 合併財務報告` | 7 筆 Yahoo，無 113 年第二季 |
| E | builder FY 查詢 | 即 `builder_fy_consolidated` |
| F | `6147 頎邦 董事會通過 113年第一季 合併財務報告` | 無 Yahoo 公告鏡像；諸彼特、財報狗、biggo、LINE TODAY 等第三方頁 |

## 踩到的坑

- **原本以為**加入「董事會通過」就足以帶出公告鏡像。8119 FY 可以（A），但頎邦
  （F）仍全是第三方頁；限定 `site:` 後才穩定集中在 Yahoo 股市。
- **原本以為**把公告標題原樣放進查詢（C）能對上 113 年第二季公告。這篇公告
  確實存在（Step-44 `wrong_quarter` 就是它），但四種寫法都沒帶出來。Yahoo 索引／
  排序不保證命中，因此查無結果只能代表「這次 SERP 沒有符合的候選」，屬語意耗盡，
  不代表公告不存在。
- **原本以為**所有公司都用「董事會通過」。頎邦用「業經董事會決議」，而且季別寫成
  阿拉伯數字（`113年第3季`）；候選規則因此不要求公告用語，並接受 `一`／`1` 兩種寫法。
- SERP 的 anchor 文字混有 breadcrumb（`Yahoo奇摩股市tw.stock.yahoo.com › news › ...`），
  標題必須只取 `<h3>` 內文字。
- `RU=` 的值是雙重編碼；解碼兩次會把目標網址的 path 解成原始中文，與 Step-44
  fixture 記錄的網址不一致。

## 限制與未完成

- 只驗證兩家公司的 FY 與一個 Q2 查詢；季報查詢在本次樣本中沒有命中，季報的
  Yahoo 命中率尚未量測。
- 期別只接受已觀察到的寫法；`上半年度` 等其他 Q2 寫法尚未觀察，現在會被當成非候選。
- 公司名稱的接續詞只接受已觀察到的 `董事會`／`民國`／`公告`／`本公司`；其他漢字
  接續寫法會被當成非候選。（原本「公司名稱以子字串比對、同名前綴交由 Step-46
  剔除」的限制已在 code review 後修正，見下節。）

## Code review 修正（2026-09-26）

- 單一自然結果解不出目標網址時，原本整頁判為 `temporary_error`，已找到的候選
  也被丟棄，且固定查詢會無限重試。改為略過該筆；全頁都沒有可用結果才是版面異常。
- 公司名稱原本以子字串比對，`統一` 會命中 `統一超`（2912）。改為完整簡稱比對，
  同時處理名稱在後段的情形（`華電`／`中華電`）。
- 回歸測試：以真實 `builder_fy_consolidated` 改壞第 1 或第 5 筆 href、缺標題結果、
  四組前後綴撞名，以及五種已觀察到的公司名稱接續寫法。
- 沒有 resident Yahoo worker：`/lease` 仍不能依 engine 篩選，`/result` 也不能上傳
  evidence。本步驟只提供查詢、解析與分類，不寫入 evidence 或 task 狀態。
- `rate_limit` 仍是合成樣本；真實 Yahoo 限流頁尚未觀察到。
