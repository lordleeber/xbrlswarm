# Step-29 MOPS worker fixtures

`manifest.json` 固定 MOPS worker 開發前的來源樣本。Q1、Q2、Q3、FY 合併
XBRL 直接引用 `tests/fixtures/discovery/mops/2330/2024/` 的四份完整 raw
capture；不另複製大型檔案。manifest 記錄路徑與原始 body 的 SHA-256，
測試會用 Step-2 verifier 及 Step-3 observation 再次檢查。

本目錄的八組 `.html.gz`／`.pdf.gz`、`.headers.json`、`.meta.json` 是 2026-09-24
從 `mopsov.twse.com.tw` 實際擷取的原始回應。`.html.gz` 只做 lossless gzip；
SHA-256 與 `size_bytes` 針對解壓後的原始 response bytes。metadata 保存
request method、URL、POST form、request body hash、HTTP status、final URL、
response headers 及擷取時間；response `Set-Cookie` 不保存。

| 情境 | 官方來源 | 已觀察到的內容 |
| --- | --- | --- |
| amendment listing、detail、attachment | `ajax_t56sb31_q1`，上市、民國 113 年 Q1；detail 指向官方 PDF | 1314 中石化的合併財報更正列、明細與附件 |
| individual listing、detail、attachment | 同一查詢，上市、民國 113 年 FY；detail 指向官方 PDF | 1216 統一的個體財報更正列、明細與附件 |
| missing result | `ajax_t203sb01`，公司代號 `9999` | 頁面顯示「查無資料」 |
| unexpected layout | `FileDownLoad`，1216／2024 FY／`report_id=A` | HTTP 200 卻回傳「下載檔名或路徑不正確」HTML，不是 XBRL |

個體更正明細與 PDF 附件是個體財報更正的來源證據，**不是個體 XBRL 文件**。
本次查詢的 `report_id=A` 沒有取得可用個體 XBRL，因此 manifest 明記
`individual_xbrl_document=not_captured`。PDF 附件也不能代替可解析的 XBRL，
不能單憑清單或附件直接推導 XBRL `filing_kind` 或修訂關係。

「查無資料」只描述這次 `9999` 查詢的回應；不能推論某家公司或某期財報
不存在。HTTP 200 的錯誤頁也不能當成成功的 XBRL 擷取。後續 Step-30
解析器須按來源與 layout 分支處理這些 raw fixture，不得以檔名或 status
臆測證據種類。
