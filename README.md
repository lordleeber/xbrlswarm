# xbrlswarm

`xbrlswarm` 用來蒐集、保存與稽核台灣上市櫃公司的歷史財務報告 / XBRL 發布證據。

目前已實作 **Step-40：Goodinfo 操作防護**及 **Step-44：Yahoo 測試 fixture**；本環境的 Goodinfo 即時請求遇到 403 challenge，歷史清單與詳細頁仍待實際擷取驗證。Step-44 固定五篇真實 Yahoo 財報公告鏡像及異常案例，來源與限制見 [Yahoo fixture 說明](tests/fixtures/yahoo/README.md)；Yahoo 查詢及 worker 尚未實作。Repository 也保存 2330 / 6147 / 4542 × 2024 Q1/Q2/Q3/FY 共 12 個從官方 MOPS XBRL 下載介面實際擷取的 raw fixtures，並以可重播分析器產生逐筆欄位 observation 與 evidence-backed matrix。

Step-3 證實 `stock_id`、公司中文全名、`fiscal_year`、`report_scope` 可由 iXBRL fact 直接取得，`report_period` 與 `source_locator` 可由已測試規則決定性推導。本次 download endpoint 的 12 個 payload 未觀察到 filing identifier、filing date/time 或 filing kind，但不能外推成整體 MOPS 來源不可得；這些欄位與公開歷史 `xbrl_confirmed_at` 均維持 **NOT PUBLICLY VERIFIED**。

## 資料來源順序

專案依照 ROADMAP 固定使用以下來源順序：

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

MOPS 是官方來源。第三方來源只能作為證據或備援，不能取代官方來源的事實基礎。

正式 engine enum 為 `mops`、`goodinfo`、`yahoo`、`google` 與 `grounded_ai`，已同時套用於 Python domain 與 `task.engine` SQLite constraint。詳細契約見 `docs/engines.md`。

## 證據類型

正式 evidence types 為 `xbrl_document`、`financial_report_document`、`material_announcement`、`search_mirror` 與 `manual_review`。Evidence type、來源、驗證狀態、事件時間及 `retrieved_at` 是不同維度，不使用單一 `published_at` 混合不同時間語意。詳細契約見 `docs/evidence-types.md`。

## 時間語意

XBRL 申報 / 確認事件與 MOPS 重大訊息公告是不同事件。第三方來源的 `announcement_at`、文章發布時間、爬蟲的 `retrieved_at` 或 HTTP header，都不能在沒有來源證據證明其語意相同的情況下改名為 `xbrl_confirmed_at`。

目前將公開歷史 `xbrl_confirmed_at` 視為 **尚未由公開來源驗證（NOT PUBLICLY VERIFIED）**。只有來源同時具備公開存取、歷史資料、可重播及可批次查詢能力，且其事件語意可稽核，才會重新評估此狀態；完整契約見 `docs/historical-xbrl-confirmed-at.md`。

Step-16 將上述禁止替代規則寫入機器可讀契約，並以 regression tests 保護公告映射、
source matrix 與 production schema 的邊界。詳見 `docs/no-fabricated-xbrl-time.md`。

Step-17 明定只含日期的事件保存為 `event_precision=date`、`event_time=NULL`；
只有來源明確提供 `HH:MM:SS` 才保存 `event_precision=second`，不補虛構的午夜。
詳見 `docs/event-time-precision.md`。

## 報告期別

第一版使用：

```text
Q1
Q2
Q3
FY
```

`FY` 代表年度財務報告，`FY != Q4`。

內部 domain enum 不接受 Q4。MOPS 來源的 `Quarter=4`／Q4 filename 經來源專用規則正規化為 FY，原始來源值仍保留在 observation artifact；此規則不會自動套用到其他來源。詳細契約見 `docs/report-period.md`。

對已確認採曆年制的公司，Step-18 提供 Q1→03/31、Q2→06/30、Q3→09/30、
FY→12/31 的期末日期計算。這不是來源聲稱的 evidence `period_end`，也不是
法定發布截止日；詳見 `docs/calendar-year-period-boundaries.md`。

Step-19 提供 `expected_publication_window(...)` 規則介面，輸入年度、期別、
公司類別與會計年度曆，輸出最早／最晚日期及 `rule_id`。目前沒有內建法規日期；
找不到經驗證的規則時會拒絕推測。詳見 `docs/publication-window-interface.md`。

Step-20 為規則加入 `valid_from`／`valid_to`／`rule_id` 版本資訊，缺少適用的歷史
版本時不套用現行規則。選版日期的語意必須由未來的來源證據明確指定；目前仍
沒有內建實際法規日期。詳見 `docs/versioned-publication-rules.md`。

Step-21 確認 2013 年官方文件曾描述申報工具支援非曆年制、會與 MOPS 的會計年度
設定勾稽；**現行工具與欄位仍未驗證**，也尚未取得可重播的公司別歷史值、全市場
清單或穩定批次來源。全市場與非曆年制任務產生維持暫緩；
不能因資料未知就套用 12/31 邊界。詳見 `docs/fiscal-calendar-research.md`。

Step-22 因來源尚未證實，選擇第一版 **calendar-year companies only**，並要求
排程前先有該公司及歷史期間採曆年制的來源證據；unknown／非曆年制不得套用
曆年制邊界。未加入 `fiscal_year_end` production 欄位或非曆年制算法。
詳見 `docs/fiscal-calendar-eligibility.md`。

Step-23 提供 `POST /lease`、`POST /result`、`GET /stats`、`GET /status` 與
`GET /healthz`。可用 `xbrlswarm-worker-api --database <已 migration 的 SQLite 檔>`
在 loopback 啟動；目前支援成功、語意耗盡與可重試基礎設施失敗回報，不含 evidence 上傳，
**不可直接公開部署**。詳見 `docs/worker-api.md`。

Step-24 將 lease 派發收斂為 SQLite 交易中的條件式更新；並行 worker 不得取得
同一 task 的同一次 lease，`worker_id`、`dispatched_at`、`attempts` 與 `updated_at`
一起寫入或一起回滾。詳見 `docs/atomic-task-lease.md`。

Step-25 在 `/lease` 請求內回收逾期租約，預設期限 300 秒，並保留
`attempts` 以拒絕舊結果；`/result` 也拒絕逾期回報。詳見
`docs/lazy-lease-recovery.md`。

Step-26 定義 `not_found` 與 `rejected` 為目前 engine 沒有可信答案的結果；
`/result` 將其保存為 task state；後續來源 gate 通過後才依 Step-28 順序轉移。
詳見 `docs/semantic-exhaustion.md`。

Step-27 定義 `rate_limited`、`transport_error`、`temporary_error` 為可重試失敗。
任務留在同一 engine，預設等待 60 秒後由 `/lease` 再次派發；等待期限保存於
`retry_at`。詳見 `docs/retryable-failures.md`。

Step-28 固定 `mops → goodinfo → yahoo → google → grounded_ai`；Step-33
通過後，MOPS 語意耗盡的 task 可在下次 lease 轉至 Goodinfo；其他跨來源
轉移等待後續 gate。已有的
`grounded_ai` task 耗盡時成為 `terminal_unresolved`。
詳見 `docs/engine-fallback.md`。

Step-29 在 `tests/fixtures/mops/` 固定 Q1／Q2／Q3／FY 合併報告、官方更正及
個體財報更正的清單／明細／PDF 附件、查無資料和非 XBRL 錯誤頁。個體 XBRL
文件尚未取得，詳見該目錄的 README 與 `docs/step-29-acceptance.md`。

Step-30 的 MOPS parser 只輸出來源矩陣已驗證的身份、期別、範圍和來源位置；
未知申報欄位與非 XBRL 回應會被拒絕。詳見 `docs/step-30-acceptance.md`。

Step-31 接受 MOPS evidence 時保存原始 response 的 SHA-256；開啟快照政策時
另存原始 bytes 和內容定址路徑。詳見 `docs/step-31-acceptance.md`。

Step-32 對 2330、6147、4542 的 2024 Q1／Q2／Q3／FY 執行官方 MOPS 即時
試點；逐筆結果與限制見 `docs/mops-pilot-report.md`。

Step-33 稽核來源契約、fixture、parser、失敗語意與試點後，只開放
`mops → goodinfo` 的語意耗盡轉移。Goodinfo 查詢與解析由後續步驟提供；
驗收範圍和未驗證事項見 `docs/step-33-acceptance.md`。

Step-34 提供明確公司代號與日期範圍的 Goodinfo 公告清單 GET 查詢，保存原始
HTML 與擷取 metadata；本環境的即時請求遇到 403 challenge，尚無真實歷史
清單 fixture。候選列解析見 Step-36，詳細頁面擷取與解析見 Step-37。
詳見 `docs/step-34-acceptance.md`。

Step-35 根據可追溯的《證券交易法》第 36 條歷史版本，對**已確認適用一般規則
且採曆年制的 2024 會計年度**，產生期末翌日至一般公告申報期限的 Goodinfo
查詢區間；其他範圍須提供已驗證規則，不能從範例月份推測。詳見
`docs/step-35-acceptance.md`。

Step-36 從原始清單擷取同公司、查詢日期內的財務報告詳細頁連結，保留
期別與合併／個體字樣作為候選提示（「個別」歸一為「個體」，上半年度提示 Q2）；
預計召開公告會標記待審，不寫入
evidence。真實 Goodinfo DOM 尚未在本環境擷取驗證，詳見
`docs/step-36-acceptance.md`。

Step-37 擷取並解析 Goodinfo 公告詳細頁，核對公司及發言時間，保留原始回應
與來源 hash；只有頁面明示的報導期間、董事會與審計委員會日期才填入結果。
本步驟不寫入 evidence 或 task，詳見 `docs/step-37-acceptance.md`。

Step-38 將已驗證詳細頁的發言日期／時間保存為秒級 `material_announcement`
evidence，要求頁面報導期間與 Goodinfo task 相符；不完成 task，也不推導
XBRL 確認時間。詳見 `docs/step-38-acceptance.md`。

Step-39 以已驗證的 `STOCK_ID`、`CLAIM_TIME`、`SUBJECT` 建立固定 Goodinfo
locator，讓相同公告的 URL 路徑或 query 寫法差異不重複建立 evidence；
舊版 URL locator 會在重播時比對，不改寫既有證據。詳見
`docs/step-39-acceptance.md`。

Step-40 以共用輸出根目錄的檔案鎖與冷卻時間，讓 Goodinfo 清單及詳細頁請求
一次只送出一筆，間隔至少 3 秒並加上 jitter；同公司、同起訖日期的完整清單
直接讀取驗證後的本地快取。清單 CLI 已套用此操作入口，詳見
`docs/step-40-acceptance.md`。

## 報告識別候選方案

目前 provisional task identity 為：

```text
(stock_id, fiscal_year, report_period)
```

現有 fixtures 只有 `consolidated`，尚未驗證同一期 `consolidated` 與 `individual` 是否共存，因此暫不加入 `report_scope`。若未來原始證據證實兩者共存，且產品決定兩種 scope 都要追蹤，identity 才擴充為四欄位 tuple。詳細決策見 `docs/report-identity-candidate.md`。

## Task schema

SQLite migration `migrations/0001_create_task.sql` 建立 Step-8 的最小 `STRICT` task 資料表，`0002_define_engine_enum.sql` 再加上 engine constraint。`(stock_id, fiscal_year, report_period)` unique constraint 保護 provisional task identity，`report_scope` 仍不納入；完整 state machine 與 lease transition 留待後續步驟。詳細 schema 契約見 `docs/task-schema.md`。

## Evidence schema

SQLite migration `migrations/0003_create_evidence.sql` 建立 Step-10 的 `STRICT` evidence table，並以外鍵連結 task；`0004_add_evidence_metadata.sql` 加入 Step-11 中已通過 Step-3 source-evidence gate 的 nullable `company_name`。其餘四個候選欄位在具備 raw-backed deterministic rule 與 matrix evidence 前維持 deferred，不能以 nullable placeholder 繞過 gate。`filing_kind` 仍是 `not_verified`，須待來源分類規則證實後才能進 schema；Schema 也不含 `xbrl_confirmed_at` 或 generic `published_at`。詳細契約見 `docs/evidence-schema.md`。

## 邏輯證據識別

Step-12 以 task、source、source locator、event 與 payload 五個維度定義 logical evidence
identity，並依來源能力使用 profile：MOPS 要求 locator + payload hash；Goodinfo 使用
locator + CLAIM_TIME + SUBJECT，不全域強制 payload hash。Profile 必要依據單邊或雙邊缺失
時為 `unresolved`，不能把 `NULL` 當成差異。`retrieved_at` 與描述／驗證 metadata 不參與
identity。完整契約見 `docs/logical-evidence-identity.md`。

Step-13 以 source-specific partial unique indexes 保護已解析的 MOPS／Goodinfo logical
identity。Crawler 可用 `ON CONFLICT DO NOTHING` 讓重抓保持一筆；新 payload、新公告及不同
來源仍會新增 evidence。必要欄位缺失或尚無 source profile 的 `unresolved` evidence 不會被
推測性折疊；完整設計見 `docs/evidence-deduplication.md`。

Step-14 加入資料庫保護，禁止改寫或刪除已保存的來源證據，讓不同 payload 可保留為完整歷史。
修訂分類定義 `original`、`amendment`、`supplemental` 與 `unknown`；現有 MOPS fixtures
無法證明前三者，故保持 `unknown`。正式 SQLite 連線使用
`xbrlswarm.storage.connect_database`，開啟 foreign keys／recursive triggers 並驗證來源欄位
都受 immutability guard 保護。詳見 `docs/revision-history.md`。

Step-15 將來源明確提供的重大訊息「發言日期＋發言時間」映射為
`material_announcement` evidence 的 `event_date`／`event_time`，即
`announcement_at` 的等價表示；它與文章時間、`retrieved_at`、`xbrl_confirmed_at`
各有不同語意。詳見 `docs/announcement-time.md`。

## 階段 0 工具

列出固定的來源探索案例：

```bash
python -m xbrlswarm.discovery list-cases
```

使用官方 MOPS XBRL 下載介面批次擷取及驗證 12 個固定案例：

```bash
python -m xbrlswarm.discovery capture-mops-cases
python -m xbrlswarm.discovery verify-mops-captures
```

批次擷取固定使用 2024 Q1/Q2/Q3/FY，並將 FY 對應到 MOPS season=4。

離線重播 Step-3 欄位分析：

```bash
python -m xbrlswarm.discovery analyze-mops-captures
python -m xbrlswarm.discovery render-matrix
```

第一個指令會驗證 fixtures，解析 6 個必要 iXBRL facts，並產生 `discovery/mops_field_observations.json`；第二個指令會驗證契約並重新產生 `docs/source-field-matrix.md`。

若研究中需要額外擷取單一公開請求，也可使用：

```bash
python -m xbrlswarm.discovery capture \
  --stock-id 2330 \
  --company-name 台積電 \
  --fiscal-year 2024 \
  --period Q1 \
  --name financial-report-list \
  --url 'https://mops.twse.com.tw/...' \
  --extension html
```

此指令會保存：

- 完整且未修改的 response bytes
- 保留重複欄位的 response headers
- request 來源追溯資訊
- 最終 URL 與 HTTP 狀態碼
- 實際擷取時間
- SHA-256 與位元組大小

預設會拒絕覆寫既有擷取結果；同一組 fixture 的並行擷取也會被互斥鎖拒絕。

執行測試：

```bash
pytest
```

## 階段 0 不處理的範圍

目前仍不實作：

- 任務 lease
- production MOPS 解析器（Step-3 分析器只用於來源探索）
- MOPS Worker
- Goodinfo / Yahoo / Google / AI Worker
- 發布時間窗規則
- 必填的 `xbrl_confirmed_at` 欄位
