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
