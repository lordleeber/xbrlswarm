# Repository agent instructions

## Code review follow-up

當使用者要求「看看 code reviewer 說的是否合理」或同義的 review 評估時：

1. 先依目前程式碼、測試、文件與專案契約逐項驗證 reviewer 的意見。
2. 若意見不合理，說明具體原因與證據，不修改程式。
3. 若意見合理，直接修正所有已確認的問題、補上相應 regression tests、執行完整測試，並更新目前的 PR；不需要等待使用者再次要求修正。
4. 若只有部分意見合理，只修正合理部分，並清楚說明未採納部分的理由。

## Step completion workflow

當使用者要求開始 ROADMAP 的某個 Step 或同義的開發任務時：

1. 完成該 Step 的程式、migration、文件與 regression tests，並執行完整測試。
2. 將變更 commit 並 push 到該 Step 的功能分支。
3. 推送完成後立即以 `main` 為 base 建立 PR，不需要等待使用者再次要求。
4. 若該分支已有 open PR，直接更新既有 PR，不得重複建立。
