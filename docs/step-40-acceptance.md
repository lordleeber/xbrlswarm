# Step-40 — Goodinfo 操作防護驗收

Goodinfo 僅作為低量備援。`GoodinfoOperationalClient` 是清單與詳細頁的操作入口；
清單 CLI 也使用它。所有合作中的程序須共用 `output_root`，使清單和詳細頁共用
一把持久檔案鎖及下一次允許請求時間。單一 root 同時最多一個請求，前次請求
結束後至少等待 3 秒，再加上均勻分布於 `[0, 2)` 秒的 jitter。拒絕或 challenge
仍佔用請求額度；不把拒絕當作空清單。

完整、來源 metadata 與 raw bytes 相符的清單擷取，按公司及**精確起訖日期**
直接從本地回傳。相同日期範圍不再發送請求。詳細頁按 request URL 快取，
其來源 list provenance 沿用首次擷取時保存的值。快取不完整或驗證失敗時
直接報錯，人工檢查後才能清理；不覆寫已存在的 raw capture。

底層 `capture_announcement_list()` 與 `capture_goodinfo_detail()` 保留單次原始
擷取語意，供重播與測試使用；正式 Goodinfo 請求應經操作入口。
本步驟不新增 evidence、完成 task 或啟動大規模爬取。不同 `output_root` 的程序
無法共享冷卻時間，部署時須指定同一 root。即時 Goodinfo 在本環境仍遇到
403 challenge，尚無真實歷史頁面的端到端驗證。

驗收涵蓋同日期快取、清單與詳細頁共用延遲及 jitter、跨 client 序列化、
並行相同查詢去重、拒絕後冷卻、損壞快取拒絕及詳細頁 provenance。
契約見 `contracts/goodinfo-operational-guard.json`。
