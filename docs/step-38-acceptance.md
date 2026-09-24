# Step-38 驗收 — 保存 Goodinfo 公告時間

`accept_goodinfo_announcement` 從 Step-37 的已保存詳細頁原始回應重播解析，核對
bytes SHA-256、metadata、URL 的公告 identity 與頁面可見的公司、發言日期／時間、
主旨。它只接受非「董事會預計召開」的財報公告，而且詳細頁必須明示報導期間。
目前只支援呼叫端已獨立確認為曆年制的公司：報導期間必須從 task 財務年度的
1 月 1 日至其 Q1／Q2／Q3／FY 期末，頁面主旨的期別也須一致；公司、期別或
Goodinfo engine 不符時拒絕
寫入。這個前提不能由股票代號或查詢區間推測。

成功後新增 `source_type=goodinfo`、`evidence_type=material_announcement` 的
evidence。頁面「發言日期」與「發言時間」分別存成 `event_date`、`event_time`，
精度是 `second`；這三欄合起來對應 ROADMAP 的 `announcement_at`。
`retrieved_at` 只取 capture metadata，原始 detail bytes 的 SHA-256 保存在
`raw_payload_hash`。`source_url` 保存實際回應的已驗證 final URL；
`source_locator` 由 Step-39 的已驗證公告 identity 建立。
頁面可見主旨
存於 `source_subject`。清單標題仍是未驗證 hint，不寫入 `source_title`。
重播完全相同的公告和原始
bytes 時回傳既有 evidence；不同原始回應保留為另一筆不可變 evidence。

新 evidence 的 `verification_state=unverified`，不完成 task，也不寫入或推導
`xbrl_confirmed_at`。Step-39 的 locator 規則與舊版相容性詳見
`docs/step-39-acceptance.md`。
詳細頁的董事會／審計委員會日期、報導期間不會塞進公告事件時間欄位。
現有 evidence schema、Step-15 公告時間映射與 Step-17 精度限制已能表示此
資料，本 Step 無 migration。

測試使用 Step-37 格式的合成 HTML 及真實 SQLite migrations，驗證秒級保存、
擷取時間分離、錯誤 task／期間拒絕、排除預計召開、raw 竄改拒絕及重播去重。
此測試不聲稱已取得可重播的真實 Goodinfo 詳細頁 raw fixture。

機器可讀邊界見 `contracts/goodinfo-announcement-evidence.json`。
