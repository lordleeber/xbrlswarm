# Step-28 驗收 — 固定 engine 順序

正式定義 MOPS、Goodinfo、Yahoo、Google、Grounded AI 的固定先後順序。
Step-33 MOPS gate 尚未通過時，`not_found`、`rejected` 不得在下一次
lease 請求轉成 Goodinfo task；其他跨來源轉移也保持關閉。
已有的 `grounded_ai` task 耗盡時進入 `terminal_unresolved`，不再派發。
基礎設施失敗仍在同一 engine 等待，成功狀態不轉移。
完整 pytest suite 通過。
