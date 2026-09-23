# Step-21 驗收 — 非曆年制公司研究閘門

## RED

先新增契約測試，要求三個 ROADMAP 問題各有明確狀態，官方工具能力不能
冒充公司別歷史資料；12 份既有 fixtures 不能外推全市場，非曆年制仍須拒絕。
測試先因研究 artifact 與文件不存在而失敗。

## GREEN

新增 `discovery/fiscal_calendar_research.json` 與決策文件，附官方來源、
本次 MOPS 存取限制、未解問題及 Step-22 的證據門檻。
本 Step 是來源研究，沒有足夠證據新增公司別會計年度資料或欄位；
既有 runtime 已拒絕未建模的非曆年制，因此不需要 migration 或新 production 解析器。
