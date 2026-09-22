# xbrlswarm

`xbrlswarm` 用來蒐集、保存與稽核台灣上市櫃公司的歷史財務報告 / XBRL 發布證據。

目前已完成 **Step-3：建立欄位可取得性矩陣**。Repository 保存 2330 / 6147 / 4542 × 2024 Q1/Q2/Q3/FY 共 12 個從官方 MOPS XBRL 下載介面實際擷取的 raw fixtures，並以可重播分析器產生逐筆欄位 observation 與 evidence-backed matrix。

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

## 時間語意

XBRL 申報 / 確認事件與 MOPS 重大訊息公告是不同事件。第三方來源的 `announcement_at`、文章發布時間、爬蟲的 `retrieved_at` 或 HTTP header，都不能在沒有來源證據證明其語意相同的情況下改名為 `xbrl_confirmed_at`。

目前將公開歷史 `xbrl_confirmed_at` 視為 **尚未由公開來源驗證（NOT PUBLICLY VERIFIED）**。

## 報告期別

第一版使用：

```text
Q1
Q2
Q3
FY
```

`FY` 代表年度財務報告，`FY != Q4`。

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

- 最終正式 Schema
- evidence 資料表
- 任務 lease
- production MOPS 解析器（Step-3 分析器只用於來源探索）
- MOPS Worker
- Goodinfo / Yahoo / Google / AI Worker
- 發布時間窗規則
- 必填的 `xbrl_confirmed_at` 欄位
