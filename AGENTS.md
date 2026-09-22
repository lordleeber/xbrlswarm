# Repository agent instructions

## Code review follow-up

當使用者要求「看看 code reviewer 說的是否合理」或同義的 review 評估時：

1. 先依目前程式碼、測試、文件與專案契約逐項驗證 reviewer 的意見。
2. 若意見不合理，說明具體原因與證據，不修改程式。
3. 若意見合理，直接修正所有已確認的問題、補上相應 regression tests、執行完整測試，並更新目前的 PR；不需要等待使用者再次要求修正。
4. 若只有部分意見合理，只修正合理部分，並清楚說明未採納部分的理由。
