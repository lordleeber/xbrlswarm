# Step-46 驗收 — 優先採用 MOPS 形式的公告鏡像

`xbrlswarm.yahoo_announcement` 審查 Step-45 找到的候選文章頁：只有帶齊 MOPS 公告
欄位、且身分與 task 相符的 Yahoo 公告鏡像才會被接受。機器可讀契約見
`contracts/yahoo-mops-form-mirror.json`。本步驟不寫入 evidence，也不輸出文章
發布時間（Step-47）。

## MOPS 形式

Yahoo 股市轉載的 MOPS 重大訊息，文章本體（`div.atoms[data-component=blocks]`）
依序是：

```text
日　　期：2025年03月12日
公司名稱：公信 (8119)
主　　旨：公信董事會通過113年度合併財務報告
發言人：李立群
說　　明：
1.財務報告提報董事會或經董事會決議日期:114/03/12
...
3.財務報告報導期間起訖日期(XXX/XX/XX~XXX/XX/XX):113/01/01~113/12/31
```

ROADMAP 要求的四個欄位對應如下：

| 欄位 | 來源 |
| --- | --- |
| 公司代號 | `公司名稱` 行括號內的代號 |
| 公司名稱 | `說明` 之前的 `公司名稱` 行 |
| 主旨 | `說明` 之前的 `主旨` 行 |
| 財務報告期間 | `說明` 之後的 `報導期間起訖日期`，民國年轉西元 |

缺任何一項即為 `not_mops_form`，列出缺少的欄位。`日期` 行只有日期，另存為
`announcement_date`，不是公告時間，也不是必要欄位。

解析規則：

- 只讀文章本體內的 `<p>`，且頁面必須恰好有一個文章本體。meta description
  與「相關新聞」卡片會重複 `公司名稱：`／`主 旨：` 等標籤（例如和益的公告），
  不能拿來當欄位。
- 標頭欄位只認 `說明` 之前的行，避免說明第 2 項 `公司名稱:公信電子股份有限公司`
  被當成標頭。
- 各行先做 NFKC 正規化（全形空白、`：`、`～`）。期間標籤可能拆成兩行
  （`3.財務報告或年度自結財務資訊報導期間` ／ `起訖日期(...)`），因此期間從
  說明各行串接後的文字比對。
- 同一欄位出現互相矛盾的值、日期無效或期間起日晚於迄日時，視為版面異常。

## 身分驗證

`verify_yahoo_announcement()` 依固定順序回傳未通過的檢查：

| 檢查 | 條件 |
| --- | --- |
| `stock_id` | 括號內代號等於 task |
| `company` | 公司名稱（NFKC）等於呼叫端提供的名稱 |
| `fiscal_year` | 期間迄日的年份等於會計年度 |
| `report_period` | 迄日等於曆年制期末；起日為 1 月 1 日（累計）或該季起日 |
| `report_scope` | task 指定範圍時，主旨須含 `合併`，或 `個體`／`個別` |
| `financial_report_subject` | 主旨含 `財務報告` |
| `reporting_entity` | 主旨不含 `子公司`（`代子公司…`、`代重要子公司…` 的公司名稱與代號是母公司的，但報告屬於子公司） |

只支援曆年制；非曆年制公司的期間會被判為不符。

## 文章審查與優先順序

| 回應 | 審查結果 |
| --- | --- |
| HTTP 200、MOPS 形式、身分相符 | `accepted` |
| HTTP 200、缺必要欄位 | `not_mops_form` |
| HTTP 200、MOPS 形式、身分不符 | `identity_mismatch`（附不符的檢查） |
| HTTP 200，final URL 在 `tw.stock.yahoo.com` 但不是 `/news/`（首頁、個股頁） | `not_article_page` |
| HTTP 200，final URL 離開 `tw.stock.yahoo.com`（consent、登入頁等） | `temporary_error` |
| HTTP 200，但沒有唯一的文章本體 | `temporary_error` |
| HTTP 404／410 | `article_unavailable` |
| HTTP 429 | `rate_limited` |
| 其他狀態 | `temporary_error` |

`select_yahoo_announcements()` 依候選順序保留所有 `accepted` 的鏡像。「優先」的
實作方式是**非 MOPS 形式的文章一律不接受**，即使排名在前也一樣。沒有任何鏡像被
接受時：只要有一篇文章的審查是可重試的失敗，task 就維持可重試（有 `rate_limited`
時回報它，否則回報 `temporary_error`）；所有候選都有最終判定時，結果才是
`rejected`。SERP 沒有候選時已由 Step-45 回報 `not_found`，所以本步驟不接受空的
審查清單。

多篇鏡像同時被接受時（例如同一期的原公告與更正公告）全部保留，不在本步驟擇一。

## 驗收證據

測試：`pytest` 由 Step-45 合併後的 566 passed 增至 **628 passed**，code review 修正後為
**635 passed**。

- `tests/test_yahoo_announcement.py` 先在只有介面的 stub 上執行，52 項全部 FAILED
  之後才開始實作。
- 實作後有兩項失敗，查明是測試本身寫錯，已修正測試（見下方「踩到的坑」）。
- 頎邦 Q3 的串接測試在 fixture 入庫前先 FAILED（6 項）。

新增的真實 fixture（2026-09-26）：

| fixture | 內容 | 結果 |
| --- | --- | --- |
| `article_other_wording` | 頎邦 113 年度，期間標籤拆成兩行 | 相符的 FY 目標：`accepted` |
| `article_not_mops_form` | 「興櫃：公信(8119)109年度合併財報…」新聞：有期間，沒有公司名稱與主旨 | `not_mops_form`（公司代號、公司名稱、主旨） |
| `article_without_report_period` | 2019 年舊版重大訊息格式「公信董事會通過107年度個體及合併財務報告」 | `not_mops_form`（財務報告期間） |
| `builder_q3_other_wording` | Step-45 builder 的 6147 2024 Q3 SERP | 1 筆候選 |
| `article_q3_other_wording` | 該候選：頎邦民國113年第3季，期間 113/01/01~113/09/30 | `accepted` |

Step-44 的五篇公告鏡像依 manifest 的 `observed_identity`，各自只在預期的那一項
檢查不符：年度 `fiscal_year`、季別 `report_period`、公司 `stock_id`＋`company`、
範圍 `report_scope`。

即時端到端流程：builder → 瀏覽器擷取 SERP → 分類 → 以 HTTP 擷取候選文章 →
審查 → 選擇。

| task | SERP | 文章 | 選擇 |
| --- | --- | --- | --- |
| 8119 2024 FY 合併 | 1 筆候選（fixture） | `valid_result`：`accepted` | 接受 |
| 6147 2024 FY 合併 | 1 筆候選（fixture） | `article_other_wording`：`accepted` | 接受 |
| 6147 2024 Q3 合併 | 1 筆候選（即時，已入庫） | `accepted`，期間 2024-01-01～2024-09-30 | 接受 |

這是 Yahoo 路徑第一次在季報上從查詢走到接受；Step-45 唯一的季報樣本（8119 Q2）
在 SERP 階段就是 `not_found`。

## 踩到的坑

- **原本以為**可以在整頁文字中找 `公司名稱：`、`主 旨：`。實際上 meta description
  重複本文，「相關新聞」卡片也帶其他公司的同名欄位。改為只讀文章本體。寫測試時
  也踩到同一件事：`text.index("3.財務報告報導期間")` 先找到 meta description 裡的
  那一次，把「刪除文章本體」寫成了「複製內容」，後來改成從本體開頭往後找。
- **原本以為**公司代號是獨立欄位。Yahoo 版本把代號放在 `公司名稱：公信 (8119)`
  的括號裡。
- **原本以為**期間標籤在同一行。友達和頎邦的標籤拆成兩個 `<p>`。
- **原本以為** Q2 期間是 04/01～06/30。實際樣本是累計的 01/01～06/30，Q3 也是
  01/01～09/30。兩種起日都接受。
- **原本以為**有 `【公告】` 標頭的 Yahoo 鏡像都有報導期間欄位。2019 年的樣本
  使用舊版重大訊息格式（事實發生日、發生緣由），沒有這個欄位，因此不被接受。
- 「興櫃：…合併財報…」新聞標題用的是「財報」而非「財務報告」，Step-45 的候選
  篩選本來就不會選中它。在這裡它只作為非 MOPS 形式的解析反例。

## Code review 修正（2026-09-26）

- **代子公司公告**：主旨寫「代子公司…董事會通過…合併財務報告」時，公司名稱、
  代號和期間都是母公司的，原本會通過全部檢查。串接流程裡 Step-45 的公司名稱
  邊界規則碰巧擋下了（`公信代…` 不符邊界），但 Step-46 是接受關卡，必須自己
  擋住。新增 `reporting_entity` 檢查：主旨含 `子公司` 就不接受。
- **跳到其他網站的轉址**：原本 final URL 只要不是 Yahoo 新聞頁就判為
  `not_article_page`（最終判定）。consent 或登入頁擋住所有候選時，task 會被判為
  `rejected`。現在改為：離開 `tw.stock.yahoo.com` 就是 `temporary_error`；仍在
  `tw.stock.yahoo.com` 但不是 `/news/` 的，維持最終判定。不全部改成可重試，是
  因為 Step-27 沒有重試上限，已移除的文章會讓 task 永遠重試。
- 同類問題的另一個位置（未在本 PR 修改）：Step-45 的
  `classify_yahoo_serp_capture()` 遇到 final URL 不是 Yahoo 搜尋頁時會丟出
  `ValueError`，不會被誤判成 `not_found`，但也不會回報成可重試。等實作 Yahoo
  worker 時再一併處理。

## 限制與未完成

- 較早年度的 Yahoo 鏡像可能使用舊格式而一律被拒；只有一個 2019 年樣本，舊格式
  涵蓋哪些年度尚未量測。
- 只支援曆年制公司。
- `announcement_date` 只有日期；MOPS 發言時間與文章發布時間的區分屬 Step-47。
- 文章頁擷取仍是 Step-44 方式的暫存腳本（一般 HTTP 請求）；沒有入庫的文章
  擷取器，也沒有常駐 Yahoo worker、evidence 寫入或 task 狀態更新。
- 多篇被接受的鏡像不做去重或擇一。
