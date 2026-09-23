# Step-18 — 曆年制報告期別邊界

對已確認採曆年制、會計年度於 12 月 31 日結束的公司，
`calendar_year_period_end(fiscal_year, report_period)` 回傳下列期末日期：

| 期別 | 期末日期 |
| --- | --- |
| Q1 | fiscal year 的 03/31 |
| Q2 | fiscal year 的 06/30 |
| Q3 | fiscal year 的 09/30 |
| FY | fiscal year 的 12/31 |

內部期別仍只有 Q1、Q2、Q3、FY；`FY != Q4`。MOPS 的 Q4 標籤須先由
來源專用正規化規則轉為 FY，不得直接把通用 Q4 當成正式期別。
函式只接受 1 到 9999 的整數年度，並回傳 `datetime.date`，不產生時刻或時區。

這是已知曆年制前提下的**排程／規則計算邊界**，不是來源明確聲稱的
`evidence.period_end`。Step-11 的 source-evidence gate 仍適用：不得因本函式存在
就新增或填補 production evidence 的 `period_start`／`period_end` 欄位。
此日期也不是公告時間、XBRL 確認時間或法定發布截止日。

Step-19 定義 `expected_publication_window(...)` 介面，但不內建法規日期；
Step-20 定義歷史規則版本；Step-21 已研究非曆年制與會計年度變更，
公司別歷史資料仍未驗證，詳見 `docs/fiscal-calendar-research.md`。
在確認公司財務年度曆以前，不得套用本映射。
