# 歷史 `xbrl_confirmed_at` 狀態

目前契約：

```text
historical xbrl_confirmed_at = NOT PUBLICLY VERIFIED
```

已知官方申報系統存在與申報 / 確認相關的時間資訊，但階段 0 尚未證實存在同時符合以下條件的公開歷史來源：

- 公開可存取
- 具有歷史資料
- 可重播
- 可批次查詢

在取得並審查這類證據以前，`xbrl_confirmed_at` 不得成為正式 Schema 的必填欄位。

以下資訊明確**不能**作為替代值：

- 重大訊息公告時間（`announcement_at`）
- 新聞 / 文章發布時間
- 爬蟲 `retrieved_at`
- HTTP `Date` 或 `Last-Modified`
