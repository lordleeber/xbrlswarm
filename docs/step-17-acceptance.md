# Step-17 驗收 — 保留時間精度

## RED

先新增 regression tests，要求日期單獨保存為 `precision=date` 且
`event_time=NULL`，明確的 `HH:MM:SS` 保存為 `precision=second`；
不合法或未定義的格式不得猜測。測試先因映射函式與契約文件不存在而失敗。

## GREEN

新增 `EventPrecision`、`event_time_fields`、機器可讀契約與決策文件。
Step-15 公告映射改用共用函式，明確保存秒級精度。
既有 SQLite evidence table 已有 `event_precision` 欄，故不需要 migration；
日期單獨寫入後仍保留 `NULL` 時間，不會變成虛構的午夜。
