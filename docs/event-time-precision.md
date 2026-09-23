# Step-17 — 保留事件時間精度

`event_precision` 的正式值域目前是 `date` 與 `second`。來源只明確給日期時，
保存 `event_date=YYYY-MM-DD`、`event_time=NULL`、`event_precision=date`；
來源明確給日期和 `HH:MM:SS` 時，保留原時間文字並保存
`event_precision=second`。`00:00:00` 只有在來源真的提供時才是合法的秒級時間。

禁止把 `2024-05-10` 自動轉成 `2024-05-10 00:00:00`。日期缺少時分秒表示
精度未知，不是午夜；亦不推測時區。若來源只提供分鐘、含分秒小數、時區或其他
格式，現階段的共用映射不擅自升級或截斷成秒，而是拒絕，等待來源專屬規則及
對應測試。來源專屬解析器負責將原始格式可稽核地正規化成此契約接受的格式。

`xbrlswarm.domain.event_time_fields` 提供日期／秒級映射；Step-15 的
`announcement_event_fields` 呼叫此映射，所以明確的公告發言時間會帶
`event_precision=second`。只有日期的其他 evidence 可使用同一映射而不產生
虛構的 `event_time`。`retrieved_at` 與 `xbrl_confirmed_at` 的語意仍保持分離。

既有 evidence schema 已有 nullable `event_date`、`event_time`、`event_precision`。
Step-17 migration `0007_enforce_event_precision.sql` 對新的 evidence INSERT 強制三種合法組合：
三欄皆 `NULL`、只有日期且精度為 `date`、或日期與時間皆有且精度為 `second`。
舊資料不重寫：先前 Step-15 已存的 Goodinfo 發言時間可保留 `event_precision=NULL`，
但 Goodinfo unique index 將這種 legacy `NULL` 視為 `second`，讓相同公告重抓仍只有一筆。
若升級前已同時存有 legacy `NULL` 與 `second` 的同一 identity，migration 會中止並保留
原資料，必須先人工稽核；不會偷偷刪除來源證據。
