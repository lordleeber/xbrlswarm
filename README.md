# xbrlswarm

`xbrlswarm` 用來蒐集、保存與稽核台灣上市櫃公司的歷史財務報告 / XBRL 發布證據。

目前已完成 **Step-2：擷取原始 MOPS 回應**。Repository 保存 2330 / 6147 / 4542 × 2024 Q1/Q2/Q3/FY 共 12 個從官方 MOPS XBRL 下載介面實際擷取的 raw fixtures；raw body 以 lossless gzip 保存，SHA-256 與 size 仍針對解壓後的原始 response bytes 驗證，並另外保存 response headers 與 request/response provenance。**Step-3 的欄位可取得性結論仍未完成**；在 evidence-backed matrix 完成前，不應進入正式 Schema 定版。

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

Step-2 使用官方 MOPS XBRL 下載介面，批次擷取 12 個固定案例：

```bash
python -m xbrlswarm.discovery capture-mops-cases
python -m xbrlswarm.discovery verify-mops-captures
```

批次擷取固定使用 2024 Q1/Q2/Q3/FY，並將 FY 對應到 MOPS season=4。此步驟只保存官方回應，不解析或推導欄位。

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

產生欄位可取得性矩陣：

```bash
python -m xbrlswarm.discovery render-matrix
```

執行測試：

```bash
pytest
```

## 階段 0 不處理的範圍

此 PR 不實作：

- 根據 capture 內容完成的欄位可取得性結論（Step-3）
- 最終正式 Schema
- evidence 資料表
- 任務 lease
- MOPS 解析器
- MOPS Worker
- Goodinfo / Yahoo / Google / AI Worker
- 發布時間窗規則
- 必填的 `xbrl_confirmed_at` 欄位
