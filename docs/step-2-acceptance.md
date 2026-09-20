# Step-2 驗收 — 擷取原始 MOPS 回應

## 範圍

Step-2 完成 ROADMAP 所要求的原始 MOPS response capture，不解析欄位，也不提前進入 Step-3。

固定案例：

```text
2330 台積電 × 2024 Q1/Q2/Q3/FY
6147 頎邦   × 2024 Q1/Q2/Q3/FY
4542 科嶠   × 2024 Q1/Q2/Q3/FY
```

共 12 個案例。

## RED

先新增測試定義：

- 每個固定案例必須對應官方 MOPS XBRL download URL
- Q1/Q2/Q3/FY 必須映射為 season=1/2/3/4
- 12 個案例都必須產生 body / headers / metadata 三件組
- verifier 必須重新計算 raw body SHA-256 與大小
- 缺少任何固定案例必須失敗
- raw body 被竄改必須失敗
- HTTP 200 的 security/error HTML 不得被視為成功 XBRL capture
- CLI 必須提供批次 capture 與離線 verify

## GREEN

新增：

```text
src/xbrlswarm/discovery/mops.py
```

提供：

- `build_mops_xbrl_capture()`
- `capture_mops_discovery_cases()`
- `verify_mops_capture_set()`

CLI：

```bash
python -m xbrlswarm.discovery capture-mops-cases
python -m xbrlswarm.discovery verify-mops-captures
```

## 真實來源擷取

2026-09-20 透過 GitHub Actions runner 直接連線：

```text
https://mopsov.twse.com.tw/server-java/FileDownLoad
```

固定參數：

```text
functionName=t164sb01
step=9
year=2024
report_id=C
season=1/2/3/4
```

成功擷取 12 / 12 個案例。每個案例保存：

```text
xbrl-consolidated.bin
xbrl-consolidated.headers.json
xbrl-consolidated.meta.json
```

總計 36 個 fixture files。

官方 response headers 的 `Content-Disposition` 回傳對應公司與季度的 iXBRL HTML filename；verifier 另確認 raw payload 具有 ZIP / iXBRL / XBRL 特徵，避免把 HTTP 200 的防護或錯誤頁誤認成成功資料。

## 測試與驗證

GitHub Actions runner：

```text
Python 3.11.16
22 passed
已擷取 12 個固定案例
已驗證 12 個固定案例
```

capture workflow 只用於產生本次真實 fixtures，完成後已從 branch 移除，不會合併進 `main`。

## Step-2 不做的事情

本 Step 不：

- 解析 XBRL / iXBRL 欄位
- 判定欄位是 direct / derived / optional
- 更新 source-field matrix 的實證結論
- 定義 production Schema
- 推導或捏造 `xbrl_confirmed_at`

以上留給 Step-3 與後續步驟。
