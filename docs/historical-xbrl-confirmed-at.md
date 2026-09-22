# 歷史 `xbrl_confirmed_at` 狀態

## 決策

目前的來源契約是：

```text
historical xbrl_confirmed_at = NOT PUBLICLY VERIFIED
```

這個狀態表示「目前沒有足夠證據證實可由公開來源取得」，不表示已證明公開來源不存在，也不表示該事件本身不存在。

## 已知與尚未證實的界線

已知官方申報系統存在申報日期、申報時間、檢核結果與確認與否等資訊；然而，階段 0 保存並分析的 12 個 MOPS iXBRL download payload 未提供 filing 或 confirmation timestamp。單一 endpoint 沒有該欄位，不能外推成整體 MOPS 都沒有該欄位。

目前尚未證實存在同時符合以下四項條件的來源：

- 公開可存取
- 具有歷史資料
- 可重播
- 可批次查詢

在取得並審查這類證據以前，`xbrl_confirmed_at` 不得成為正式 Schema 的必填欄位，也不得由其他時間欄位推導或填補。

## 禁止替代值

以下資訊明確**不能**作為替代值：

- 重大訊息公告時間（`announcement_at`）
- 新聞 / 文章發布時間
- 爬蟲 `retrieved_at`
- HTTP `Date` 或 `Last-Modified`

這些時間分別描述公告、內容發布、資料擷取或 HTTP response metadata；它們不是 XBRL confirmation event。即使時間恰好相同，也不能只憑相等的值宣稱語意相同。

## 未來變更此狀態的門檻

只有新證據同時通過下列審查，才能提案變更 `NOT PUBLICLY VERIFIED`：

1. 來源欄位的官方定義或其他可稽核證據，能證明它表示 XBRL confirmation event。
2. 歷史查詢可用固定輸入重播，而不是只能查看當下狀態或人工操作畫面。
3. 能以公司與報告期別進行批次查詢，或有可重現的決定性列舉方式。
4. 保存原始 response、來源位置、擷取時間與 payload hash，讓結論可以獨立複核。
5. 以涵蓋不同公司和 Q1/Q2/Q3/FY 的 fixtures 建立 regression tests。

通過上述門檻仍只代表可以建模該來源實際提供的語意；是否必填，必須再依歷史涵蓋率與缺值行為另行決定。

## 現有證據

- `discovery/mops_field_observations.json`：12 個 MOPS iXBRL payload 的可重播欄位 observations。
- `docs/source-field-matrix.md`：將 `xbrl_confirmed_at` 保持為 `not_verified` 的來源欄位矩陣。
- `docs/step-3-acceptance.md`：記錄本次 endpoint 的發現與不可外推的範圍。
