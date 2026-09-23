# Engine 契約

## 正式值域

`engine` 必須是下列其中之一：

```text
mops
goodinfo
yahoo
google
grounded_ai
```

正式 Python enum 為 `xbrlswarm.domain.Engine`，機器可讀契約為 `contracts/engines.json`。這些值代表執行搜尋或證據擷取的 engine，不是 evidence type、source endpoint 或 task state。

`engine` 也不等於 evidence 的 `source_type`。例如 Google engine 可能發現 MOPS 或 Goodinfo artifact；task 仍記錄當前執行的 `google`，後續 evidence 則必須保留 artifact 的實際來源。

## Persistence

`migrations/0002_define_engine_enum.sql` 重建 Step-8 的 SQLite `task` table，在保留所有欄位、primary key、identity constraint、預設值與 `STRICT` typing 的同時，為 `task.engine` 加上固定值域。

Migration 只接受 enum 內的既有 task。若 Step-8 時期已寫入其他 engine，`INSERT OR ROLLBACK` 會在 constraint failure 時自動回滾整個 transaction：原始 `task` 與資料保持不變、`task_step9` 會被清除，連線也不會繼續持有 write transaction。這個失敗語意不依賴外部 migration runner 另行呼叫 `rollback()`。

## 本 Step 的邊界

Enum 中的宣告順序與 ROADMAP 一致，但 Step-9 只定義值域。何時從目前 engine fallback 到下一個 engine、哪些失敗必須留在原 engine，以及相應的 state transition，由 Step-26 至 Step-28 定義。

Step-9 不建立 worker、不實作來源請求，也不根據 enum 宣告順序自動改變 task engine。
