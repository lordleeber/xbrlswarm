# xbrlswarm — ROADMAP

## 1. Project Goal

`xbrlswarm` 的目標是建立一套針對台灣上市櫃公司的：

> **歷史財務報告 / XBRL publication evidence 蒐集、驗證與來源追溯系統**

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

# 2. Scope

本專案負責：

- 研究並取得 MOPS / XBRL 公開資料
- 保存財報文件 / filing evidence
- 搜尋歷史財報公告 evidence
- 保存重大訊息發言時間
- 區分財報文件 evidence 與 announcement evidence
- 保存來源 provenance
- 保存 original / amendment / supplemental evidence
- 保存不同來源間的 corroboration / conflict
- 分散式 task leasing
- retry / rate-limit / failure handling
- deterministic export
- unresolved tail audit

本專案不負責：

- EPS / revenue / assets 等財報數值分析
- 財務指標 canonicalization
- adjusted price
- backtesting
- trading strategy
- 財務報表投資分析

---

# 3. Core Research Conclusions

目前已確認：

## 3.1 官方 XBRL 申報系統確實有秒級申報時間

TWSE 申報系統存在：

```text
申報日期
申報時間
檢核結果
確認與否
```

因此「秒級 filing-related timestamp」是真實存在於官方系統的資訊。

但是：

> **目前尚未找到一個公開、可重播、可批次查歷史資料的方式，可以直接取得 historical `xbrl_confirmed_at`。**

所以第一版禁止假設：

```text
xbrl_confirmed_at
```

一定能從公開 historical endpoint 取得。

---

## 3.2 XBRL confirmation 與重大訊息 announcement 是不同事件

目前必須分開：

```text
XBRL submission / confirmation
```

與：

```text
MOPS material announcement
```

第三方 mirror 如 Goodinfo / Yahoo / Cnyes 保存的：

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

除非未來有正式 evidence 證明兩者相同。

---

## 3.3 Yahoo / Goodinfo / Google 可以找到有價值的 announcement evidence

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

所有 parser 必須允許 nullable optional fields。

---

## 3.4 Goodinfo 可以直接做 historical announcement lookup

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

Detail page 可提供：

```text
CLAIM_TIME
STOCK_ID
SUBJECT
```

以及公告內容。

因此 Goodinfo 值得成為正式 fallback worker。

---

# 4. Source Order

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
= historical announcement search

Google
= cross-site historical mirror discovery

Grounded AI
= final long-tail recovery
```

---

# 5. Mandatory TDD Rule

所有 production code 必須遵守：

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

## 5.1 禁止先寫 code 再補 test

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

## 5.2 每個 Step 的標準流程

### 1. Write failing test

先新增適用的：

```text
unit test
integration test
regression test
```

### 2. Confirm RED

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

### 3. Implement minimum code

只寫讓測試通過所需的最少 production code。

### 4. Confirm GREEN

依序執行：

```text
new tests
related tests
full suite
```

全部通過。

### 5. Refactor

只能在 GREEN 狀態下整理。

---

## 5.3 Bug fix rule

任何 bug：

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

# Phase 0 — Discovery Before Schema

## Step 0 — Define research questions

在 freeze schema 前，先回答：

```text
1. 公開 MOPS/XBRL 能取得哪些欄位？
2. 能否取得 historical filing date？
3. 能否取得 historical filing time？
4. 能否取得 confirmation timestamp？
5. consolidated / individual 是否都存在？
6. 同公司同季度是否同時有多種 report scope？
7. amendment / correction 如何表示？
8. 是否有穩定 filing identifier？
9. 公開 endpoint 是否有 stable locator？
10. 非曆年制公司的 fiscal calendar 如何取得？
```

---

## Step 1 — Create discovery cases

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

## Step 2 — Capture raw MOPS responses

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

此 Step 不做 final schema。

---

## Step 3 — Build field availability matrix

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

才能進 production schema。

---

## Step 4 — Record unresolved historical confirmed_at

文件明確寫：

```text
historical xbrl_confirmed_at
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

的來源前，不建立 required production column。

---

# Phase 1 — Domain Contract

## Step 5 — Define report identity candidate

先從：

```text
(stock_id, fiscal_year, report_period)
```

開始。

但在 discovery 後確認是否需要：

```text
report_scope
```

如果同一公司同一季度真的同時存在：

```text
consolidated
individual
```

且兩者都要追蹤，task identity 改為：

```text
(stock_id, fiscal_year, report_period, report_scope)
```

---

## Step 6 — Define report period

內部統一：

```text
Q1
Q2
Q3
FY
```

如果 source 使用：

```text
Q4
```

但實際代表年度財報：

```text
source Q4
↓ normalize
FY
```

這個 mapping 必須有 fixture + test。

---

## Step 7 — Define evidence types

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

# Phase 2 — Minimal Schema Freeze

只有 Phase 0 discovery 完成後才能做。

## Step 8 — Create tasks table

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

## Step 9 — Define engine enum

固定：

```text
mops
goodinfo
yahoo
google
grounded_ai
```

---

## Step 10 — Create evidence table

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

## Step 11 — Optional parsed metadata

只有 source 明確提供才填：

```text
period_start
period_end

board_approved_date
audit_committee_date

company_name
```

這些欄位 nullable。

---

# Phase 3 — Evidence Idempotency

## Step 12 — Define logical evidence identity

Append-only 不代表每次抓都新增重複 row。

需要定義：

```text
same task
same source
same source locator
same event
same payload
```

是否是同一 logical evidence。

---

## Step 13 — Add duplicate protection

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

才新增 evidence。

---

## Step 14 — Preserve revisions

支援：

```text
original
amendment
supplemental
unknown
```

禁止 amendment overwrite original。

---

# Phase 4 — Time Semantics

## Step 15 — Define `announcement_at`

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

## Step 16 — Do not invent XBRL confirmation time

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

## Step 17 — Preserve precision

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

# Phase 5 — Publication Window Rules

## Step 18 — Implement period boundaries

calendar-year 第一版：

```text
Q1 → 03/31
Q2 → 06/30
Q3 → 09/30
FY → 12/31
```

---

## Step 19 — Introduce regulation-rule interface

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

## Step 20 — Version historical rules

規則必須：

```text
valid_from
valid_to
rule_id
```

不得用現行規則驗證所有歷史年度。

---

# Phase 6 — Fiscal Calendar Research Gate

## Step 21 — Research non-calendar-year companies

在 full-market task generation 前確認：

```text
哪些公司不是 12/31 year-end？
歷史上是否變更過 fiscal year-end？
公開來源能否穩定取得？
```

---

## Step 22 — Add fiscal calendar only if source is proven

如果能可靠取得，再 model：

```text
fiscal_year_end
```

否則第一版明確限制：

```text
calendar-year companies only
```

不能偷偷套用錯誤 period boundary。

---

# Phase 7 — Distributed Task Server

## Step 23 — Implement worker API

核心：

```text
POST /lease
POST /result
GET  /stats
GET  /status
GET  /healthz
```

---

## Step 24 — Atomic lease

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

兩個 worker 不得拿到同一 task。

---

## Step 25 — Lazy lease reclaim

worker 消失：

```text
dispatched
↓ timeout
undone
```

不需要 background scheduler。

---

# Phase 8 — Global Failure State Machine

## Step 26 — Define semantic exhaustion

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

## Step 27 — Define retryable infrastructure failures

以下不得 escalation：

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

## Step 28 — Fixed engine order

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

# Phase 9 — MOPS Worker

## Step 29 — Freeze MOPS fixtures

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

## Step 30 — Parse only proven fields

Parser 只能輸出 Phase 0 source-field-matrix 已證實欄位。

禁止因為「應該有」就造欄位。

---

## Step 31 — Preserve raw response

accepted MOPS evidence 至少保存：

```text
raw_payload_hash
```

如果 raw snapshot policy 開啟：

```text
raw_snapshot_id/path
```

---

## Step 32 — MOPS pilot

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

## Step 33 — MOPS gate

只有：

```text
source contract stable
fixtures complete
parser stable
failure semantics stable
pilot audited
```

後才啟用 Goodinfo fallback。

---

# Phase 10 — Goodinfo Worker

Goodinfo 是 MOPS 後第一個 fallback。

## Step 34 — Implement announcement-list lookup

使用：

```text
StockAnnounceList.asp
STOCK_ID
START_DT
END_DT
```

建立 historical announcement list。

---

## Step 35 — Define conservative search window

例如：

```text
Q1 → Apr ~ May
Q2 → Jul ~ Aug
Q3 → Oct ~ Nov
FY → Jan ~ Mar
```

實際 window 必須由 regulation rules 決定。

---

## Step 36 — Parse list candidates

先從 list 找：

```text
財務報告
第1季 / 第2季 / 第3季
年度
合併 / 個體
```

不要直接接受。

---

## Step 37 — Parse detail page

Detail 可以抽：

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

## Step 38 — Save `announcement_at`

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

不得標成 XBRL confirmation。

---

## Step 39 — Goodinfo idempotency

Detail URL / locator 可用：

```text
STOCK_ID
CLAIM_TIME
SUBJECT
```

做 logical evidence dedupe 的一部分。

---

## Step 40 — Goodinfo operational guard

Goodinfo 為第三方 fallback。

要求：

```text
low concurrency
delay
jitter
cache
avoid duplicate date-range queries
```

不要當 massive primary crawler。

---

# Phase 11 — Goodinfo Pilot Gate

## Step 41 — Pilot cases

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

## Step 42 — Validate historical coverage

量：

```text
exact hit rate
missing-list rate
detail parse rate
seconds precision coverage
```

---

## Step 43 — Turn all failures into fixtures

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

# Phase 12 — Yahoo Worker

## Step 44 — Freeze Yahoo fixtures

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

## Step 45 — Yahoo query builder

query 至少包含：

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

## Step 46 — Prefer MOPS-style announcement mirrors

優先接受包含：

```text
公司代號
公司名稱
主旨
財務報告期間
```

的公告型結果。

---

## Step 47 — Distinguish article time from announcement time

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

# Phase 13 — Google Worker

## Step 48 — Cross-site mirror discovery

Google 用來找：

```text
Goodinfo
Cnyes
MoneyDJ
Yahoo
other MOPS mirrors
```

---

## Step 49 — Source-specific parsers

若 domain 是：

```text
goodinfo.tw
```

用 Goodinfo parser。

若是：

```text
cnyes.com
```

用 Cnyes parser。

不要全部只靠 generic snippet parser。

---

## Step 50 — Reuse shared validation

Google candidate 必須通過：

```text
stock/company match
year match
report period match
scope match if present
publication window
financial-report intent
```

---

# Phase 14 — Grounded AI Fallback

## Step 51 — Require grounding

模型結果必須有：

```text
traceable source
```

不能只因模型回答了一個日期就接受。

---

## Step 52 — Separate source evidence from model claim

```text
source says X
```

與：

```text
model says X
```

必須分開保存。

---

## Step 53 — Terminal unresolved

Grounded AI 仍無可信 source：

```text
terminal unresolved
```

不要造資料補洞。

---

# Phase 15 — Evidence Verification

## Step 54 — Verification states

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

## Step 55 — Source independence

兩個 URL 不代表兩個獨立來源。

例如：

```text
Goodinfo
Cnyes
```

若只是同一筆 MOPS 重大訊息 mirror：

```text
same upstream event
```

只能算：

```text
same event corroborated by mirrors
```

不能誤認為兩個不同 filing event。

---

## Step 56 — Preserve conflicts

若：

```text
source A ≠ source B
```

保存：

```text
conflicted
```

禁止 overwrite。

---

# Phase 16 — Manual Adjudication

## Step 57 — Manual review table

保存：

```text
reviewer
decision
reason
reviewed_at
```

---

## Step 58 — Never mutate source evidence

人工決策：

```text
resolution record
```

不是：

```text
UPDATE original evidence
```

---

# Phase 17 — Export

## Step 59 — Define JSONL export

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

## Step 60 — Deterministic export

相同 DB state：

```text
export twice
```

必須 byte-for-byte identical。

---

## Step 61 — Do not fake unified published_at

Export 不要硬塞：

```text
published_at
```

除非 evidence type 已定義該時間的 event semantics。

---

# Phase 18 — Full-Market Task Generation

## Step 62 — Build historical stock universe

不能只使用：

```text
currently listed companies
```

需要歷史 universe。

---

## Step 63 — Respect listing lifecycle

避免產生公司尚未上市櫃時期的 task。

---

## Step 64 — Apply fiscal-calendar gate

非曆年制公司如果尚未 model：

```text
skip
or
mark unsupported
```

不能用錯誤 quarter boundary。

---

## Step 65 — Generate tasks idempotently

rerun：

```text
same task count
no duplicates
```

---

# Phase 19 — Operations

## Step 66 — `/stats`

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

## Step 67 — `/status`

human-readable：

```text
MOPS queue
Goodinfo queue
Yahoo queue
Google queue
Grounded AI queue
recent throughput
```

---

## Step 68 — `/healthz`

只代表：

```text
server alive
```

---

# Phase 20 — Failure Recovery

## Step 69 — Server restart test

確認：

```text
completed tasks preserved
lease recovered
engine preserved
fail_count preserved
```

---

## Step 70 — Worker disappearance test

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

## Step 71 — Duplicate-result retry test

network retry 不得造成：

```text
duplicate logical evidence
wrong state transition
wrong fail_count
```

---

# Phase 21 — Unresolved Tail Audit

## Step 72 — Generate unresolved report

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

## Step 73 — Convert real failures into regression tests

任何 production failure：

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

# Phase 22 — Performance

只有 correctness 穩定後才優化。

## Step 74 — Establish baseline

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

## Step 75 — Tune Goodinfo conservatively

只調：

```text
delay
jitter
cache
date-window size
```

不要用暴力 concurrency。

---

## Step 76 — Validate SQLite

先量：

```text
WAL
busy timeout
DB size
transaction duration
write contention
```

有實際瓶頸才考慮更重的 infrastructure。

---

# Definition of Done

第一個穩定版本完成條件：

```text
✓ source discovery completed before schema freeze

✓ public historical xbrl_confirmed_at status explicitly documented

✓ strict TDD workflow

✓ task identity validated against real MOPS data

✓ report_scope included only if proven necessary

✓ evidence idempotency

✓ append-only revisions

✓ time semantics separated by event type

✓ historical regulation rules versioned

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

# Non-Negotiable Rules

## Rule 1 — Test before code

```text
NO FAILING TEST
=
NO PRODUCTION CODE
```

---

## Rule 2 — Real source before schema

```text
NO PROVEN SOURCE FIELD
=
NO REQUIRED PRODUCTION COLUMN
```

---

## Rule 3 — Never fabricate XBRL confirmation time

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

## Rule 4 — Source order

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

## Rule 5 — Retryable error stays on same engine

```text
rate_limited
transport_error
temporary_error
```

不得直接 escalation。

---

## Rule 6 — Unknown != absent

```text
查不到
```

不等於：

```text
不存在
```

---

## Rule 7 — Evidence is append-only

```text
new evidence
amendment
correction
new mirror
```

不得 overwrite historical evidence。

---

## Rule 8 — Duplicate crawl is not new evidence

同一 logical evidence 重抓：

```text
dedupe
```

不是：

```text
INSERT another duplicate row
```

---

## Rule 9 — Third-party mirror is not official truth

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

## Rule 10 — Production failures become permanent tests

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

# Recommended Development Order

```text
Phase 0   Discovery Before Schema
  ↓
Phase 1   Domain Contract
  ↓
Phase 2   Minimal Schema Freeze
  ↓
Phase 3   Evidence Idempotency
  ↓
Phase 4   Time Semantics
  ↓
Phase 5   Publication Window Rules
  ↓
Phase 6   Fiscal Calendar Research Gate
  ↓
Phase 7   Distributed Server
  ↓
Phase 8   Global Failure State Machine
  ↓
Phase 9   MOPS Worker
  ↓
──────────── MOPS Gate ────────────
  ↓
Phase 10  Goodinfo Worker
  ↓
Phase 11  Goodinfo Pilot
  ↓
Phase 12  Yahoo Worker
  ↓
Phase 13  Google Worker
  ↓
Phase 14  Grounded AI
  ↓
Phase 15  Evidence Verification
  ↓
Phase 16  Manual Adjudication
  ↓
Phase 17  Export
  ↓
Phase 18  Full-Market Tasks
  ↓
Phase 19  Operations
  ↓
Phase 20  Failure Recovery
  ↓
Phase 21  Unresolved Tail Audit
  ↓
Phase 22  Performance
```

---

# Milestone 1 — Source Contract

必須能回答：

```text
MOPS 公開端到底能取得哪些欄位？
哪些欄位拿不到？
哪些只有申報端存在？
哪些只能從第三方 announcement mirror 取得？
```

---

# Milestone 2 — Cold-Stock Announcement Recovery

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
historical announcement
↓
second-level announcement_at
```

可以穩定工作。

---

# Milestone 3 — Semantic Separation

必須證明資料庫不會混淆：

```text
XBRL document evidence
MOPS material announcement
Yahoo article timestamp
crawler retrieved_at
```

---

# Milestone 4 — Full Historical Recovery

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

每一層 recovery rate 都要能獨立統計。
