# MOPS 來源探索 fixture

此目錄只用來保存從公開 MOPS 來源研究中實際擷取的完整原始回應。

**不得**自行製造看似真實的 MOPS fixture。此目錄中的 fixture 必須來自實際擷取的回應，並且必須同時包含對應的 `.meta.json` 與 `.headers.json` sibling files。

預期目錄結構：

```text
tests/fixtures/discovery/mops/
  2330/2024/Q1/<capture>.<ext>
  2330/2024/Q1/<capture>.headers.json
  2330/2024/Q1/<capture>.meta.json
  ...
```

使用 `python -m xbrlswarm.discovery capture ...` 建立這些檔案。

## Step-2 固定批次擷取

使用官方 MOPS XBRL 下載介面一次擷取 12 個固定案例：

```bash
python -m xbrlswarm.discovery capture-mops-cases
python -m xbrlswarm.discovery verify-mops-captures
```

固定 capture 名稱為 `xbrl-consolidated`，raw body 以 `xbrl-consolidated.bin.gz` lossless 保存，避免把大型 iXBRL HTML 當成 Git 文字 diff；metadata 的 SHA-256 與 `size_bytes` 仍針對解壓後的原始 response bytes。

`verify-mops-captures` 不連網，只驗證：

- 12 個固定案例的 body / headers / metadata 三件組都存在
- metadata 指向預期的官方 MOPS URL
- HTTP status 為 200
- raw body SHA-256 與大小和 metadata 一致
- response headers 的保存格式有效
