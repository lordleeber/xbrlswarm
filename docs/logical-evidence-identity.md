# 邏輯證據識別

## 決策

Step-12 將同一邏輯證據定義為下列五個 ROADMAP 維度都相同：

| 維度 | 欄位 | 比較方式 |
| --- | --- | --- |
| same task | `task_id` | 儲存值完全相同 |
| same source | `source_type` | 儲存值完全相同 |
| same source locator | `source_locator` | 依來源 profile 要求穩定 locator |
| same event | `evidence_type`, `event_date`, `event_time`, `event_precision`, `source_subject` | 依來源 profile 比較 event 欄位 |
| same payload | `raw_payload_hash` | 依來源 profile 決定是否為必要依據 |

正式欄位順序與 resolution policy 保存於
`contracts/logical-evidence-identity.json`。比較採 exact stored value；Step-12 不做 URL
canonicalization、大小寫轉換、日期推導或來源間的值合併。

## 來源 profile

不同來源能穩定提供的 identity evidence 不同，因此 `raw_payload_hash` 不是所有 evidence 的
全域必要條件。Step-12 先定義已有 ROADMAP 依據的兩個 profile：

| `source_type` | Profile | 必要欄位 | 依據 |
| --- | --- | --- | --- |
| `mops` | `mops_payload_backed` | `source_locator`, `raw_payload_hash` | Step-31 要求已接受的 MOPS evidence 至少保存 payload hash |
| `goodinfo` | `goodinfo_announcement` | `source_locator`, `event_date`, `event_time`, `source_subject` | Step-39 使用詳細頁 URL／定位資訊及 STOCK_ID + CLAIM_TIME + SUBJECT |

Goodinfo 的 `source_locator` 必須由詳細頁 URL 或可重播的定位資訊建立；task 已識別股票，
`event_date` + `event_time` 保存 CLAIM_TIME，`source_subject` 保存 SUBJECT。Goodinfo 若另有
payload hash，兩邊皆有值時仍會參與差異判定，但缺少 hash 不妨礙同一公告去重。

尚未定義 profile 的 source 保持 `unresolved`。Yahoo、Google 發現的各站 mirror 與
Grounded AI 必須在各自來源契約證實穩定 identity evidence 後才能新增 profile，不能直接
套用 MOPS 或 Goodinfo 規則。

## 三態比較

Identity 比較結果是 `same`、`different` 或 `unresolved`：

1. `task_id`、`source_type` 或 `evidence_type` 兩邊皆有值且不同時，結果是 `different`。
2. 依共同的 `source_type` 選擇 profile；沒有已定義 profile 時結果是 `unresolved`。
3. Profile comparison field 只有在兩邊皆有值且不相等時，才證明為 `different`。
4. Profile comparison field 只有一側有值時，結果是 `unresolved`。
5. 沒有已知差異，但 profile 的必要欄位兩側都缺值時，結果也是 `unresolved`。
6. 沒有已知差異、沒有 asymmetric missing，且兩邊都具備 profile 必要欄位時，結果才是
   `same`。

`NULL` 代表未知，不證明相同或不同。特別是 profile 必要欄位出現 asymmetric missing
（一側 `NULL`、另一側有值）時，如果沒有其他兩邊皆已知且不同的欄位，結果必須是
`unresolved`，不能判成 `different`。兩側都缺必要欄位亦同；不得以 `source_url` 猜測
locator。`unresolved` evidence 必須保留，不能自動折疊。

Event tuple 中的 nullable 值描述 evidence 實際保存的事件主張。例如兩筆文件都沒有
event timestamp，但 MOPS 的 task、source、locator、evidence type 與 payload 完全相同時，
仍可辨識為同一個 artifact。兩側皆有 event 值且互相衝突時是 `different`；單側新增
optional event metadata 時是 `unresolved`，不能自動折疊。

## 不參與 identity 的欄位

以下欄位是 retrieval、provenance、描述或驗證 metadata，不會單獨產生新的邏輯證據：

```text
id
source_endpoint
source_url
source_title
retrieved_at
verification_state
company_name
```

因此同一 artifact 再次擷取，即使 `retrieved_at`、URL、標題、驗證狀態或公司名稱表示不同，
也不會只因這些欄位產生新 logical evidence。`source_subject` 是 Goodinfo announcement
profile 的 event identity 欄位，但不參與 MOPS profile。Profile 中兩邊皆已知的 locator、
event 或 payload 值若不同，則必須視為不同證據；這會保留不同來源、新公告與 payload 修訂。

## Step 邊界

- Step-13 以 source-specific partial unique indexes 實作已解析 identity 的重複防護；
  `unresolved` evidence 不會被自動折疊。
- Payload 不同目前只表示不同 logical evidence。Step-14 定義 original、amendment、
  supplemental、unknown 值域；具體修訂關係仍須來源證據才能分類。
- `event_precision` 的正式值域留給 Step-17；在此只比較 evidence table 已保存的值。
- Identity 不使用 `filing_kind`、`xbrl_confirmed_at` 或未通過 source-evidence gate 的欄位。
