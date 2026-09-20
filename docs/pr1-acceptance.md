# PR1 驗收 — 階段 0：Schema 前的來源探索

## 範圍

PR1 僅實作目前 ROADMAP 的第一個開發切片：階段 0 / 步驟 0–4。

包含：

- 固定來源探索案例：2330 / 6147 / 4542 × 2024 Q1/Q2/Q3/FY
- 用於 MOPS 來源研究的原始 HTTP 回應擷取器
- 完整 response body bytes 與 SHA-256 保存
- request / response 來源追溯資訊與 response headers 保存
- source-field matrix 契約與決定性 Markdown 產生器
- 明確鎖定歷史 `xbrl_confirmed_at = NOT PUBLICLY VERIFIED`
- 階段 0 研究問題文件

明確排除：

- 正式 DB / Schema
- task / evidence 資料表
- MOPS 解析器與 Worker
- 來源升級 Worker
- 發布時間窗法規規則
- 任何捏造或必填的 `xbrl_confirmed_at`

## 先新增的測試

在正式程式碼實作以前，測試先定義以下行為：

- 必須存在 12 個固定來源探索案例
- 每家公司都涵蓋 Q1/Q2/Q3/FY
- 拒絕 Q4 與未知期別
- 完整保存原始 response bytes
- 保存 response SHA-256 / 大小與來源追溯資訊
- 敏感 request headers 在 metadata 中必須遮蔽
- 既有 fixture 不得被靜默覆寫
- 在網路 I/O 前檢查同組 sibling file 衝突，避免產生半套 fixture
- `retrieved_at` 必須帶有時區
- source-field matrix 只能接受已知狀態值
- 此 PR 不得將歷史 `xbrl_confirmed_at` 從 `not_verified` 提升為其他狀態
- 欄位矩陣的 Markdown 輸出必須具有決定性，且包含未解決時間戳的契約

## 預期 RED

在實作存在以前，測試會因為 `xbrlswarm.discovery` package、來源探索案例 registry、原始回應 recorder 與 matrix contract 尚不存在而失敗。

## 實作

最小實作新增 Python 3.11+ package，runtime 不需要第三方相依套件。網路存取封裝在可注入的 opener 後方，因此 unit tests 永遠不會呼叫 live MOPS。

每個來源回應的 raw capture 會寫入三個 sibling files：

```text
<capture>.<ext>
<capture>.headers.json
<capture>.meta.json
```

擷取階段不解析來源回應內容。

## 回歸測試涵蓋

partial-fixture 回歸測試確保：只要任一目標 sibling 已存在，就會在送出 request 前失敗，而且不會寫入任何新的 sibling file。

## 完整測試結果

```text
13 passed
```
