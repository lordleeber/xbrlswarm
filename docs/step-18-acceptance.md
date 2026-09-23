# Step-18 驗收 — 曆年制期別邊界

## RED

先新增 regression tests，覆蓋 Q1→03/31、Q2→06/30、Q3→09/30、FY→12/31、
不同 fiscal year、無效年度及 Q4 拒絕；並確認計算結果不會繞過
`evidence.period_end` 的 Step-3 source-evidence gate。
測試先因期別邊界函式與契約文件不存在而失敗。

## GREEN

新增 `calendar_year_period_end`、機器可讀契約與決策文件。
此函式只計算已確認曆年制公司的期末日期，不定義期初、法定發布期限或非曆年制規則。
本 Step 不增加 production 欄位，因此不需要 migration。
