# Step-39 驗收 — Goodinfo 公告冪等性

Step-38 直接以候選 request URL 作 `source_locator` 時，同一公告若由 `/tw/` 與
`/tw2/`、不同 query 順序或不同 percent encoding 取得，會被當成不同 locator。
Step-39 的 `goodinfo_announcement_locator` 從 Step-37 已核對的 URL 解出
`STOCK_ID`、`CLAIM_TIME`、`SUBJECT`，固定欄位順序建立
`goodinfo:announcement:` locator。主旨僅套用 Step-37 已驗證的 Unicode NFKC、
空白移除及民國年轉西元年規則。其他 query 參數、路徑和轉址目標不進 locator。
`source_url` 仍保存實際回應 URL，不參與 identity。

Step-13／17 的既有 Goodinfo unique index 會對新 locator、公告事件欄位、頁面
主旨和 raw hash 防止完全重複；同一 raw 回應重播時，Step-38 返回原 evidence。
不同 `SUBJECT` 或 raw payload 仍保留為不同證據。資料庫寫入使用
`BEGIN IMMEDIATE`，先檢查既有列再插入。舊版 Step-38 已存的 request URL
locator 不可改寫；重播時會比對其三個 identity 欄位，若唯一等價列存在就返回
舊列。若已有多個等價列（包括新舊 locator 混存），拒絕自動選擇，留待人工稽核。缺少 locator 的舊列
不以 `source_url` 猜測並折疊。

這是 Goodinfo 來源專用的**locator 建構規則**。一般 logical evidence 比較仍依
儲存值相等判定，不對任意來源 URL 做通用 canonicalization。現有 schema 與
unique index 已能使用固定 locator，本 Step 無 migration。邊界見
`contracts/goodinfo-idempotency.json`。本 Step 不改變 Step-38 的發言時間語意、
task 狀態或未驗證 XBRL 確認時間。
