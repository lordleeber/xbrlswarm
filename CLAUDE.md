# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

`xbrlswarm` 蒐集、保存並稽核台灣上市櫃公司歷史財務報告／XBRL 的**發布證據**（哪家公司、哪一期、在什麼時間、經由哪個來源出現了什麼證據）。它不做財報數值分析。專案文件以繁體中文撰寫；程式碼與 commit message 用英文。

## 指令

只有 `python3`（沒有 `python`），pytest 也沒有安裝在系統環境。先建立 venv：

```bash
python3 -m venv .venv && .venv/bin/pip install -q -e '.[dev]'
.venv/bin/pytest                                   # 全套（pyproject 已設 -q、pythonpath=src）
.venv/bin/pytest tests/test_yahoo_search.py        # 單一檔案
.venv/bin/pytest tests/test_yahoo_search.py -k builder_url   # 單一測試
```

沒有 linter 或 formatter 設定，runtime 也沒有第三方依賴（`dependencies = []`）。

入口：

- `xbrlswarm-worker-api --database <已套用 migration 的 SQLite>`：Worker API，只監聽 loopback，**不可公開部署**。
- `python -m xbrlswarm.discovery <subcommand>`：階段 0 的 MOPS 來源探索、擷取與離線重播。用法見 README 的「階段 0 工具」。
- `python -m xbrlswarm.mops_pilot --database ... --output ...`：MOPS 試點。
- `node tools/yahoo_serp_capture.js <scenario> '<query>' --out DIR`：用有畫面的 Chromium 擷取 Yahoo SERP，輸出 fixture 格式。Node 找不到 playwright 時，用 `PLAYWRIGHT_MODULE` 指定套件路徑。詳見 `tests/fixtures/yahoo/README.md`。

Migration 沒有 runner。測試與 `mops_pilot` 都依檔名排序，對 `migrations/*.sql` 逐一執行 `executescript`。正式連線一律使用 `xbrlswarm.storage.connect_database`：它會開啟 foreign keys 與 recursive triggers，並驗證 evidence 不可變的 trigger 涵蓋所有來源欄位。

## 架構

- `src/xbrlswarm/domain/`：與來源無關的契約。
  - engine 順序 `mops → goodinfo → yahoo → google → grounded_ai`，以及 `PAUSED_ENGINES`（目前 Goodinfo 暫停）。
  - `ReportPeriod` 只有 Q1／Q2／Q3／FY，**FY ≠ Q4**，拒絕 Q4。
  - 兩類失敗語意：`RetryableFailure`（`rate_limited`、`transport_error`、`temporary_error`，留在同一 engine 重試）與 `SemanticExhaustion`（`not_found`、`rejected`，可轉到下一個 engine）。
  - 曆年制期末日期與版本化的發布時間窗規則。
- `migrations/` + `storage/`：SQLite `STRICT` 表 `task` 與 `evidence`。task identity 是 `(stock_id, fiscal_year, report_period)`，不含 `report_scope`。evidence 由 trigger 禁止改寫或刪除；各來源的去重由 partial unique index 負責。
- `worker_api.py`：以 wsgiref 提供 `/lease`、`/result`、`/stats`、`/status`、`/healthz`。
  - lease 派發、逾期回收、`retry_at` 到期回收，以及語意耗盡後的跨 engine 轉移，都在 `/lease` 的同一個 `BEGIN IMMEDIATE` 交易內完成。
  - `/lease` 還不能依 engine 篩選，`/result` 不能上傳 evidence。
  - **沒有重試次數上限**：固定輸入每次都得到 `temporary_error` 的情況會永遠重試。設計結果分類時要考慮這點。
- 來源模組（每個來源都是「擷取 → 解析 → 驗證 → evidence」的流程）：
  - MOPS：`mops_parser`、`mops_evidence`、`mops_pilot`。
  - Goodinfo：`goodinfo_*`，涵蓋清單、候選、詳細頁、locator、操作防護與 evidence。
  - Yahoo：`yahoo_search` 產生查詢、解析 SERP 並篩出候選；`yahoo_announcement` 審查 MOPS 形式的公告鏡像並做選擇。Yahoo 目前只到審查與選擇，還不寫入 evidence。
- `discovery/`（套件與 repo 根目錄的 `discovery/*.json`）：階段 0 的來源研究。產物由離線重播重新產生，例如 `docs/source-field-matrix.md`。

### 每個 Step 的產物三件組

每個 ROADMAP step 通常同時交付三樣東西：

- `contracts/<name>.json`：機器可讀的規則。
- `docs/step-N-acceptance.md`：驗收證據、決策、「原本以為」的踩坑、限制。
- 測試：會載入 contract，並與實際行為交叉比對。

改變行為時，三者都要同步，README 的進度段落也要更新。

### Fixture

`tests/fixtures/<source>/` 保存真實擷取的原始回應：

- body 為 `.html.gz`（只做無損 gzip）。
- `.meta.json` 記錄 request、status、final URL、sha256、`retrieved_at`；`origin` 為 `live` 或 `synthetic`。
- `.headers.json` 不含 cookie。
- `manifest.json` 列出案例，以及 `observed_identity`／`query_target`。

合成樣本必須標明 `synthetic`，不能被當成真實觀察。

## 不可違反的領域規則

- 時間語意不可互換：MOPS 發言時間（`announcement_at`）、文章發布時間、`retrieved_at`、HTTP header 都不能改名成 `xbrl_confirmed_at`。公開歷史的 `xbrl_confirmed_at` 目前是 NOT PUBLICLY VERIFIED。只有日期的事件存成 `event_precision=date`，不補午夜。
- 只支援曆年制公司。unknown 或非曆年制不能套用 12/31 邊界。
- 空結果不代表不存在。`not_found`／`rejected` 只能在完成該來源的搜尋與檢查之後回報；未知版面、challenge、bot 驗證或 consent 頁都是可重試失敗，不能用來觸發 fallback。
- 第三方來源只能作為證據或備援，不能取代 MOPS 的官方事實。
- Yahoo：SERP 必須由真實瀏覽器完成 `/_bv/` 轉址，curl 會失敗；文章頁用一般 HTTP 就能取得。只讀文章本體 `div.atoms[data-component=blocks]`，因為 meta description 與相關新聞卡片會重複相同的欄位標籤。

## 工作流程（AGENTS.md 與 ROADMAP 的約定）

- 一個 ROADMAP step 對應一個功能分支，也對應一個以 `main` 為 base 的 PR。完成程式、migration、文件與 regression tests，並跑完全套測試之後，commit、push、開 PR，不用等使用者再次要求。分支已有 open PR 就更新它，不要重開。
- 嚴格 TDD（ROADMAP §5）：先寫測試，並確認它因「功能尚未實作」而紅，才實作。修 bug 時先寫能重現的 failing regression。
- PR 標題與描述用**繁體中文**，標題格式為 `step-N：…`；commit message 用英文。
- 沒有 `gh`。PR 透過 GitHub REST API（repo `lordleeber/xbrlswarm`）開立，token 取自 `git remote get-url origin` 內嵌的 PAT。**不得移除、遮蔽或改寫 remote URL 裡的 PAT。**
- 使用者要求「看看 code reviewer 說的是否合理」時：逐項對照程式、測試與合約驗證。合理的直接修正、補 regression tests、跑全套測試並更新 PR；不合理的說明理由與證據。
- 對外來源（Yahoo、Goodinfo、MOPS）探測要低頻，查詢之間保留間隔。Goodinfo 在本環境會回 Cloudflare challenge。
