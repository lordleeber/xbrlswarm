# Step-17 驗收 — 保留時間精度

## RED

先新增 regression tests，要求日期單獨保存為 `precision=date` 且
`event_time=NULL`，明確的 `HH:MM:SS` 保存為 `precision=second`；
不合法或未定義的格式不得猜測。測試先因映射函式與契約文件不存在而失敗。

## GREEN

新增 `EventPrecision`、`event_time_fields`、機器可讀契約與決策文件。
Step-15 公告映射改用共用函式，明確保存秒級精度。
既有 SQLite evidence table 已有 `event_precision` 欄，但仍需要 migration
`migrations/0007_enforce_event_precision.sql` 約束新 INSERT 的值域與欄位組合；
日期單獨寫入後仍保留 `NULL` 時間，不會變成虛構的午夜。

## Code review regression

- Step-15 Goodinfo legacy `event_precision=NULL` 與 Step-17 `second` 必須命中同一
  logical identity，重抓後仍只有一筆；既有列不得被改寫。
- 升級前若已存在兩筆在新 identity projection 下重複的列，migration 必須拒絕，
  不可刪除來源證據。
- 直接 SQL INSERT 不得繞過 `date`／`second` 值域及三欄合法組合。
