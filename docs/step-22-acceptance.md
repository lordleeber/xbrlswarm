# Step-22 驗收 — 僅在來源已證實時加入會計年度曆

## RED

先新增測試，要求 Step-21 仍未證實穩定的公司別歷史來源時，必須選擇
`calendar-year companies only`，且未知／非曆年制不會進入規則 provider。
測試先因 Step-22 契約和文件不存在而失敗。

## GREEN

新增機器可讀的適用範圍契約與決策文件，明定公司及歷史期間的來源證據
是未來 production 排程的必要條件；unknown 不得默認 12/31。
現有 runtime 已在查詢規則前拒絕所有非 `calendar_year` 值，且尚無
全市場 task generator 可放行未驗證公司；本 Step 不需要 migration，
也不能憑舊版官方手冊建立 `fiscal_year_end` production 欄位。
