# xbrlswarm — 開發路線圖

## 1. 專案目標

`xbrlswarm` 的目標是建立一套針對台灣上市櫃公司的：

> **歷史財務報告 / XBRL 發布證據 蒐集、驗證與來源追溯系統**

本專案關注的是：

```text
哪一家公司
哪一個 fiscal year / report period
哪一種 report scope
在什麼時間點
透過什麼來源
出現了什麼財報相關 evidence
```

第一版主要處理：

```text
Q1
Q2
Q3
FY
```

其中：

```text
FY != Q4
```

`FY` 代表年度財務報告。

---

# 2. 範圍

本專案負責：

- 研究並取得 MOPS / XBRL 公開資料
- 保存財報文件 / 申報證據
- 搜尋歷史財報公告 證據
- 保存重大訊息發言時間
- 區分財報文件 證據 與 公告證據
- 保存來源 來源追溯資訊
- 保存 原始 / 更正 / 補充證據
- 保存不同來源間的 交叉佐證 / 衝突
- 分散式 任務 lease
- 重試 / 限流 / 失敗處理
- 決定性匯出
- 未解決尾端稽核

本專案不負責：

- EPS / 營收 / 資產 等財報數值分析
- 財務指標 正規化
- 還原股價
- 回測
- 交易策略
- 財務報表投資分析

---

# 3. 核心研究結論

目前已確認：

## 3.1 官方 XBRL 申報系統確實有秒級申報時間

TWSE 申報系統存在：

```text
申報日期
申報時間
檢核結果
確認與否
```

因此「秒級 申報相關時間戳」是真實存在於官方系統的資訊。

但是：

> **目前尚未找到一個公開、可重播、可批次查歷史資料的方式，可以直接取得 歷史 `xbrl_confirmed_at`。**

所以第一版禁止假設：

```text
xbrl_confirmed_at
```

一定能從公開 歷史端點 取得。

---

## 3.2 XBRL 確認 與重大訊息 公告 是不同事件

目前必須分開：

```text
XBRL submission / confirmation
```

與：

```text
MOPS material announcement
```

第三方鏡像 如 Goodinfo / Yahoo / Cnyes 保存的：

```text
發言日期
發言時間
```

應命名為：

```text
announcement_at
```

不能直接命名為：

```text
xbrl_confirmed_at
```

除非未來有正式 證據 證明兩者相同。

---

## 3.3 Yahoo / Goodinfo / Google 可以找到有價值的 公告證據

實測可取得：

```text
stock_id
company_name
fiscal_year
report_period
report_scope
announcement_date
announcement_time
subject
period_start
period_end
board_date
audit_committee_date
source_url
```

但不是每個來源 / 每筆資料都會提供全部欄位。

所有解析器 必須允許 可為空的選用欄位。

---

## 3.4 Goodinfo 可以直接做 歷史公告查詢

Goodinfo 公開頁面可用：

```text
StockAnnounceList.asp
?STOCK_ID=...
&START_DT=...
&END_DT=...
```

直接以：

```text
stock_id
+
date range
```

列歷史公告。

詳細頁面 可提供：

```text
CLAIM_TIME
STOCK_ID
SUBJECT
```

以及公告內容。

因此 Goodinfo 值得成為正式備援 Worker。

---

# 4. 資料來源順序

固定順序：

```text
MOPS
 ↓
Goodinfo
 ↓
Yahoo
 ↓
Google
 ↓
Grounded AI
```

角色：

```text
MOPS
= official financial-report / XBRL evidence

Goodinfo
= structured MOPS announcement mirror

Yahoo
= 歷史 announcement search

Google
= cross-site 歷史 mirror discovery

Grounded AI
= final long-tail recovery
```

---

# 5. 強制 TDD 規則

所有 正式程式碼 必須遵守：

```text
RED
 ↓
GREEN
 ↓
REFACTOR
```

流程：

```text
先寫測試
↓
確認測試失敗
↓
寫最少量 production code
↓
確認測試通過
↓
refactor
↓
重新跑完整 test suite
```

---

## 5.1 禁止先寫程式碼再補測試

以下流程禁止：

```text
先實作
↓
手動確認
↓
再補測試
```

這不算 TDD。

---

## 5.2 每個步驟的標準流程

### 1. 先寫會失敗的測試

先新增適用的：

```text
unit test
integration test
regression test
```

### 2. 確認 RED

失敗原因必須是：

```text
功能尚未實作
```

不能是：

```text
syntax error
broken fixture
wrong import
bad test setup
```

### 3. 實作最小必要程式碼

只寫讓測試通過所需的最少 正式程式碼。

### 4. 確認 GREEN

依序執行：

```text
new tests
related tests
full suite
```

全部通過。

### 5. 重構

只能在 GREEN 狀態下整理。

---

## 5.3 錯誤修正規則

任何錯誤：

```text
先建立 failing regression
↓
確認能重現
↓
修 code
↓
確認 regression pass
↓
跑 full suite
```

---

# 階段 0 — Schema 前的來源探索

## 步驟 0 — 定義研究問題

在定版 Schema 前，先回答：

```text
1. 公開 MOPS/XBRL 能取得哪些欄位？
2. 能否取得 歷史 filing date？
3. 能否取得 歷史 filing time？
4. 能否取得 confirmation timestamp？
5. consolidated / individual 是否都存在？
6. 同公司同季度是否同時有多種 report scope？
7. amendment / correction 如何表示？
8. 是否有穩定 filing identifier？
9. 公開 endpoint 是否有 stable locator？
10. 非曆年制公司的 fiscal calendar 如何取得？
```

---

## 步驟 1 — 建立來源探索案例

固定研究：

```text
2330 台積電
6147 頎邦
4542 科嶠
```

至少包含：

```text
2024 Q1
2024 Q2
2024 Q3
FY
```

並刻意包含：

```text
熱門公司
中等知名公司
冷門上櫃公司
```

---

## 步驟 2 — 擷取原始 MOPS 回應

保存：

```text
tests/fixtures/discovery/mops/
```

可以包含：

```text
HTML
JSON
XBRL / iXBRL metadata
download listing
HTTP headers
```

此步驟不做最終 Schema。

---

## 步驟 3 — 建立欄位可取得性矩陣

建立：

```text
docs/source-field-matrix.md
```

每個欄位標示：

```text
direct
derived
optional
not available
not verified
```

只有：

```text
direct
derived with deterministic rule
```

才能進正式 Schema。

---

## 步驟 4 — 記錄尚未解決的歷史 `confirmed_at`

文件明確寫：

```text
歷史 xbrl_confirmed_at
=
NOT PUBLICLY VERIFIED
```

直到找到：

```text
public
historical
replayable
batch-queryable
```

的來源前，不建立 正式 Schema 的必填欄位。

---

# 階段 1 — 領域契約

## 步驟 5 — 定義報告識別候選方案

先從：

```text
(stock_id, fiscal_year, report_period)
```

開始。

但在 來源探索後確認是否需要：

```text
report_scope
```

如果同一公司同一季度真的同時存在：

```text
consolidated
individual
```

且兩者都要追蹤，任務識別 改為：

```text
(stock_id, fiscal_year, report_period, report_scope)
```

---

## 步驟 6 — 定義報告期別

內部統一：

```text
Q1
Q2
Q3
FY
```

如果 來源使用：

```text
Q4
```

但實際代表年度財報：

```text
source Q4
↓ normalize
FY
```

這個 對應規則 必須有 測試 fixture 與測試。

---

## 步驟 7 — 定義證據類型

至少區分：

```text
xbrl_document
financial_report_document
material_announcement
search_mirror
manual_review
```

不要全部塞進單一：

```text
published_at
```

---

# 階段 2 — 最小 Schema 定版

只有 階段 0 來源探索 完成後才能做。

## 步驟 8 — 建立 task 資料表

至少：

```text
id

stock_id
fiscal_year
report_period
report_scope   # only if research proves needed

state
engine

attempts
fail_count

dispatched_at
worker_id

created_at
updated_at
```

---

## 步驟 9 — 定義 engine 列舉

固定：

```text
mops
goodinfo
yahoo
google
grounded_ai
```

---

## 步驟 10 — 建立 證據資料表

第一版只放已證實可取得 / 可產生欄位：

```text
id
task_id

evidence_type

event_date
event_time
event_precision

source_type
source_endpoint
source_url
source_locator

source_title
source_subject

retrieved_at
raw_payload_hash

filing_kind
verification_state
```

### 注意

禁止預設：

```text
xbrl_confirmed_at NOT NULL
```

---

## 步驟 11 — 可選的解析後 metadata

只有 來源明確提供才填：

```text
period_start
period_end

board_approved_date
audit_committee_date

company_name
```

這些欄位可為空。

---

# 階段 3 — 證據冪等性

## 步驟 12 — 定義邏輯證據識別

只追加不代表每次抓都新增重複資料列。

需要定義：

```text
same task
same source
same source locator
same event
same payload
```

是否是同一邏輯證據。

---

## 步驟 13 — 加入重複資料防護

測試：

```text
crawl once  → 1 logical evidence
crawl twice → still 1 logical evidence
```

真正新的：

```text
amendment
new announcement
different source
```

才新增 證據。

---

## 步驟 14 — 保留修訂歷史

支援：

```text
original
amendment
supplemental
unknown
```

禁止 更正申報覆蓋原始申報。

---

# 階段 4 — 時間語意

## 步驟 15 — 定義 `announcement_at`

當來源明確提供：

```text
發言日期
+
發言時間
```

保存為：

```text
announcement_at
```

或等價的：

```text
event_date
event_time
event_type=material_announcement
```

---

## 步驟 16 — 不得捏造 XBRL 確認時間

禁止：

```text
announcement_at
→ rename
xbrl_confirmed_at
```

禁止：

```text
article time
→ rename
xbrl_confirmed_at
```

禁止：

```text
retrieved_at
→ rename
xbrl_confirmed_at
```

---

## 步驟 17 — 保留時間精度

如果只有日期：

```text
precision = date
```

如果有：

```text
HH:MM:SS
```

則：

```text
precision = second
```

禁止把：

```text
2024-05-10
```

變成：

```text
2024-05-10 00:00:00
```

---

# 階段 5 — 發布時間窗規則

## 步驟 18 — 實作期別邊界

第一版先處理曆年制公司：

```text
Q1 → 03/31
Q2 → 06/30
Q3 → 09/30
FY → 12/31
```

---

## 步驟 19 — 導入法規規則介面

建立：

```text
expected_publication_window(...)
```

輸入：

```text
fiscal_year
report_period
company_class
fiscal_calendar
```

輸出：

```text
earliest_date
latest_date
rule_id
```

---

## 步驟 20 — 對歷史規則進行版本化

規則必須：

```text
valid_from
valid_to
rule_id
```

不得用現行規則驗證所有歷史年度。

---

# 階段 6 — 會計年度曆研究閘門

## 步驟 21 — 研究非曆年制公司

在 全市場任務產生 前確認：

```text
哪些公司不是 12/31 year-end？
歷史上是否變更過 fiscal year-end？
公開來源能否穩定取得？
```

---

## 步驟 22 — 僅在來源已證實時加入會計年度曆

如果能可靠取得，再建模：

```text
fiscal_year_end
```

否則第一版明確限制：

```text
calendar-year companies only
```

不能偷偷套用錯誤 期別邊界。

---

# 階段 7 — 分散式任務伺服器

## 步驟 23 — 實作 Worker API

核心：

```text
POST /lease
POST /result
GET  /stats
GET  /status
GET  /healthz
```

---

## 步驟 24 — 原子化 lease

```text
undone
→
dispatched
```

記錄：

```text
worker_id
dispatched_at
```

兩個 Worker 不得拿到同一任務。

---

## 步驟 25 — 延遲回收 lease

Worker 消失：

```text
dispatched
↓ timeout
undone
```

不需要 背景排程器。

---

# 階段 8 — 全域失敗狀態機

## 步驟 26 — 定義語意耗盡

以下代表目前 engine 已嘗試但沒有可信答案：

```text
not_found
rejected
```

可以：

```text
→ next engine
```

---

## 步驟 27 — 定義可重試的基礎設施失敗

以下不得升級到下一來源：

```text
rate_limited
transport_error
temporary_error
```

必須：

```text
stay on same engine
retry later
```

---

## 步驟 28 — 固定 engine 順序

```text
mops
 ↓
goodinfo
 ↓
yahoo
 ↓
google
 ↓
grounded_ai
 ↓
terminal unresolved
```

---

# 階段 9 — MOPS Worker

## 步驟 29 — 定版 MOPS 測試 fixture

建立：

```text
tests/fixtures/mops/
```

包含：

```text
Q1
Q2
Q3
FY
consolidated
individual if available
amendment
missing result
unexpected layout
```

---

## 步驟 30 — 只解析已證實的欄位

解析器 只能輸出 階段 0 來源欄位矩陣已證實欄位。

禁止因為「應該有」就造欄位。

---

## 步驟 31 — 保存原始回應

已接受的 MOPS 證據至少保存：

```text
raw_payload_hash
```

如果 原始快照政策 開啟：

```text
raw_snapshot_id/path
```

---

## 步驟 32 — MOPS 試點

固定跑：

```text
2330
6147
4542
```

多個 Q1/Q2/Q3/FY。

產出：

```text
docs/mops-pilot-report.md
```

---

## 步驟 33 — MOPS 閘門

只有：

```text
source contract stable
fixtures complete
parser stable
failure semantics stable
pilot audited
```

後才啟用 Goodinfo 備援。

---

# 階段 10 — Goodinfo Worker

Goodinfo 是 MOPS 後第一個備援來源。

## 步驟 34 — 實作公告清單查詢

使用：

```text
StockAnnounceList.asp
STOCK_ID
START_DT
END_DT
```

建立 歷史公告清單。

---

## 步驟 35 — 定義保守搜尋時間窗

例如：

```text
Q1 → Apr ~ May
Q2 → Jul ~ Aug
Q3 → Oct ~ Nov
FY → Jan ~ Mar
```

實際時間窗 必須由 法規規則 決定。

---

## 步驟 36 — 解析清單候選項目

先從清單尋找：

```text
財務報告
第1季 / 第2季 / 第3季
年度
合併 / 個體
```

不要直接接受。

---

## 步驟 37 — 解析詳細頁面

詳細頁面可以抽取：

```text
stock_id
claim_time
subject
period_start
period_end
board_date
audit_committee_date
```

只存頁面實際提供的欄位。

---

## 步驟 38 — 保存 `announcement_at`

如果：

```text
CLAIM_TIME=2024/05/10 14:48:53
```

則：

```text
event_type = material_announcement
event_at   = 2024-05-10 14:48:53
precision  = second
```

不得標成 XBRL 確認。

---

## 步驟 39 — Goodinfo 冪等性

詳細頁 URL / 定位資訊 可用：

```text
STOCK_ID
CLAIM_TIME
SUBJECT
```

作為邏輯證據去重的一部分。

---

## 步驟 40 — Goodinfo 操作防護

Goodinfo 為第三方備援。

要求：

```text
low concurrency
delay
jitter
cache
avoid duplicate date-range queries
```

不要當 大規模主要爬蟲。

---

# 階段 11 — Goodinfo 試點閘門

## 步驟 41 — 試點案例

至少：

```text
4542 科嶠 2024 Q1
6147 頎邦 2024 Q1
2330 台積電 2024 Q1
```

再加入較舊年度：

```text
2022
2020 where possible
```

---

## 步驟 42 — 驗證歷史涵蓋率

量：

```text
exact hit rate
missing-list rate
detail parse rate
seconds precision coverage
```

---

## 步驟 43 — 將所有失敗案例轉成測試 fixture

任何：

```text
wrong year
wrong quarter
wrong scope
HTML change
multiple announcements same day
```

都永久回歸測試。

---

# 階段 12 — Yahoo Worker

## 步驟 44 — 定版 Yahoo 測試 fixture

至少：

```text
valid result
wrong year
wrong quarter
wrong company
wrong scope
no result
rate limit
unexpected page
```

---

## 步驟 45 — Yahoo 查詢建構器

查詢至少包含：

```text
stock_id
company
fiscal_year
report_period
財務報告
```

必要時：

```text
合併
個體
```

---

## 步驟 46 — 優先採用 MOPS 形式的公告鏡像

優先接受包含：

```text
公司代號
公司名稱
主旨
財務報告期間
```

的公告型結果。

---

## 步驟 47 — 區分文章時間與公告時間

如果 Yahoo 頁面只有：

```text
article_published_at
```

不能當：

```text
announcement_at
```

除非內文也有 MOPS 發言時間。

---

# 階段 13 — Google Worker

## 步驟 48 — 跨站鏡像探索

Google 用來找：

```text
Goodinfo
Cnyes
MoneyDJ
Yahoo
other MOPS mirrors
```

---

## 步驟 49 — 各來源專用解析器

若網域是：

```text
goodinfo.tw
```

用 Goodinfo 解析器。

若是：

```text
cnyes.com
```

用 Cnyes 解析器。

不要全部只靠 通用摘要解析器。

---

## 步驟 50 — 重用共用驗證

Google 候選結果必須通過：

```text
stock/company match
year match
report period match
scope match if present
publication window
financial-report intent
```

---

# 階段 14 — Grounded AI 備援

## 步驟 51 — 要求可追溯依據

模型結果必須有：

```text
traceable source
```

不能只因模型回答了一個日期就接受。

---

## 步驟 52 — 分離來源證據與模型主張

```text
來源表示 X
```

與：

```text
模型表示 X
```

必須分開保存。

---

## 步驟 53 — 終止於未解決狀態

Grounded AI 仍無可信來源：

```text
terminal unresolved
```

不要造資料補洞。

---

# 階段 15 — 證據驗證

## 步驟 54 — 驗證狀態

至少：

```text
unverified
corroborated
conflicted
rejected
manual_review
resolved
```

---

## 步驟 55 — 來源獨立性

兩個 URL 不代表兩個獨立來源。

例如：

```text
Goodinfo
Cnyes
```

若只是同一筆 MOPS 重大訊息鏡像：

```text
same upstream event
```

只能算：

```text
same event corroborated by mirrors
```

不能誤認為兩個不同 申報事件。

---

## 步驟 56 — 保留衝突

若：

```text
source A ≠ source B
```

保存：

```text
conflicted
```

禁止覆蓋。

---

# 階段 16 — 人工裁決

## 步驟 57 — 人工審查資料表

保存：

```text
reviewer
decision
reason
reviewed_at
```

---

## 步驟 58 — 永不修改來源證據

人工決策：

```text
resolution record
```

不是：

```text
UPDATE original evidence
```

---

# 階段 17 — 匯出

## 步驟 59 — 定義 JSONL 匯出

例如：

```json
{
  "stock_id": "4542",
  "fiscal_year": 2024,
  "report_period": "Q1",
  "report_scope": "consolidated",
  "evidence_type": "material_announcement",
  "event_at": "2024-05-10T14:48:53+08:00",
  "event_precision": "second",
  "source_type": "goodinfo",
  "source_url": "...",
  "verification_state": "corroborated"
}
```

---

## 步驟 60 — 決定性匯出

相同 資料庫狀態：

```text
export twice
```

必須 逐位元組完全一致。

---

## 步驟 61 — 不得捏造統一的 published_at

匯出時不要硬塞：

```text
published_at
```

除非證據類型已定義該時間的事件語意。

---

# 階段 18 — 全市場任務產生

## 步驟 62 — 建立歷史股票集合

不能只使用：

```text
currently listed companies
```

需要歷史股票集合。

---

## 步驟 63 — 尊重上市櫃生命週期

避免產生公司尚未上市櫃時期的 task。

---

## 步驟 64 — 套用會計年度曆閘門

非曆年制公司如果尚未建模：

```text
skip
or
mark unsupported
```

不能用錯誤 季度邊界。

---

## 步驟 65 — 以冪等方式產生任務

重跑：

```text
same task count
no duplicates
```

---

# 階段 19 — 維運

## 步驟 66 — `/stats`

至少：

```text
by_state
by_engine
by_year
by_period
success rate
retryable failures
terminal unresolved
```

---

## 步驟 67 — `/status`

人類可讀：

```text
MOPS queue
Goodinfo queue
Yahoo queue
Google queue
Grounded AI queue
recent throughput
```

---

## 步驟 68 — `/healthz`

只代表：

```text
server alive
```

---

# 階段 20 — 失敗復原

## 步驟 69 — 伺服器重啟測試

確認：

```text
completed tasks preserved
lease recovered
engine preserved
fail_count preserved
```

---

## 步驟 70 — Worker 消失測試

```text
lease
↓
worker dies
↓
lease expires
↓
task returns undone
```

---

## 步驟 71 — 重複結果重試測試

網路重試 不得造成：

```text
duplicate logical evidence
wrong state transition
wrong fail_count
```

---

# 階段 21 — 未解決尾端稽核

## 步驟 72 — 產生未解決報告

產出：

```text
docs/unresolved-report.md
```

分類：

```text
MOPS exhausted
Goodinfo exhausted
Yahoo exhausted
Google exhausted
AI unresolved
source conflict
manual review required
unsupported fiscal calendar
```

---

## 步驟 73 — 將真實失敗轉成回歸測試

任何 正式環境失敗：

```text
fixture
↓
failing regression
↓
fix
↓
permanent test
```

---

# 階段 22 — 效能

只有 正確性 穩定後才優化。

## 步驟 74 — 建立基準線

記錄：

```text
tasks/minute
MOPS success rate
Goodinfo recovery rate
Yahoo recovery rate
Google recovery rate
AI recovery rate
rate-limit rate
average attempts/task
terminal unresolved rate
```

---

## 步驟 75 — 保守調校 Goodinfo

只調：

```text
delay
jitter
cache
date-window size
```

不要用暴力 併發。

---

## 步驟 76 — 驗證 SQLite

先量：

```text
WAL
busy timeout
DB size
transaction duration
write contention
```

有實際瓶頸才考慮更重的 基礎設施。

---

# 完成定義

第一個穩定版本完成條件：

```text
✓ source discovery completed before schema freeze

✓ public 歷史 xbrl_confirmed_at status explicitly documented

✓ strict TDD workflow

✓ task identity validated against real MOPS data

✓ report_scope included only if proven necessary

✓ evidence idempotency

✓ append-only revisions

✓ time semantics separated by event type

✓ 歷史 regulation rules versioned

✓ MOPS worker

✓ MOPS pilot audited

✓ Goodinfo worker as first fallback

✓ Goodinfo low-volume operational guard

✓ Yahoo fallback

✓ Google cross-site fallback

✓ grounded AI final fallback

✓ retryable failure != semantic exhaustion

✓ source provenance preserved

✓ raw payload hash preserved

✓ verification / conflict handling

✓ manual adjudication

✓ deterministic JSONL export

✓ fiscal-calendar gate before full market

✓ restart / resume tested

✓ unresolved tail report
```

---

# 不可妥協規則

## 規則 1 — 測試先於程式碼

```text
NO FAILING TEST
=
NO PRODUCTION CODE
```

---

## 規則 2 — 真實來源先於 Schema

```text
NO PROVEN SOURCE FIELD
=
NO REQUIRED PRODUCTION COLUMN
```

---

## 規則 3 — 絕不捏造 XBRL 確認時間

```text
announcement_at
article_time
retrieved_at
HTTP Last-Modified
```

都不能自動等同：

```text
xbrl_confirmed_at
```

---

## 規則 4 — 資料來源順序

```text
MOPS
 ↓
Goodinfo
 ↓
Yahoo
 ↓
Google
 ↓
Grounded AI
```

---

## 規則 5 — 可重試錯誤留在同一 engine

```text
rate_limited
transport_error
temporary_error
```

不得直接 升級到下一來源。

---

## 規則 6 — 未知不等於不存在

```text
查不到
```

不等於：

```text
不存在
```

---

## 規則 7 — 證據只能追加

```text
new evidence
amendment
correction
new mirror
```

不得覆蓋歷史證據。

---

## 規則 8 — 重複抓取不是新證據

同一邏輯證據重抓：

```text
dedupe
```

不是：

```text
INSERT another duplicate row
```

---

## 規則 9 — 第三方鏡像不是官方真值

Goodinfo / Yahoo / Google：

```text
valuable evidence
```

但仍須保留：

```text
source_type
source_url
source_locator
```

---

## 規則 10 — 正式環境失敗必須成為永久測試

```text
real failure
↓
fixture
↓
RED
↓
fix
↓
GREEN
```

---

# 建議開發順序

```text
階段 0   Discovery Before Schema
  ↓
階段 1   領域契約
  ↓
階段 2   最小 Schema 定版
  ↓
階段 3   證據冪等性
  ↓
階段 4   時間語意
  ↓
階段 5   發布時間窗規則
  ↓
階段 6   會計年度曆研究閘門
  ↓
階段 7   分散式伺服器
  ↓
階段 8   全域失敗狀態機
  ↓
階段 9   MOPS Worker
  ↓
──────────── MOPS Gate ────────────
  ↓
階段 10  Goodinfo Worker
  ↓
階段 11  Goodinfo 試點
  ↓
階段 12  Yahoo Worker
  ↓
階段 13  Google Worker
  ↓
階段 14  Grounded AI
  ↓
階段 15  證據驗證
  ↓
階段 16  人工裁決
  ↓
階段 17  匯出
  ↓
階段 18  全市場任務
  ↓
階段 19  維運
  ↓
階段 20  失敗復原
  ↓
階段 21  未解決尾端稽核
  ↓
階段 22  效能
```

---

# 里程碑 1 — 來源契約

必須能回答：

```text
MOPS 公開端到底能取得哪些欄位？
哪些欄位拿不到？
哪些只有申報端存在？
哪些只能從第三方 announcement mirror 取得？
```

---

# 里程碑 2 — 冷門股票公告回復能力

至少用：

```text
4542 科嶠
6147 頎邦
```

證明：

```text
Goodinfo
↓
stock_id + date range
↓
歷史 announcement
↓
second-level announcement_at
```

可以穩定工作。

---

# 里程碑 3 — 語意分離

必須證明資料庫不會混淆：

```text
XBRL document evidence
MOPS material announcement
Yahoo article timestamp
crawler retrieved_at
```

---

# 里程碑 4 — 完整歷史資料回復能力

必須可以量化：

```text
MOPS resolved
Goodinfo recovered
Yahoo recovered
Google recovered
AI recovered
terminal unresolved
manual review
```

每一層 回復率 都要能獨立統計。
