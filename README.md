# xbrlswarm

`xbrlswarm` 用來蒐集、保存與稽核台灣上市櫃公司的歷史財務報告 / XBRL 發布證據。

目前已完成 **Step-9：定義 engine 列舉**。Repository 保存 2330 / 6147 / 4542 × 2024 Q1/Q2/Q3/FY 共 12 個從官方 MOPS XBRL 下載介面實際擷取的 raw fixtures，並以可重播分析器產生逐筆欄位 observation 與 evidence-backed matrix。

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

## 報告識別候選方案

目前 provisional task identity 為：

```text
(stock_id, fiscal_year, report_period)
```

現有 fixtures 只有 `consolidated`，尚未驗證同一期 `consolidated` 與 `individual` 是否共存，因此暫不加入 `report_scope`。若未來原始證據證實兩者共存，且產品決定兩種 scope 都要追蹤，identity 才擴充為四欄位 tuple。詳細決策見 `docs/report-identity-candidate.md`。

## Task schema

SQLite migration `migrations/0001_create_task.sql` 建立 Step-8 的最小 `STRICT` task 資料表，`0002_define_engine_enum.sql` 再加上 engine constraint。`(stock_id, fiscal_year, report_period)` unique constraint 保護 provisional task identity，`report_scope` 仍不納入；完整 state machine 與 lease transition 留待後續步驟。詳細 schema 契約見 `docs/task-schema.md`。

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

- evidence 資料表
- 任務 lease
- production MOPS 解析器（Step-3 分析器只用於來源探索）
- MOPS Worker
- Goodinfo / Yahoo / Google / AI Worker
- 發布時間窗規則
- 必填的 `xbrl_confirmed_at` 欄位
