# Step-19 驗收 — 發布時間窗規則介面

## RED

先新增 regression tests，要求四個輸入完整傳給規則提供者，結果含
`earliest_date`、`latest_date`、`rule_id`；無 provider 或無匹配規則必須拒絕推測。
測試也要求拒絕 Q4、無效年度、空白公司類別及未研究的非曆年制。
測試先因介面與契約文件不存在而失敗。

## GREEN

新增 `expected_publication_window`、查詢／回傳型別、provider protocol、
machine-readable contract 與決策文件。Step-20 才導入歷史規則版本；
本 Step 不內建法規日期或變更資料表，因此不需要 migration。
