# 階段 0 研究問題

在任何正式 Schema 定版前，必須以實際擷取的原始證據回答以下問題：

1. 公開 MOPS / XBRL 來源可以取得哪些欄位？
2. 能否取得歷史 filing date？
3. 能否取得歷史 filing time？
4. 能否從公開來源取得歷史 XBRL confirmation timestamp？
5. consolidated 與 individual 報告是否都存在？
6. 同一公司、同一 fiscal year、同一 report period 是否可能同時存在兩種 scope？
7. amendment / correction / supplemental filing 如何表示？
8. 是否存在穩定的公開 filing identifier？
9. 是否存在穩定、可重播的公開 locator / endpoint？
10. 如何可靠取得非曆年制公司的 fiscal calendar？

Step-21 已將第 10 題的官方來源能力、未解的公司別歷史資料與研究閘門記錄於
`docs/fiscal-calendar-research.md`；目前仍不能推導全市場的 fiscal calendar。

## 固定案例

永久來源探索案例固定為：

- 2330 台積電 — 2024 Q1/Q2/Q3/FY
- 6147 頎邦 — 2024 Q1/Q2/Q3/FY
- 4542 科嶠 — 2024 Q1/Q2/Q3/FY

此組案例刻意涵蓋高知名度公司、中等知名度公司，以及較冷門的上櫃公司。
