# Step-7 驗收 — 定義證據類型

## 範圍

Step-7 建立來源無關的 `EvidenceType` 領域契約，至少區分：

```text
xbrl_document
financial_report_document
material_announcement
search_mirror
manual_review
```

本 Step 不建立 production Schema、evidence table、時間欄位或 verification state enum。

## RED

先新增測試，要求：

- domain enum 必須精確包含五個 ROADMAP 規定值。
- machine-readable contract 與 enum 必須一一對應、不得重複。
- `mops` 等來源名稱、`corroborated` 等驗證狀態及時間欄位名稱不得被解析成 evidence type。
- contract 必須將 source、verification、event time 與 capture time 分成不同維度。
- contract 必須明確拒絕通用 `published_at` 模型。
- contract 必須將可追溯並識別為特定重大訊息的鏡像分類為 `material_announcement`，並排除 `search_mirror`。
- `search_mirror` 僅適用於尚未識別上游 artifact／事件的 discovery evidence。

測試先因 `xbrlswarm.domain.EvidenceType` 尚未存在而在 collection 階段失敗。

## GREEN

新增：

```text
src/xbrlswarm/domain/evidence_type.py
contracts/evidence-types.json
docs/evidence-types.md
```

enum 提供正式值域與嚴格 parser；JSON contract 供後續 schema 步驟機器化檢查，並明確規定可追溯的重大訊息鏡像與未解析 discovery evidence 的互斥分類；文件定義分類例子與語意邊界。

## 語意分離

```text
evidence_type       = artifact / event 是什麼
source_type         = evidence 從哪個來源取得
verification_state  = evidence 如何被驗證
event time          = 來源所聲稱的事件時間（可缺）
retrieved_at        = 系統何時擷取資料
```

這些維度不得互相改名或推導。尤其文章時間、公告時間、XBRL confirmation time 與 crawler retrieval time 不能統一叫做 `published_at`。

## 不包含

本 Step 不：

- 建立 evidence table 或 migration
- 決定 event date/time/precision 的 schema
- 定義 verification state
- 定義 evidence 冪等鍵
- 實作人工審查流程

本 Step 正式程式碼遠低於 800 行，不需要拆分。
