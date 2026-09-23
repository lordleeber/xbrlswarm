# Step-22 — 會計年度曆建模閘門

Step-21 的[來源研究](fiscal-calendar-research.md)尚未取得可靠的公司別、歷史期間
會計年度曆資料，因此 Step-22 選擇 ROADMAP 的保守分支：第一版明確限制為
`calendar-year companies only`。機器可讀決策見
`contracts/fiscal-calendar-eligibility.json`。

「只支援曆年制」不代表預設所有公司都是曆年制。任何後續 production 排程者
在產生某公司、某歷史期間的任務前，必須有可稽核的來源證據證明該公司及歷史期間
採 12/31 year-end；不得只依公司代號、現行設定、既有 12 份 XBRL fixtures，
或呼叫者傳入的 `fiscal_calendar="calendar_year"` 就視為已驗證。
未知不等於 12/31，也不等於該公司從未採非曆年制。

目前 repository 尚無全市場 task generator，亦無已驗證公司／期間的 fiscal calendar
名單，因此全市場與非曆年制任務產生繼續暫緩。後續排程遇到 unknown、
unverified 或 non-calendar year 必須標為 unsupported／跳過，不能套用 Step-18 的
曆年制季度邊界。既有 `expected_publication_window(...)` 只接受精確的
`calendar_year`，其餘值在查詢 rule provider 前即拒絕；
`calendar_year_period_end(...)` 只是給已確認曆年制案例使用的純日期計算，
不會自行驗證公司來源。

本 Step 不新增 `fiscal_year_end` production 欄位、非曆年制日期算法或 migration。
待取得公司別原始回應、可重播 locator、跨年度變更樣本與決定性解析規則後，
才能重新評估來源矩陣、歷史有效範圍與 schema。舊版官方手冊描述的工具能力
不能替代現行或公司別來源證據。
