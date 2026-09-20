# PR1 驗收 — 階段 0 來源探索工具骨架

## 範圍

PR1 提供 ROADMAP 階段 0 / 步驟 0–4 所需的**工具、固定案例與保守契約骨架**，但不宣稱完成步驟 2/3 的實際 MOPS 來源研究。

包含：

- 固定來源探索案例：2330 / 6147 / 4542 × 2024 Q1/Q2/Q3/FY
- 用於 MOPS 來源研究的原始 HTTP 回應擷取器
- 完整 response body bytes 與 SHA-256 保存
- request / response 來源追溯資訊
- 保留重複欄位的 response headers 保存格式
- 敏感 request header 遮蔽
- 同一組 fixture 的並行 capture 防護
- source-field matrix 契約與決定性 Markdown 產生器
- 明確鎖定歷史 `xbrl_confirmed_at = NOT PUBLICLY VERIFIED`
- 階段 0 研究問題文件

明確排除：

- 實際 MOPS capture fixtures
- 根據實際 capture 證據完成的欄位可取得性結論
- 正式 DB / Schema
- task / evidence 資料表
- MOPS 解析器與 Worker
- 來源升級 Worker
- 發布時間窗法規規則
- 任何捏造或必填的 `xbrl_confirmed_at`

因此，在實際 fixture 與 evidence-backed matrix 完成前，**階段 0 不應被視為已完成，也不應進入正式 Schema freeze**。

## 先新增的測試

測試定義以下行為：

- 必須存在 12 個固定來源探索案例
- 每家公司都涵蓋 Q1/Q2/Q3/FY
- 拒絕 Q4 與未知期別
- 完整保存原始 response bytes
- 保存 response SHA-256 / 大小與來源追溯資訊
- response headers 不得因重複欄位而遺失
- 敏感 request headers 在 metadata 中必須遮蔽
- 既有 fixture 不得被靜默覆寫
- 在網路 I/O 前檢查同組 sibling file 衝突，避免產生半套 fixture
- body extension 不得與 `.headers.json` / `.meta.json` sibling 路徑碰撞
- 同一組 fixture 的並行 capture 不得互相覆寫
- `stock_id` 不得包含可跳脫 output root 的路徑字元
- `retrieved_at` 必須帶有時區
- source-field matrix 只能接受已知狀態值
- 此 PR 不得將歷史 `xbrl_confirmed_at` 從 `not_verified` 提升為其他狀態
- 欄位矩陣的 Markdown 輸出必須具有決定性，且包含未解決時間戳的契約

## 實作

最小實作新增 Python 3.11+ package，runtime 不需要第三方相依套件。網路存取封裝在可注入的 opener 後方，因此 unit tests 不會呼叫 live MOPS。

每個來源回應的 raw capture 會寫入三個 sibling files：

```text
<capture>.<ext>
<capture>.headers.json
<capture>.meta.json
```

擷取階段不解析來源回應內容。

## 回歸測試涵蓋

- 任一目標 sibling 已存在時，在送出 request 前失敗。
- extension 不得造成 body 與 metadata sibling 同路徑。
- 同一組 fixture 同時執行時，只有一個 capture 能進入網路 I/O 與寫檔流程。
- response header 以有序項目保存，重複 header 不會被 dict 覆蓋。
- 不安全的 `stock_id` 會在建立 `DiscoveryCase` 時被拒絕。

## 完整測試結果

```text
15 passed
```
