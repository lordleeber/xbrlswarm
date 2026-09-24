# Step-33 驗收 — MOPS 閘門

## 判定與範圍

**通過**，只開放 `mops → goodinfo`。這是 task 已由有效 MOPS lease 明確回報
`not_found` 或 `rejected` 後的排程轉移，不代表任何 MOPS 回應都可以自動判定
語意耗盡。Goodinfo 的查詢和解析從 Step-34 起實作。

| 閘門條件 | 稽核證據與限制 |
| --- | --- |
| source contract stable | `docs/source-field-matrix.md` 只採用 12 筆原始 XBRL 已證實的身份、期別、範圍與 locator；`docs/step-30-acceptance.md` 限定合併 `FileDownLoad` 路徑。 |
| fixtures complete | `tests/fixtures/mops/manifest.json` 固定 Q1／Q2／Q3／FY 合併 XBRL，以及更正、個體更正清單與附件、查無資料和錯誤版面；`tests/test_mops_worker_fixtures.py` 核對 raw hash。個體 XBRL 文件標示 `not_captured`，不能視為已支援。 |
| parser stable | `tests/test_mops_parser.py` 重播 12 筆已驗證 XBRL，檢查只輸出矩陣許可欄位；拒絕錯誤 URL、個體版面、更正類型、衝突 fact 與非 XBRL 頁面。 |
| failure semantics stable | `docs/semantic-exhaustion.md` 和 `docs/retryable-failures.md` 定義回報語意；試點對非預期或變更 payload 回報 `temporary_error`。`tests/test_engine_fallback.py` 驗證只有 `not_found`／`rejected` 轉來源，retryable 與成功不轉。`查無資料` fixture 只證明單次查詢無列，不能單獨觸發 `not_found`。 |
| pilot audited | `docs/mops-pilot-report.md` 與 `discovery/mops_pilot_2026-09-24.json` 留存 2330／6147／4542 × 2024 Q1／Q2／Q3／FY 的 12 筆即時官方來源 URL、時間、hash、任務及 evidence 結果；12／12 完成且與封存 bytes 一致。 |

`TaskStore.lease()` 在同一個 SQLite `BEGIN IMMEDIATE` 交易中完成 MOPS 語意
耗盡轉移及派發。保留 attempts、fail_count 和 evidence；僅轉移 engine 和 state。
Goodinfo 以後的來源仍維持關閉。本 Step 不需 migration，現有 task schema 已含
上述 state 和 engine。Regression tests 覆蓋兩種語意耗盡、尚未開放的來源、
retryable、成功、計數器、定向 lease 與交易回滾。

本 gate 不擴張到個體 XBRL、修訂分類、申報時間或 `xbrl_confirmed_at`；這些
仍需新來源證據和各自驗收。
