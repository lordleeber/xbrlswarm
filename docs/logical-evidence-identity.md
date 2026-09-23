# 邏輯證據識別

## 決策

Step-12 將同一邏輯證據定義為下列五個 ROADMAP 維度都相同：

| 維度 | 欄位 | 比較方式 |
| --- | --- | --- |
| same task | `task_id` | 儲存值完全相同 |
| same source | `source_type` | 儲存值完全相同 |
| same source locator | `source_locator` | 儲存值完全相同且不得缺值 |
| same event | `evidence_type`, `event_date`, `event_time`, `event_precision` | event tuple 的儲存值完全相同 |
| same payload | `raw_payload_hash` | 儲存值完全相同且不得缺值 |

正式欄位順序與 resolution policy 保存於
`contracts/logical-evidence-identity.json`。比較採 exact stored value；Step-12 不做 URL
canonicalization、大小寫轉換、日期推導或來源間的值合併。

## 三態比較

Identity 比較結果是 `same`、`different` 或 `unresolved`：

1. 任一 identity 欄位不同，結果是 `different`。
2. 所有 identity 欄位相同，但任一筆缺少 `source_locator` 或 `raw_payload_hash`，結果是
   `unresolved`。
3. 所有 identity 欄位相同，且 locator 與 payload hash 都存在，結果才是 `same`。

`source_locator` 與 `raw_payload_hash` 是證明 same locator／same payload 的必要依據。兩筆資料
都為 `NULL` 不代表兩者相同；不得把未知當成不存在，也不得以 `source_url` 猜測 locator。
`unresolved` evidence 必須保留，不能自動折疊。

Event tuple 中的 nullable 值描述 evidence 實際保存的事件主張。例如兩筆文件都沒有
event timestamp，但 task、source、locator、evidence type 與 payload 完全相同時，仍可辨識
為同一個 artifact；若後續 evidence 多出日期、時間或 precision，event tuple 已改變，應追加
保存而非覆寫原資料。

## 不參與 identity 的欄位

以下欄位是 retrieval、provenance、描述或驗證 metadata，不會單獨產生新的邏輯證據：

```text
id
source_endpoint
source_url
source_title
source_subject
retrieved_at
verification_state
company_name
```

因此同一 artifact 再次擷取，即使 `retrieved_at`、URL、標題、驗證狀態或公司名稱表示不同，
仍是同一 logical evidence。反之，task、source、locator、event tuple 或 payload 任一不同，
都必須視為不同證據；這會保留不同來源、新公告與 payload 修訂。

## Step 邊界

- Step-12 只定義 identity contract，不建立 unique constraint，也不實作寫入時去重；這是
  Step-13 的範圍。
- Payload 不同目前只表示不同 logical evidence。它是否為 original、amendment、
  supplemental 或其他修訂關係，由 Step-14 定義。
- `event_precision` 的正式值域留給 Step-17；在此只比較 evidence table 已保存的值。
- Identity 不使用 `filing_kind`、`xbrl_confirmed_at` 或未通過 source-evidence gate 的欄位。
