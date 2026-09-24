# Step-29 驗收 — 定版 MOPS 測試 fixture

`tests/fixtures/mops/manifest.json` 指向已驗證的 2024 Q1／Q2／Q3／FY
合併 XBRL raw captures，並固定八組來自官方 MOPS 的完整回應三件組：
更正清單與明細及其 PDF 附件、個體財報更正清單與明細及其 PDF 附件、
查無資料與非 XBRL 錯誤頁。每組都有請求、
headers、擷取時間與原始 body hash，可離線重播與驗證。

目前有個體財報更正清單、明細及 PDF 附件，沒有個體 XBRL 文件；PDF
附件不能視為 XBRL 原文。這些限制已寫入 manifest 與 fixture README，
不會將缺少的文件冒充已取得的報告，也不會把「查無資料」提升成
財報不存在的主張。本 Step 不新增 production parser 或 migration。
