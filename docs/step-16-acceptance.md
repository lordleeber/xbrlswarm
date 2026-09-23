# Step-16 驗收 — 不得捏造 XBRL 確認時間

## RED

先新增 regression tests，檢查公告映射只產生公告事件欄位、已套用全部 migration
的 production schema 不含 `xbrl_confirmed_at`，且 source matrix 仍為
`not_verified`。機器可讀的禁止替代契約與 Step 文件尚不存在，測試先失敗。

## GREEN

新增契約與決策文件，明確禁止把 `announcement_at`、`article_published_at`、
`retrieved_at`、HTTP `Date`／`Last-Modified` 改名或推導為 `xbrl_confirmed_at`。
既有程式與 schema 已保留此邊界，
所以不需要 migration 或新的來源擷取程式。時間精度留待 Step-17。

## Code review regression

`prohibited_substitutes` 必須同時包含 `http_date`、`http_last_modified`；
不得讓機器可讀契約比 Step-4 禁令少了 HTTP metadata。
