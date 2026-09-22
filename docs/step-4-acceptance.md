# Step-4 驗收 — 記錄尚未解決的歷史 `confirmed_at`

## 範圍

Step-4 將歷史 XBRL confirmation timestamp 的研究現況定版為來源契約：

```text
historical xbrl_confirmed_at = NOT PUBLICLY VERIFIED
```

本 Step 記錄未知狀態、禁止錯誤的時間替代值，並定義未來若要改變狀態所需的證據門檻。它不建立 production Schema，也不宣稱已證明公開歷史來源不存在。

## RED

先新增 repository contract tests，要求：

- 歷史時間文件必須保留精確的 `NOT PUBLICLY VERIFIED` 決策。
- 候選來源必須同時是公開可存取、具有歷史資料、可重播且可批次查詢。
- `announcement_at`、文章發布時間、`retrieved_at` 與 HTTP headers 必須明列為禁止替代值。
- 來源欄位矩陣中的 `xbrl_confirmed_at` 必須維持 `not_verified`。
- 文件必須明定 `xbrl_confirmed_at` 不得成為正式 Schema 的必填欄位。

測試先因本驗收文件尚未存在而失敗，確認失敗原因是 Step-4 契約尚未完成，而非測試設定錯誤。

## GREEN

擴充 `docs/historical-xbrl-confirmed-at.md`，明確區分：

```text
已知：官方申報系統存在申報／確認相關資訊
已觀察：12 個 MOPS iXBRL download payload 未提供該 timestamp
未知：是否存在符合四項條件的其他公開歷史來源
```

並定義未來變更狀態至少需要：

- 可稽核的事件語意證據
- 決定性歷史查詢與批次列舉方式
- 原始 response、來源位置、擷取時間及 payload hash
- 跨公司與 Q1/Q2/Q3/FY 的 regression fixtures

## Schema 決策

在上述證據通過審查以前：

- `xbrl_confirmed_at` 不得成為正式 Schema 的必填欄位。
- 不得用公告、文章、擷取或 HTTP metadata 的時間改名或填補。
- `discovery/source_field_matrix.json` 必須維持 `status = not_verified`。
- 單一 endpoint 未提供欄位，不得寫成「所有公開來源均不存在」。

即使未來找到合格來源，是否必填仍須另行驗證歷史涵蓋率與缺值行為。

## 交付物

```text
docs/historical-xbrl-confirmed-at.md
docs/step-4-acceptance.md
tests/test_step4_contract.py
```

本 Step 只有文件契約與測試，正式程式碼增量為 0 行，低於 800 行，因此不需要拆成 Step-4-a / Step-4-b。
