# Step-41 Goodinfo 試點報告

## 案例與方法

2026-09-24 執行固定的五個 Q1 案例：4542／6147／2330 的 2024 Q1、
6147 的 2022 Q1，以及 2330 的 2020 Q1。每個案例使用當年 4 月 1 日至
6 月 30 日的**探索用**公告清單日期範圍。這個範圍不代表該公司適用的法定
公告期限，也未證明公司歷史會計年度曆；2022／2020 年尤其沒有 Step-35
內建的已驗證法規查詢規則。

執行器 `python -m xbrlswarm.goodinfo_pilot` 使用 Step-40 的共用請求鎖、
至少 3 秒延遲與 jitter，同日期範圍的完整擷取可重用快取。每個清單最多
讀取三個期別提示相符的詳細頁，逐筆記錄解析與報導期間是否相符。試點
**不寫 evidence、不建立或完成 task**；候選提示及詳細頁解析不會直接
轉為已接受證據。

完整查詢 URL 與逐筆狀態見
[`discovery/goodinfo_pilot_2026-09-24.json`](../discovery/goodinfo_pilot_2026-09-24.json)。

| 案例 | 清單結果 | 候選數 | 詳細頁結果 |
| --- | --- | --- | --- |
| 4542-2024-Q1 | HTTP 403 | 未知 | 未請求 |
| 6147-2024-Q1 | HTTP 403 | 未知 | 未請求 |
| 2330-2024-Q1 | HTTP 403 | 未知 | 未請求 |
| 6147-2022-Q1 | HTTP 403 | 未知 | 未請求 |
| 2330-2020-Q1 | HTTP 403 | 未知 | 未請求 |

本執行環境沒有取得可保存的清單 bytes 或詳細頁，因此目前無法觀察歷史
涵蓋率、候選正確率或秒級發言時間覆蓋率。HTTP 403 是存取受阻，不能
推論這五筆沒有財報公告。Step-42 的歷史涵蓋率量測需等可存取且可重播的
原始回應；本報告保留未驗證狀態。

離線 regression tests 用可控的清單和詳細頁回應驗證五筆案例、限速入口、
候選及詳細頁解析、詳細頁數上限、快取重跑與拒絕回應語意。

重跑時可使用新的 report 路徑；如需沿用本機已驗證的快取，使用同一
`--output-root`：

```bash
PYTHONPATH=src python -m xbrlswarm.goodinfo_pilot \
  --output-root /tmp/xbrlswarm-goodinfo-pilot-captures \
  --report /tmp/xbrlswarm-goodinfo-pilot.json
```
