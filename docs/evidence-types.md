# 證據類型契約

## 正式值域

`evidence_type` 必須是下列其中之一：

| Evidence type | 角色 | 描述 |
| --- | --- | --- |
| `xbrl_document` | document | XBRL／iXBRL 文件 artifact |
| `financial_report_document` | document | 未分類為 XBRL artifact 的財務報告文件 |
| `material_announcement` | announcement | 重大訊息公告事件，包含可追溯並識別為該特定上游事件的鏡像 |
| `search_mirror` | discovery | 尚不足以識別上游 artifact／事件的搜尋結果、文章或鏡像 |
| `manual_review` | adjudication | 不修改來源證據的人工審查或 resolution record |

正式 enum 位於 `xbrlswarm.domain.EvidenceType`，機器可讀契約位於 `contracts/evidence-types.json`。

## 分類原則

Evidence type 描述「這筆 evidence 是什麼」，不是「從哪裡取得」。例如：

- MOPS XBRL download 是 `xbrl_document`，來源可以是 `mops`。
- Goodinfo 詳細頁若可追溯並識別為一筆特定 MOPS 重大訊息，描述的就是 `material_announcement`，來源可以是 `goodinfo`；不得同時分類為 `search_mirror`。
- 搜尋結果 snippet 或只提供文章線索的頁面是 `search_mirror`；它僅適用於尚不足以建立已識別上游 artifact／事件的 discovery evidence。
- 當後續驗證已能識別特定上游 artifact／事件時，必須依該上游對象的種類分類；例如可追溯的重大訊息鏡像必須升格為 `material_announcement`。
- 人工裁決另存 `manual_review`／resolution record，不得改寫原始 evidence。

因此 `evidence_type` 與 `source_type` 是不同維度。同一來源可產生不同 evidence types，同一 evidence type 也可由官方來源或第三方鏡像提供。

## 驗證狀態不是證據類型

`verification_state` 描述 evidence 是否已佐證、衝突、拒絕或解決；它不改變 evidence 原本的種類。`manual_review` 是審查記錄的 evidence type，也不等於未來 verification state 中可能出現的同名字詞。

## 時間語意

Evidence 不保證一定具有 event time。只有來源明確提供並能辨識語意時，才保存相應事件時間：

- `material_announcement` 的發言日期／時間是公告事件時間。
- `search_mirror` 的文章或索引時間仍是 mirror／article 語意，不能改名為公告時間或 XBRL confirmation time。
- `xbrl_document` 或 `financial_report_document` 的存在，不足以自行推導 filing／confirmation time。
- `manual_review` 的 reviewed time 是審查動作時間，不是來源事件時間。
- `retrieved_at` 永遠是 capture metadata，不是任何上游事件時間。

禁止把上述時間全部塞進單一 `published_at`。後續 schema 可以使用帶有 evidence type／event semantic 的日期、時間與精度欄位，但必須保留來源實際聲稱的語意，且允許事件時間缺值。

## 本 Step 的邊界

本契約只定義 evidence type 值域與語意分界，不定義 evidence table、時間欄位、verification state enum、冪等鍵或人工審查 schema；這些由後續步驟處理。
