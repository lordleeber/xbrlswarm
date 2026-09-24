# Step-41 — Goodinfo 試點案例驗收

固定試點案例為 4542／6147／2330 的 2024 Q1，另加 6147 2022 Q1 與 2330
2020 Q1（`xbrlswarm.goodinfo_pilot.PILOT_CASES`）。每案使用當年 4/1～6/30
的**探索用**清單日期範圍，不代表法定公告期限。

## 為何需要人工擷取

2026-09-24 的網路試點中，五筆清單請求都收到 HTTP 403，回應標頭為
`cf-mitigated: challenge`，頁面為 Cloudflare「Just a moment...」。這是網站
對自動化程式設的存取控制，與請求頻率無關。本專案**不自動解 challenge、
不偽裝瀏覽器、不借用瀏覽器 cookie**。改由人在瀏覽器正常開啟頁面並另存
HTML，程式只負責驗證與重播。

## 流程

```bash
ROOT=/path/to/goodinfo-captures   # 與 Step-40 操作入口共用的 output root
INBOX=/path/to/saved-pages

# 1. 列出尚待另存的頁面與檔名（清單匯入後才會出現詳細頁）
PYTHONPATH=src python -m xbrlswarm.goodinfo_manual plan --output-root "$ROOT"

# 2. 在瀏覽器開啟每個 url，另存成 save_as 指定的檔名放進 $INBOX
# 3. 匯入；任一頁被拒絕時 exit code 為 1，其餘頁面仍會處理
PYTHONPATH=src python -m xbrlswarm.goodinfo_manual import --output-root "$ROOT" --inbox "$INBOX"

# 重複 1～3 直到 plan 無輸出，再離線重播試點
PYTHONPATH=src python -m xbrlswarm.goodinfo_pilot --offline \
  --output-root "$ROOT" --report discovery/goodinfo_pilot_<date>.json
```

## 驗收規則

- 匯入的 bytes 走與網路回應相同的驗證：challenge 標記、HTML、清單標記；
  詳細頁須與候選 URL 的 `STOCK_ID`／`CLAIM_TIME`／`SUBJECT` 一致。
- 若檔案含瀏覽器寫入的 `saved from url=` 註解，該 URL 必須是同一清單
  查詢或同一公告；否則拒絕。
- 字元集取前 4096 bytes 的 `<meta charset>`，無則為 UTF-8；解碼失敗即拒絕。
- metadata 記錄 `capture_method: manual_browser`、`source_file`、
  `imported_at`，`retrieved_at` 取自檔案修改時間（`retrieved_at_basis:
  saved_file_mtime`）。`final_url` 等於要求的 URL；人工模式無法觀察轉址，
  以 `saved from url` 檢查作為唯一可用的佐證。
- 相同 bytes 重複匯入為 `already_imported`；不同 bytes 拒絕，不覆寫。
- 詳細頁只接受已匯入清單中、期別提示相符的前三個候選。
- `--offline` 試點只讀已驗證快取，缺少的頁面標為 `not_captured`，
  不連網、不佔 Step-40 冷卻時間。
- 不寫 evidence、不建立或完成 task。

契約見 `contracts/goodinfo-manual-capture.json`。
