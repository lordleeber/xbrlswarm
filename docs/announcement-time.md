# Step-15 — 重大訊息公告時間

當可追溯的來源明確標示同一筆重大訊息的「發言日期」與「發言時間」時，
以 `evidence_type=material_announcement`、`event_date`、`event_time`、
`event_precision=second` 保存。
這三個欄位合起來是 ROADMAP 所稱 `announcement_at` 的等價表示；
不另設單一 timestamp 欄位，避免在尚未確認時區時捏造資訊。
來源值原樣保留，不從其他時間欄位補出缺少的發言日期或時間。

`announcement_event_fields` 只接受已從來源辨識出的發言日期與時間。
呼叫端必須確保兩者屬於同一公告、標籤確為發言日期／時間，並保存可追溯的來源位置；
若任一欄缺失或空白，函式會拒絕建立完整公告時間。
這個映射不代表目前已有 Goodinfo 或其他第三方頁面的正式擷取器；
真正的來源欄位解析與格式驗證仍須由各來源實作及其 raw-backed tests 證明。

`retrieved_at` 是擷取時間，文章發布時間是文章事件時間，均不可當作公告發言時間。
`xbrl_confirmed_at` 是另一種尚未公開驗證的 XBRL 確認時間，不能由公告時間改名取得。
即使公告與文件恰有相同日期／時間，也必須依 `evidence_type` 分開查詢與保存。

本 Step 僅定義完整「發言日期＋發言時間」的映射；日期／時間精度值域
由 Step-17 的 `docs/event-time-precision.md` 定義，來源解析留待對應的來源 Step。
