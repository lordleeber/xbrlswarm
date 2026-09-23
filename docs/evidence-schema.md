# Evidence 資料表

## Schema

Step-10 以 SQLite migration `migrations/0003_create_evidence.sql` 建立 `STRICT` evidence 資料表：

| 欄位 | SQLite 型別 | 必填 | 語意 |
| --- | --- | --- | --- |
| `id` | INTEGER | 是 | SQLite row identifier／primary key |
| `task_id` | INTEGER | 是 | 所屬 task；外鍵禁止刪除仍有 evidence 的 task |
| `evidence_type` | TEXT | 是 | Step-7 定義的五種 evidence type 之一 |
| `event_date` | TEXT | 否 | 來源明確聲稱的事件日期 |
| `event_time` | TEXT | 否 | 來源明確聲稱的事件時間 |
| `event_precision` | TEXT | 否 | 事件時間精度；正式值域由 Step-17 定義 |
| `source_type` | TEXT | 是 | evidence 實際來源，不是 task engine |
| `source_endpoint` | TEXT | 否 | 來源 endpoint 識別 |
| `source_url` | TEXT | 否 | 實際來源 URL |
| `source_locator` | TEXT | 否 | 可重播或追溯的來源位置 |
| `source_title` | TEXT | 否 | 來源標題 |
| `source_subject` | TEXT | 否 | 來源主旨／公告主旨 |
| `retrieved_at` | TEXT | 是 | 系統擷取 evidence 的時間；capture metadata |
| `raw_payload_hash` | TEXT | 否 | 存在 raw payload 時的 content hash |
| `verification_state` | TEXT | 是 | 驗證狀態；正式值域由 Step-54 定義 |

`task_id`、`evidence_type`、`source_type`、`retrieved_at` 與 `verification_state` 是每筆 evidence 可由系統保證產生的核心 metadata，因此為必填。尚未定義正式 enum 的 `verification_state` 在本 Step 只要求非空，不提前實作 Step-54。

SQLite 必須在每個 runtime connection 啟用 `PRAGMA foreign_keys = ON`，才會執行 `task_id` 的 `ON DELETE RESTRICT` 外鍵。Migration 保留該外鍵宣告；連線建立與 PRAGMA 設定屬於後續 database runtime 實作。

## 可選欄位與來源忠實性

`event_date`、`event_time` 與 `event_precision` 只有在來源明確提供並能辨識事件語意時才填寫。不得由 `retrieved_at`、公告時間、文章時間或 HTTP metadata 推導其他事件時間。

Source locator、title、subject 與 raw payload hash 也只在實際可得時保存，不用假值填補。

ROADMAP Step-10 的列表雖然列出 `filing_kind`，但 Step-3 的 schema gate 規定只有 `direct` 或具決定性規則的 `derived` 欄位才能進入正式 Schema。現有 MOPS source matrix 將 `filing_kind` 標示為 `not_verified`，因此 Step-10 不建立該欄位。Step-14 必須先確認分類契約與來源規則，再以新 migration 加入；nullable placeholder 不能取代這個證據門檻。

## 時間語意

Schema 不含 `xbrl_confirmed_at`，因為公開歷史來源仍為 **NOT PUBLICLY VERIFIED**。它也不含 generic `published_at`；evidence 的事件時間與 crawler `retrieved_at` 保持分離。

## 本 Step 的邊界

- Evidence type 值域沿用 Step-7，不將 `source_type` 或 `verification_state` 混入。
- `task.engine` 描述執行搜尋的 engine；`evidence.source_type` 描述 artifact 的實際來源。例如 Google engine 發現 Cnyes mirror 時，兩者分別保存為 `google` 與 `cnyes`。
- Step-10 不定義 logical evidence identity 或 unique constraint；這是 Step-12 的範圍。
- Step-10 不建立 `filing_kind` 欄位，也不定義 event precision 或 verification state 的正式 enum。
- Step-11 的 parsed metadata 欄位不在本資料表。
