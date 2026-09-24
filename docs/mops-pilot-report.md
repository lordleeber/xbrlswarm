# Step-32 MOPS 試點報告

## 執行範圍與方法

2026-09-24 08:44:25–08:44:37 UTC，對官方 MOPS `FileDownLoad` 端點重新請求
2330、6147、4542 的 2024 Q1／Q2／Q3／FY 合併 XBRL，共 12 個固定案例。
每筆使用 Step-2 已驗證的 URL 與 request headers；沒有查詢個體報告。

試點每個固定案例只執行一次：runner 對該案例的 task id 定向 lease，並把試點
retry cooldown 設為一天，避免一般 60 秒重試排程在本輪稽核中搶先重新派發
較早失敗的 task。若異常漫長的稽核使 cooldown 仍到期，定向 lease 也會繼續
執行尚未檢查的案例；逐筆 `task_state` 記錄該筆 result 當下的狀態。

使用 `python -m xbrlswarm.mops_pilot` 在獨立 SQLite 資料庫套用全部 migration，
建立 12 個 MOPS task。每筆依序經 `/lease` 同一套 `TaskStore` 交易邏輯、
即時 HTTP 擷取、Step-30 parser、Step-31 evidence 接受與 result 完成邏輯。
試點未修改正式資料庫。快照政策關閉；本次原始 bytes 與已提交的 Step-2 raw
fixture 逐筆完全相同，因此可用既有 fixture 重播。

完整逐筆來源 URL、擷取時間、HTTP status／final URL、原始 SHA-256、byte 數、
fixture 比對及 evidence id 見
[`discovery/mops_pilot_2026-09-24.json`](../discovery/mops_pilot_2026-09-24.json)。
以下摘要雜湊只列前 12 碼；完整摘要以 JSON 為準。

| 案例 | UTC 時間 | 原始 bytes | SHA-256 前 12 碼 | task 結果 |
| --- | --- | ---: | --- | --- |
| 2330-2024-Q1 | 08:44:25 | 751,149 | `68117c2ed0ca` | completed |
| 2330-2024-Q2 | 08:44:26 | 800,160 | `9be8d57b4626` | completed |
| 2330-2024-Q3 | 08:44:27 | 807,198 | `c89f1074e9a8` | completed |
| 2330-2024-FY | 08:44:29 | 808,091 | `45a7f1e2008d` | completed |
| 6147-2024-Q1 | 08:44:29 | 507,508 | `3db1987326db` | completed |
| 6147-2024-Q2 | 08:44:30 | 565,759 | `3e99c36c3607` | completed |
| 6147-2024-Q3 | 08:44:31 | 571,115 | `43ef36c02522` | completed |
| 6147-2024-FY | 08:44:33 | 559,878 | `878efb08396b` | completed |
| 4542-2024-Q1 | 08:44:34 | 586,425 | `5ecd37ef38e8` | completed |
| 4542-2024-Q2 | 08:44:35 | 643,165 | `8a591904e277` | completed |
| 4542-2024-Q3 | 08:44:36 | 649,677 | `1e394fb65b6b` | completed |
| 4542-2024-FY | 08:44:37 | 622,176 | `d6d165834e59` | completed |

## 稽核結果

- 12／12 HTTP 200，final URL 等於請求 URL；12／12 payload SHA-256 與封存 fixture 相同。
- 12／12 通過 Step-30 已驗證欄位 parser；12／12 evidence 保存原始 response hash，
  12／12 task 成為 `completed`；沒有 retryable failure 或來源切換。
- 試點 runner 遇到不同於封存 fixture 的 payload，會將該 task 留在
  `temporary_error` 並要求重新擷取與審查，不把未知版面直接視為完成。
- 本次結果只支持上述合併報告與已測來源契約；沒有驗證個體 XBRL、修訂版本
  分類、申報時間或 `xbrl_confirmed_at`。Step-33 的來源與失敗語意 gate 尚待另行審查；
  此報告本身不啟用 Goodinfo 備援。

重跑時使用新的 scratch 路徑，避免覆寫先前試點資料：

```bash
PYTHONPATH=src python -m xbrlswarm.mops_pilot \
  --database /tmp/xbrlswarm-mops-pilot.sqlite \
  --output /tmp/xbrlswarm-mops-pilot.json
```
