# HCS Plus Strict Habit Log

## D3854 / preserve specific snapshot blocker detail

- `#拆解問題` / `#差距分析` / `#語意含義`：invalid snapshot 已能產生 browser manual review，但 generic blocker 與具體 hash/provider error 同時存在時，action detail 仍可能掩蓋真正證據。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以 generic error + hash mismatch fixture 先取得 `1 failed` RED；沿用後端 repair queue／reading notice 的 precedence，移除 generic text、保留具體 detail，無具體 detail 才 fallback。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：focused `16 passed`，更新 cache-buster、API/operator/architecture contract；只改瀏覽器 read-only evidence detail，不修改 snapshot、artifact、index、review、queue 或 rerun。

## D3853 / surface invalid snapshot action in browser quality policy

- `#拆解問題` / `#差距分析` / `#語意含義`：後端 repair queue 對 invalid／`valid=false` snapshot 已產生人工審核，但瀏覽器 quality action 未投影此 blocker，preview 可能只有 blocked reading notice 而沒有 action。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以 ` INVALID ` 與 hash mismatch fixture 先取得 `1 failed` RED；quality gate 先判定 snapshot integrity，保留 error/hash detail，再沿用既有 `reportRecommendedAction` 產生 `manual_review`。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：focused `16 passed`、前端/static/HCS `247 passed`、quality/preview/storage `281 passed`、文件/import `573 passed`，四個 JS syntax、Python compile、行數、`git diff --check` 與正式 runtime health/ready/assets `200` 通過；只改瀏覽器 read-only action projection，不修改 snapshot、artifact、index、review、queue 或 rerun。

## D3852 / normalize browser data-trust and freshness states

- `#拆解問題` / `#差距分析` / `#語意含義`：D3851 已收斂品質 gate／snapshot 的格式變體，但 report-facing data-trust action、fresh-data boundary、徽章與 decision-freshness label 仍直接比較原始狀態；` ERROR ` 可能漏掉人工複核，` FRESH ` 可能顯示未知，` CURRENT ` 可能露出原始字串。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：新增 error/fresh/current 的跨層 fixture，先取得 `1 failed` RED；將品質 policy、閱讀邊界與資料可信度 UI 統一為 trim/lowercase projection，保留資料新鮮度與結論新鮮度的獨立語意。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：focused reading-boundary suite `15 passed`、前端/static/HCS `246 passed`、報告全套 `1636 passed, 1 skipped`、refresh/storage/runtime `42 passed`、文件/import `573 passed`；Node syntax、Python compile、`git diff --check`、靜態模組行數與正式 runtime health/ready/assets `200` 通過。此批只改瀏覽器 read-only display/action classification，不回寫 snapshot、artifact、index、review、queue 或 rerun。

## D3851 / normalize browser quality and snapshot boundary states

- `#拆解問題` / `#差距分析` / `#語意含義`：品質狀態已採 allowlist，但 snapshot `VERIFIED`、` INVALID ` 與注入 helper 的大小寫值仍可能走不同分支，造成缺 gate、snapshot blocker 或 warning 被低估。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先加入大寫 verified 缺 gate、空白 invalid 與大寫 helper fixture，取得 `3 failed` RED；修正為 trim/lowercase 後再套用既有 known-state policy，保留 `unverified` warning 與 invalid blocked 語意。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：同步 API、operator、architecture 與 cache-buster；閱讀邊界 `14 passed`，品質 backend `269 passed`、前端/static/HCS `245 passed`、品質前端/HTTP `96 passed`、文件/import `573 passed`，未知／格式變體仍導向正確的人工核對或阻斷，不修改 snapshot、artifact、index、review、queue 或 rerun。

## D3850 / align browser quality-state recording with backend allowlist

- `#拆解問題` / `#差距分析` / `#語意含義`：後端品質 metadata repair 與 conformance 已拒絕未知狀態，但瀏覽器 `recorded()` 只看非空字串；`future`／`experimental` 可能讓 preview action 與 reading boundary 跳過未記錄提示，大寫 known status 也可能被誤判為非通過。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先加入全未知、部分未知與大寫 known-status fixture，取得 `1 failed` RED；前端改用與後端一致的 known-state allowlist，品質 gate 狀態不分大小寫，snapshot integrity 維持獨立的 `unverified` warning 語意。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 API、operator、architecture contract；閱讀邊界 `12 passed`，跨層品質／前端／HTTP 回歸 `370 passed`，Node syntax、Python compile、static line guard 與文件檢查完成。未知品質狀態仍導向人工核對，不修改 snapshot、artifact、index、review、queue 或 rerun。

## D3849 / fail closed on unknown quality-gate statuses

- `#拆解問題` / `#差距分析` / `#語意含義`：`report_lint` 與 `content_credibility` 的 step builder 對空 payload、unknown 或 failed/rejected status 沒有完整狀態政策，可能把無法證實的品質結果當成 passed。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以空 gate、unknown 與 failed/rejected fixture 先取得 `2 failed` RED；改為明確 allowlist，只有 passed 通過，warning/未確認回 warning，failed/rejected/blocked 或 blocker 回 blocked，並保留 case-insensitive status normalization。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 API、operator、architecture contract；conformance/content/storage `101 passed`、lint/quality audit/repair `105 passed`、import/docs `70 passed`，Python compile、`git diff --check` 通過，`conformance_steps.py` 122 行。正式 reload 後 health/ready `200/200`，current `165/85`、conformance `80/71/14`、content `93/59/13`、evidence `134/28/3`，historical `1175/59` 且 artifact `present=59/unavailable=0`，doctor canonical paths 與 RQ 正常。本批只改 read-only conformance classification，不寫 snapshot、artifact、index、review、queue 或 rerun。

## D3848 / keep missing final-audit evidence visible

- `#拆解問題` / `#差距分析` / `#語意含義`：產製 conformance 的 final-audit step 對空 payload 使用 `passed` fallback；因此缺少最終稽核證據的輸出仍可能被標成通過，和歷史品質稽核對 `not_recorded` 缺口的語意不一致。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先新增完整可見 artifact、fresh data、approved evidence、passed content 的 missing-final-audit fixture 取得 RED，再只把缺少或 `not_recorded` 的 final audit 收斂為 warning；critical 與 blocked/failed/rejected 仍優先 blocked，沒有從歷史/API projection 借用 metadata。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 API、operator、architecture contract；conformance/steps `10 passed`、content credibility `28 passed`、report/storage `90 passed`、tracking refresh/artifact/runtime `25 passed`、品質前端/文件 `342 passed`、受影響模組與 import/docs `614 passed`，可選商業頁三 viewport `3 passed`，Python compile、`git diff --check` 通過。全套基線為 `8521 passed, 6 skipped, 75 subtests passed` 並有 3 個失敗；舊 final-audit placeholder 期待與新契約已由 targeted regression 修正，commercial visual timeout 後續獨立重跑通過。正式 reload 後 health/ready `200/200`，current `165/85`、conformance `80/71/14`、evidence `134/28/3`，historical `1175/59` 且 artifact `present=59/unavailable=0`，doctor canonical paths 與 RQ 正常。本批只改 read-only conformance classification，不寫 snapshot、artifact、index、review、queue 或 rerun。

## D3847 / keep quality-audit artifact evidence strict

- `#拆解問題` / `#差距分析` / `#語意含義`：quality audit 的 Markdown context reader 以 `errors="replace"` 解析不可解碼 bytes，可能把壞檔判成 `present/partial`；artifact marker summary 在 decode 失敗後也把存在但不可讀的檔案回報成 `not_found`，操作員會得到錯誤的 artifact evidence。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先以 invalid UTF-8 Markdown fixture 重現 `not_found` 與 `present` RED，再新增共用 strict UTF-8 decoder；不可解碼 Markdown/HTML 只回 `unavailable`，可讀的另一 artifact 仍可提供 marker evidence，不輸出 replacement text、不借用其他報告值。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 API/operator/architecture contract；artifact/quality `53 passed`、refresh/storage `89 passed`、品質/前端/文件 `342 passed`、import/runtime `546 passed`、preview `121 passed`，Python compile 與 `git diff --check` 通過；正式 runtime reload 後 `/healthz`、`/readyz` `200/200`，live current-quality `165/85/5/85`、historical `1175/59/59/truncated=false`，59 筆 historical artifact marker 全數 `present`、`unavailable=0`，doctor canonical report index/operational DB、local storage 與 RQ 正常。本批不改報告內容、quality gate、snapshot/index 寫入、review、queue 或 rerun side effect。

## D3846 / fail closed on malformed report artifact encodings and shapes

- `#拆解問題` / `#差距分析` / `#語意含義`：report index、preview、compare、rerun、download 等 read path 對非 UTF-8 artifact 只要直接 decode 就可能中止整個操作；合法 JSON 陣列或純量也可能在 metadata/rerun path 被當成 object 呼叫 `.get()`，把不可驗證資料誤變成 500。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先以 invalid UTF-8 與 `[]` fixtures 取得 RED，再只在各 reader 邊界加入 decode/root-shape fail-closed；index/preview/compare 回 unavailable/fallback，data trust/freshness 保留 unknown，rerun 與 HTML/Markdown download 回 HTTP 400，不以 replacement character、其他 artifact 或 index 值補內容。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 API/operator/architecture contract；decode/shape boundary `10 passed`，refresh/storage/artifact `89 passed`、tracking `9 passed`、品質/前端/文件 `342 passed`、import/architecture/docs/runtime `614 passed`、preview/boundary `131 passed`，Python compile 與 `git diff --check` 通過；正式 runtime reload 後 `/healthz`、`/readyz` `200/200`，live current-quality `165/85/5/85`、historical `1175/59/0`，doctor canonical report index/operational DB、local storage 與 RQ 正常。本批不改報告內容、quality gate、snapshot/index 寫入、review、queue 或 rerun side effect。

## D3845 / derive refresh freshness from the persisted snapshot

- `#拆解問題` / `#差距分析` / `#語意含義`：data-only refresh 已寫入新的 snapshot，卻再以 `output_dir + bundle.data_key` 讀檔計算 freshness；storage abstraction 沒有 filesystem path 時，明確的 `needs_rerun` 會被錯誤降級成 `unknown`。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先以 InMemoryStorage 的 changed-price fixture 鎖定 `unknown` RED，再讓 `report_refresh_service` 直接消費同一份 `refreshed_snapshot`；不從 path、index 或舊 snapshot 猜 freshness，也不改 refresh diff、保存內容或 rerun side effect。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 API/operator/architecture contract；target refresh `13 passed`，refresh/storage/artifact regression `89 passed`、tracking workflow `9 passed`、品質/前端/文件 `342 passed`、import/architecture/docs/runtime `546 passed`、preview/boundary `121 passed`，Python compile 與 `git diff --check` 通過；正式 runtime reload 後 health/ready `200/200`，live current `165/85/5`、historical `1175/59`，doctor canonical paths 正常。本批只修 response freshness 的 storage-independent truth。

## D3844 / co-locate certification review sidecars with report artifacts

- `#拆解問題` / `#差距分析` / `#語意含義`：legacy certification review 仍以 flat `output_dir/<base>.review.json` 為唯一位置；nested report bundle 的 review 會被讀不到，新寫入也和 HTML/Markdown/data 分離，刪除或 retention 可能留下孤兒 sidecar。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先以 nested read/write fixture 取得 RED，再讓 `report_review_gate` 使用 canonical review candidates，保留 flat legacy fallback；route 注入 runtime storage，bundle delete/expire/orphan cleanup 都納入 review key，遇到 invalid JSON 仍 fail closed，不借用 operational review ledger。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 API/operator/architecture contract；review gate/storage/cleanup focused `5 passed`，storage/review/artifact integration `81 passed`，品質/前端/文件 `342 passed`，import/architecture/docs `595 passed`，preview `110 passed`，runtime/storage `19 passed`，Python compile 與 `git diff --check` 通過；正式 runtime reload 後 health/ready/reports/current-quality/historical/review `200`，live current `165/85/5`、historical `1175/59`，首筆 review status `pending_review` 且 candidates 正確。本批不改報告內容、quality gate、snapshot、index、operational review ledger、queue 或 rerun state。

## D3843 / resolve rerun source artifacts through canonical storage

- `#拆解問題` / `#差距分析` / `#語意含義`：`report_rerun_service` 在沒有顯式 storage 的直接呼叫路徑只檢查 `output_dir/filename`，沒有沿用 partitioned artifact candidates；nested HTML 存在時仍會回覆「找不到報告」，而且後續 snapshot/重跑層也無法取得同一來源。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先以 nested `YYYY-MM/TICKER` source bundle 取得 RED，再由 `storage_for_existing_output_dir()` 與 `ReportArtifactLocator` 統一解析 HTML，將 resolved storage 傳入 snapshot、full/final rerun 與 renderer persistence；保留 legacy flat candidate，不借用 index row 或另一份報告補 artifact。focused regression `1 passed`。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：此修正讓操作員從歷史品質 target 進入重跑時，nested 與 flat artifact 使用同一查找規則；重跑/儲存 `54 passed`、preview `110 passed`、品質/前端/文件 `400 passed`、import-boundary `505 passed`、runtime/storage `19 passed`，Python compile、Node syntax、`git diff --check` 通過；正式 runtime health/ready `200/200`，doctor canonical paths 正常，live current-quality `165/85/5/85`、historical `1175/59`，實際 locator 成功解析 nested HTML/Markdown/data keys。本批不改報告內容、品質 gate、snapshot 資料、index、review、queue 或 rerun state。

## D3842 / invalidate current-quality cache by index fingerprint

- `#拆解問題` / `#差距分析` / `#語意含義`：current-quality summary 原本只以 30 秒 TTL 判斷 cache；report index 的 `updated_at`、file mtime 或 stored content/data hash 改變後，TTL 內仍可能顯示舊 gate 分布與 bounded target，讓操作員看到資料已更新但結論未同步。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以同一 output scope 先取得 warning summary，再變更 row fingerprint 與 conformance 取得 RED；report index 新增不載入 artifact 的 latest-row fingerprint，current-quality 與 quality audit 共用欄位與 digest，indexed 與 historical-filter scope/filter 另行隔離，fingerprint 改變即 bypass 舊 projection，讀不到 fingerprint 時也不重用 cache。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：新增 current-quality stale-cache、cross-scope isolation 與 SQLite fingerprint regression，focused backend `58 passed`，品質/前端/索引/文件回歸 `400 passed`、import-boundary `504 passed`、runtime/storage `21 passed`，Python compile、Node syntax 與 `git diff --check` 通過；正式 runtime/live current `165/85/5/85`、historical `1175/59` 且 current projection `165/85`，health/ready `200/200`、helper assets `200`、official launcher/worker/8080 與 doctor canonical paths 正常。本批只修 read-only cache invalidation，不改 snapshot、artifact、index 寫入、review、queue 或 rerun state。

## D3841 / fail closed on incomplete full-index pagination

- `#拆解問題` / `#差距分析` / `#語意含義`：current-quality 與 historical quality audit 的 `audited_reports` 依賴全量 index pagination；原 collector 只看第一頁 total，後續 page 缺失或異常時仍交付 partial rows，會讓 undercount 看起來像合法完整 scope。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以 declared total `3` 但第二頁空回，以及 declared total `5`、非最後頁只回一筆取得 RED；collector 新增 `pagination.complete`，核對每頁 list、total、page size、非最後頁長度與最後 rows count，quality callers 只對明確 incomplete 回 unavailable，不猜算缺少資料。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 API/operator/architecture contract，新增 current-quality、indexed audit、historical latest caller 覆蓋，完整 backend/frontend/history/static/docs regression `392 passed`，Python compile、Node syntax 與 `git diff --check` 通過；live current `165/85/5/85`、historical `1175/59/5`、current projection `165/85`，health/ready、official launcher/worker/8080 與 doctor canonical paths 正常。本批不改 audit count、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3840 / validate current-quality navigation target shape

- `#拆解問題` / `#差距分析` / `#語意含義`：current-quality aggregate scope 與 bounded target list 是兩層資料；原 validator 只確認 returned 數量，沒有確認 target 真的是 non-passed、具備歷史導覽檔名與可顯示的三個 gate 狀態，會把 passed report 當成待查看項目。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以 `audited=2、non_passed=1、items_total=1` 搭配一筆全 `passed/approved` target 取得 RED，另以缺 filename target 覆蓋不可導覽邊界；watchlist/history validator 現在要求非空 filename、已知 normalized statuses，且至少一個 gate 非 passed，任一筆失效即 fail closed，不從 aggregate map 猜測或補造 target。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新兩個 current-quality asset cache-buster 與 API/operator/architecture contract，focused target tests 通過，相關 frontend/history/report-quality/static/docs `342 passed`、backend current-quality `11 passed`，Node syntax 與 `git diff --check` 通過；live current `165/85/5/85` 且第一筆 target 含 filename 與三個 gate status，historical `1175/59`、current projection `165/85` 且 `item_limit=0` 無 target list，assets `200` 且與本地一致，health/ready、official launcher/worker/8080 與 doctor canonical paths 正常。本批不改 audit count、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3839 / reject unknown current-quality keys

- `#拆解問題` / `#差距分析` / `#語意含義`：status/verdict map 會以 `Object.values()` 計算總和，但 renderer 只顯示已知 labels；未知 key 可能讓總和看似完整，同時讓一部分報告從操作員摘要消失。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以 `future=1` 與既定 bucket 加總到 `audited=2` 取得 RED；兩個 current-quality helper 的 shape validator 現在要求 mapping、既定 keys、有限非負整數，未知 key 直接 fail closed，不把它當成已知狀態或補回其他 bucket。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新兩個 current-quality asset cache-buster 與 API/operator/architecture contract，focused unknown-key `2 passed`，完整 history/report-quality/static/docs/current-quality regression `350 passed`，Node syntax、line guard 與 `git diff --check` 通過；live current `165/85/5/85`、三組 status sum `165`，historical `1175/59/5/59`、current projection `165/85`，assets `200` 且與本地一致，health/ready、official launcher/worker/8080 與 doctor canonical paths 正常。本批不改 audit count、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3838 / bound current-quality non-passed scope

- `#拆解問題` / `#差距分析` / `#語意含義`：current-quality 的 gate status 分布各自以 `audited_reports` 為分母，但 union 型 `non_passed_reports` 沒有上限檢查；它不是任一單一 status map 的加總，卻仍必須落在同一 audited scope 內。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以 `audited=1`、`non_passed=2`、`items_total=2` 取得 RED；watchlist/history 兩個 validator 加入 `non_passed <= audited`，保留合法 zero、status 分布與 bounded target，不借用 gate status 推算 union count。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新兩個 current-quality asset cache-buster 與 API/operator/architecture contract，focused scope `2 passed`，完整 history/report-quality/static/docs/current-quality regression `348 passed`，Node syntax、line guard 與 `git diff --check` 通過；live current `165/85/5/85` 且三組 status sum `165`，daily `165/2`、historical `1175/59/5/59`，assets `200` 且與本地一致，health/ready、official launcher/worker/8080 與 doctor canonical paths 正常。本批不改 audit count、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3837 / validate top-level quality distributions

- `#拆解問題` / `#差距分析` / `#語意含義`：provenance、重跑策略、context、review 與歷史 version map 都是 missing scope 的一對一分布；逐 bucket 轉數字不足以證明它們能代表全量缺口，partial map 會製造虛假的摘要完整度。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以合法整數、可省略零 bucket、未知 key、fractional 值與 sum mismatch 建立 RED；新增共用 `completeDistribution`，由兩個 renderer 對 ephemeral API payload 移除不可信 optional map，保留全量缺口和其他獨立 evidence，不借用其他欄位補數字。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新三個 asset cache-buster 與 API/operator/architecture contract，focused distribution `2 passed`，完整 history/report-quality/static/docs regression `335 passed`，Node syntax、line guard 與 `git diff --check` 通過；live daily `2=1+1`、historical `59=15+15+14+15`、4/4 context maps、bounded `59/5/5/truncated=true`，三個 assets `200` 且與本地一致，health/ready、official launcher/worker/8080 與 doctor canonical paths 正常。本批不改 audit count、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3836 / enforce per-pipeline context scope

- `#拆解問題` / `#差距分析` / `#語意含義`：top-level pipeline missing partition 正確時，單一 pipeline 的 context 分布仍可能超過自身 missing 分母，原 UI 會顯示超額模式準備度。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以 v1 missing `1`、context `present=2` 並保持總 missing 正確取得 RED；新增 per-pipeline context validator，要求已知 bucket、有限非負整數與 context 加總等於 entry missing，任一 entry 失效時只隱藏模式 context。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新三個 asset cache-buster 與契約，focused context-scope `2 passed`，完整 history/report-quality/static/docs regression `332 passed`，Node syntax、line guard 與 `git diff --check` 通過；live daily `missing=2`、4/4 context map 完整，historical `missing=59`、pipeline sum `59`、4/4 context map 完整，bounded `59/5/5/truncated=true`，assets `200` 且與本地一致，health/ready、official launcher/worker/8080 與 doctor canonical paths 正常。本批不改 audit count、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3835 / suppress context outside valid pipeline scope

- `#拆解問題` / `#差距分析` / `#語意含義`：pipeline missing partition 失效時，renderer 原本仍可能顯示同一 partial map 的「模式上下文」，讓局部準備度被誤讀成完整模式結論。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以 `missing=3`、pipeline `1+1` 並附 context entry 取得 RED；讓 history/watchlist 共用同一 pipeline scope validity，scope 失效時同時隱藏模式 gap/context，正常 partition 與 legacy context fallback 保持既有行為。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新兩個 renderer cache-buster 與契約，focused context suppression `2 passed`，完整 history/report-quality/static/docs regression `330 passed`，Node syntax、line guard 與 `git diff --check` 通過；live daily `2=1+1`、historical `59=15+15+14+15`、bounded `59/5/5/truncated=true` 正常，audit-scope/watchlist/history assets `200` 且與本地一致，health/ready、official launcher/worker/8080 與 doctor canonical paths 正常。本批不改 audit count、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3834 / enforce pipeline missing scope

- `#拆解問題` / `#差距分析` / `#語意含義`：watchlist/history 逐欄顯示 pipeline 缺口，但沒有確認各 entry 是否完整分割 top-level 缺口；部分 map 會被誤讀成全量模式分布。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以 `missing=3`、pipeline `1+1` 取得 RED；新增共用 audit-scope helper，要求 entry、有限非負整數與加總一致，矛盾時隱藏模式缺口，不改 backend audit payload 或 legacy context fallback。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新正式 asset load order、API/operator/architecture 契約與兩個 Node fixture，focused pipeline scope `3 passed`，完整 history/report-quality/static/docs regression `330 passed`，Node syntax、line guard 與 `git diff --check` 通過；live daily `2=1+1`、historical `59=15+15+14+15`，bounded `59/5/5/truncated=true`，asset `200` 且與本地一致，health/ready、official launcher/worker/8080 與 doctor canonical paths 正常。本批不改 audit count、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3833 / enforce action freshness projection scope

- `#拆解問題` / `#差距分析` / `#語意含義`：current-quality 的總 action map 與 freshness 分布 map 應是同一份逐報告 projection；原 formatter 未核對逐 action 加總，矛盾 payload 會同時顯示兩套不同數字。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以總數 `manual_review=1`、freshness `manual_review=2` 取得 RED；新增共用 map validator，要求有限非負整數、已知 freshness bucket 與逐 action 加總一致，矛盾時只保留可信總數，不改 backend projection 或 legacy fallback。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 action helper cache-buster 與 API/operator/architecture 契約，focused action tests `5 passed`，完整 history/report-quality/static/docs regression `328 passed`，品質摘要/dashboard `85 passed`，Node syntax、Python compile、line guard 與 `git diff --check` 通過；live current-quality `165` 份、非通過 `85`、action `81/4` 且 freshness 加總一致，helper asset `200` 且與本地一致，health/ready、official launcher/worker/8080 與 doctor canonical paths 正常。本批不改 action picker、daily queue、snapshot、artifact、index、review 或 rerun state。

## D3832 / enforce historical offset scope

- `#拆解問題` / `#差距分析` / `#語意含義`：歷史 audit 的 page offset 沒有納入 bounded scope；`offset=99、total=5、returned=1` 會形成不可能的「第 100-5 份」頁碼。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以異常 offset fixture 取得 RED，當 total/returned 明確存在時要求 `offset <= total` 且 `offset + returned <= total`，不對缺失 offset 或 legacy 欄位補造頁碼。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 renderer cache-buster 與測試契約，完整 history/report-quality/static/docs regression `327 passed`，Node syntax、line guard 與 `git diff --check` 通過；live historical page 1 為 `offset=0 / returned=5 / total=59`，scope chain 正常，renderer asset `200` 且與本地一致，health/ready `200/ready`、official launcher/worker/8080 與 doctor canonical paths 正常。本批不改 audit count、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3831 / enforce historical item-total scope

- `#拆解問題` / `#差距分析` / `#語意含義`：歷史 audit 的主缺口數與 bounded `items_total` 未互相核對；`missing=5、items_total=3、items_returned=3` 會把不完整範圍顯示成 5 份缺口中的完整 3 份。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以 `missing=5 / items_total=3` 取得 RED，明確存在的 item total 要求合法且等於主缺口數；缺欄位不補造，維持既有 fallback，矛盾時顯示「資料需確認」。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 renderer cache-buster 與測試契約，完整 history/report-quality/static/docs regression `326 passed`，Node syntax、line guard 與 `git diff --check` 通過；live historical `items_total=59`、`missing=59`、`items_returned=5`、`items.length=5`，renderer asset `200` 且與本地一致，health/ready `200/ready`、official launcher/worker/8080 與 doctor canonical paths 正常。本批不改 audit count、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3830 / enforce historical returned-item coverage

- `#拆解問題` / `#差距分析` / `#語意含義`：歷史 audit 的 `items_returned` 與實際 `items[]` 長度未互相核對；`returned=5` 但只返回 2 個 target 時，範圍文字仍會顯示 5。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以 `items_returned=5 / items.length=2` 取得 RED，明確存在的 returned count 要求合法非負整數且等於實際陣列長度；缺欄位才使用既有陣列長度 fallback，不推算缺少的 targets。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 renderer cache-buster 與測試契約，完整 history/report-quality/static/docs regression `325 passed`，Node syntax、line guard 與 `git diff --check` 通過；live historical `items_returned=5`、`items.length=5`、`items_total=59`，renderer asset `200` 且與本地一致，health/ready `200/ready`、official launcher/worker/8080 與 doctor canonical paths 正常。本批不改 audit count、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3829 / enforce historical snapshot scope decomposition

- `#拆解問題` / `#差距分析` / `#語意含義`：歷史 renderer 只驗證 gap、verified、audited 與 complete 關係，`verified=10、invalid=1、unverified=0、audited=10` 仍會同時顯示完整度與 snapshot 異常。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以 snapshot decomposition contradiction 取得 RED；只有三個 snapshot scope 欄位都明確提供時要求 `verified + invalid + unverified = audited`，不對 legacy 缺欄位補算 0，矛盾時顯示「資料需確認」。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 renderer cache-buster 與測試契約，live daily `165/165/0/0`、historical `1175/1175/0/0` 均符合分解；focused `3 passed`、完整 history/report-quality/static/docs regression `324 passed`，Node syntax、line guard 與 `git diff --check` 通過；renderer asset `200` 且與本地一致，health/ready `200/ready`、official launcher/worker/8080 與 doctor canonical paths 正常。本批不改 audit count、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3828 / enforce historical complete scope bounds

- `#拆解問題` / `#差距分析` / `#語意含義`：歷史 renderer 已檢查 `missing <= verified <= audited`，但 `complete=9、missing=0、verified=10` 仍會被顯示為 9 份完整，沒有反映 verified scope 的分解矛盾。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以 `complete=9 / missing=0 / verified=10 / audited=10` 取得 RED；明確存在的 complete count 要求合法且 `complete + missing = verified`，verified 缺失時只要求不超過 audited，不自行補造分母。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 renderer cache-buster 與測試契約，live daily `165/165/163/2`、historical `1175/1175/1116/59` 均符合新不變量；focused `3 passed`、完整 history/report-quality/static/docs regression `323 passed`，Node syntax、line guard 與 `git diff --check` 通過；renderer asset `200` 且與本地一致，health/ready `200/ready`、official launcher/worker/8080 與 doctor canonical paths 正常。本批不改 audit count、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3827 / enforce historical verified scope bounds

- `#拆解問題` / `#差距分析` / `#語意含義`：D3826 收緊 `missing <= audited` 後，歷史 renderer 仍未檢查 optional `verified_snapshot_reports`；`audited=10、verified=1、missing=2` 會顯示超過已驗證快照分母的缺口。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以 `missing=2 / verified=1 / audited=10` 取得 RED，明確存在的 verified count 要求 `missing <= verified <= audited`；欄位缺失不自行補算，維持既有 legacy fallback。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 renderer cache-buster 與測試契約，live daily `165/165/2`、historical `1175/1175/59` 均符合新不變量；focused `3 passed`、完整 history/report-quality/static/docs regression `322 passed`，Node syntax、line guard 與 `git diff --check` 通過；post-push renderer asset `200` 且與本地一致，health/ready `200/ready`、official launcher/worker/8080 與 doctor canonical paths 正常。本批不改 audit count、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3826 / enforce historical audit core scope bounds

- `#拆解問題` / `#差距分析` / `#語意含義`：歷史品質稽核 renderer 只檢查 `missing` 與 `audited` 的型別，沒有檢查 `quality_metadata_missing_reports <= audited_reports`；矛盾 payload 會顯示超出稽核範圍的缺口數。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先以 `audited=2 / missing=3` 取得 RED，再加入核心範圍不變量；不借用其他欄位修正數字，矛盾時 fail closed 顯示「品質 metadata 範圍資料需確認」，正常 legacy fallback 與 pagination 不變。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 renderer cache-buster、API/operator/architecture 說明與 regression；focused `3 passed`、完整 history/report-quality/static/docs regression `321 passed`，Node syntax 與 `git diff --check` 通過；official renderer asset `200` 且與本地一致，live daily `165/2/2`、current-quality `165/85/5/85`、historical `1175/59/5/59/truncated=true`，兩個 live core scope 均通過 `missing <= audited`，health/ready `200/ready`、official launcher 與 doctor canonical paths 正常。本批不改 audit count、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3825 / validate watchlist quality detail scope

- `#拆解問題` / `#差距分析` / `#語意含義`：watchlist board 重複渲染的品質 detail 分布與 bounded scope 沒沿用 strict count contract；fractional values 會被 floor，review 進度還可能用部分有效欄位形成錯誤分母。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以 `7fb43251` baseline replay 重現 field/review/pipeline/scope 四個錯誤，改用 local summary count boundary；分布逐欄忽略 invalid，review 四欄全體有效才顯示，malformed bounded metadata 顯示範圍需確認，不推算未展開數量。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 watchlist asset cache-buster、operator/architecture 說明與 regression；focused `1 passed`、完整 history/report-quality/static/docs regression `319 passed`，Node syntax 與 `git diff --check` 通過；live daily/current-quality 合併 shape 的 renderer smoke、7 個 asset `200`、health/ready `200/ready`、official launcher 與 doctor canonical paths 正常。本批不改 evidence gate、audit、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3824 / reject fractional watchlist evidence failures

- `#拆解問題` / `#差距分析` / `#語意含義`：watchlist current-quality summary 與 bounded target 的 `evidence_failed_count` 仍直接 floor，會讓 valid payload 的 `1.5` 變成看似精確的 mismatch `1`。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：用上一個 commit `ed0cd159` 的 baseline replay 重現錯誤，再以有限正整數 validator 收斂 summary/target 兩個直接顯示點；無效欄位逐項省略，不影響同一 payload 的其他合法 projection。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 watchlist helper cache-buster、operator/architecture 說明並沿用既有 API contract；focused/cache-buster tests `4 passed`，完整 history/report-quality/static/docs regression `318 passed`，Node syntax 與 `git diff --check` 通過；official live asset `200` 且與本地一致，current-quality `165`、target `5/85`、第一筆 count `0`，health/ready `200/ready`、official launcher 與 doctor canonical paths 正常。本批不改 evidence gate、audit、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3823 / reject fractional shared summary counts

- `#拆解問題` / `#差距分析` / `#語意含義`：共用 evidence、freshness、blocker、action 與 history current-quality 摘要仍會把 fractional/malformed counts floor 成原因、mismatch、處理建議或 evidence failure 數，讓 read-only diagnostics 看起來像合法整數。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以 `1.5`、`3.5`、`Infinity` 的跨入口 RED fixture 鎖定問題，所有 positive-entry 改用有限大於零整數，freshness 報告數另接受有限非負整數並保留合法 `0`；無效欄位逐項省略，不補算其他分母。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新四個 summary asset cache-buster、API/operator/architecture 說明與 regression；focused/full regression `317 passed`，Node syntax 與 `git diff --check` 通過，live daily current-quality `165`、historical `1175/59/5/59` 與 current projection `165` 正常，synthetic fractional/malformed counts 被抑制、合法 `0` report count 保留，health/ready `200/200`、doctor canonical paths 正常。本批不改 evidence gate、audit、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3822 / reject fractional review counters

- `#拆解問題` / `#差距分析` / `#語意含義`：review summary、審核歷史與三類 filter 仍把 fractional/malformed count floor 成合法 ordinal 或分母，會誤導人工核對範圍。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以 `event_count=2.5`、`event_id=3.5`、filter `Infinity` 的 RED fixture 鎖定問題，套用有限非負整數 validator；無效當前篩選保留入口並明示資料需確認。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 helper cache-buster、API/operator/architecture 說明與 regression；focused/full regression `315 passed`，helper/renderer 新 asset `200`，live historical audit `1175/59/5/59/truncated=true` 保留，synthetic fractional review/filter counts 被抑制，health/ready `200/200`、doctor canonical paths 正常。本批不改 review ledger、audit、quality gate、queue、snapshot、artifact、index 或 rerun state。

## D3821 / reject fractional historical audit counts

- `#拆解問題` / `#差距分析` / `#語意含義`：歷史稽核仍把 fractional/malformed count floor 成整數，會把 `2.5` 缺口與 `1.5` snapshot/error count 變成可採信的報告數。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先以完整 fractional/malformed RED 鎖定所有摘要類別，再加入有限非負整數 validator；不借用其他欄位補造 invalid 核心範圍，legacy 缺欄位才沿用既有 fallback。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 history renderer cache-buster、API/operator/architecture 說明與 regression；focused/full regression `314 passed`，新 asset `200`，live historical audit `1175/59/5/59/truncated=true` 正常保留，synthetic fractional/malformed counts 被抑制，health/ready `200/200`、doctor canonical paths 正常。本批不改 audit、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3820 / require complete overlap item coverage

- `#拆解問題` / `#差距分析` / `#語意含義`：`status=complete` 只看 split counts 仍不夠；`gap=2`、`returned=1` 會把部分 item comparison 當成 exact split。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以 complete-but-missing-items RED 鎖定問題，要求 `returned == gap` 且 in/out 加總等於 gap；不推算 partial scope。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 watchlist cache-buster、API/operator/architecture 說明與 regression；focused/full regression `313 passed`，新 asset `200`，live normal split `complete / 0/2 sample 內 / 2 sample 外 / returned 2` 保留，synthetic missing-items `0/2` 被抑制，health/ready `200/200`、doctor canonical paths 正常。本批不改 audit、repair sample、queue、snapshot、artifact、index、review 或 rerun state。

## D3819 / enforce repair overlap split invariant

- `#拆解問題` / `#差距分析` / `#語意含義`：整數 count 不代表 exact split 合法；`in_sample=3`、`gap=2`、`outside=0` 仍可被渲染成 `3/2`。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先取得 arithmetic contradiction RED，再要求 complete overlap 的 in/out 加總等於 gap；不延伸到 partial 未展開資料、不推算缺少欄位。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 watchlist cache-buster、API/operator/architecture 說明與 regression；focused/full regression `312 passed`，新 asset `200`，live overlap `complete / 0/2 sample內 / 2 sample外 / returned 2` 正常保留，synthetic `3/2` 被抑制，health/ready `200/200`、doctor canonical paths 正常。本批不改 audit、repair sample、queue、snapshot、artifact、index、review 或 rerun state。

## D3818 / reject fractional repair overlap counts

- `#拆解問題` / `#差距分析` / `#語意含義`：repair sample overlap 只檢查 finite，會把 fractional gap/in/out 數字 `floor` 成看似精確的 sample 統計。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以 `2.5`、`1.5` overlap fixture 取得 RED，讓既有 formatter 對 malformed/fractional 回傳 `null`，四個 overlap count 任一無效即 fail closed，不借用或推算其他欄位。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 watchlist cache-buster、API/operator/architecture 說明與 regression；focused/full regression `311 passed`，新 asset `200`，live overlap 為 `complete / gap 2 / sample內 0 / sample外 2 / returned 2`，正常摘要保留、synthetic fractional overlap 被抑制，health/ready `200/200`、doctor canonical paths 正常。本批不改 audit、repair sample、queue、snapshot、artifact、index、review 或 rerun state。

## D3817 / bound repair sample size labels

- `#拆解問題` / `#差距分析` / `#語意含義`：品質 count 已拒絕 fractional audit totals，但 repair sample label 仍將 `20.5` floor 成 `20`，操作員會收到看似精確的取樣範圍。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先取得 `sampled_reports=20.5` RED，再重用既有 `nonNegativeInteger()`；正常整數保留，fractional/malformed value 省略，不改 queue aggregate 或 item scope。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 watchlist cache-buster、API/operator/architecture 說明與 regression；focused/full regression `310 passed`，新 asset `200`，live `sampled_reports=20` 正常、synthetic `20.5` 被抑制，health/ready `200/200`、doctor canonical paths 正常。本批不改 repair queue、snapshot、artifact、index、review 或 rerun state。

## D3816 / reject fractional quality projections

- `#拆解問題` / `#差距分析` / `#語意含義`：watchlist freshness/current-quality 與 history current-quality 只檢查 finite/non-negative，`1.5` 分布可通過 validator，部分文案再 `floor` 成看似正常的整數。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以三個入口的 fractional RED fixture 鎖定問題，將 aggregate、status distribution、bounded totals 改為 finite non-negative integer；不使用 floor 修補，不借用其他欄位。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新三個 asset cache-buster、API/operator/architecture 說明與 regression；focused regression `309 passed`，三個新 asset `200`，live freshness 為 `一致 137 / 需完整重跑 28`、current-quality 為 `165/85` 且回傳 `5` 筆，三個 synthetic fractional scope 全部 suppressed，health/ready `200/200`、doctor canonical paths 正常。本批不改 quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3815 / bound watchlist quality counts

- `#拆解問題` / `#差距分析` / `#語意含義`：history renderer 已有有限非負整數 normalization，但 watchlist 主品質摘要仍把 `2.5`、`1.5` 或 `Infinity` 當成報告／snapshot 數量直接顯示。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先用 fractional/infinite count 取得 RED，再新增 local `nonNegativeInteger()`；正常整數保留，malformed 或 fractional value 省略，不借用其他欄位、不改 API 分母。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 cache-buster、API/operator/architecture 說明與 regression；需完成 focused regression、Node syntax、live normal-count 與 synthetic suppression 驗證。本批不改 quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3814 / bound watchlist quality coverage percentages

- `#拆解問題` / `#差距分析` / `#語意含義`：history renderer 已拒絕超過 100 的 coverage，但 watchlist 主品質摘要直接拼接 `quality_metadata_coverage_pct`；`120` 會被當成已驗證覆蓋率顯示。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先以 `coverage_pct=120` 取得 RED，再沿用 history 的 finite 0-100 normalization；正常 coverage 保留原數字，越界值省略，不借用其他欄位。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 watchlist cache-buster、API/operator/architecture 說明與 regression；focused regression `305 passed`，official live `98.79%` 正常、synthetic `120%` 被抑制，static assets `200`、health/ready `200/200`、doctor canonical paths 正常。本批不改 API count、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3813 / reject invalid historical current-quality item counts

- `#拆解問題` / `#差距分析` / `#語意含義`：watchlist validator 已拒絕 `returned > total`，但 history current-quality validator 沒有；矛盾 target list 可能通過摘要 projection。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：以 `total=0 / returned=1 / items.length=1` 取得 RED，補上 `returned <= total`；保留既有 watchlist regression，避免兩個 current-quality 入口再次分叉。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 history helper cache-buster 與 API/operator/architecture 說明；focused regression `304 passed`，official live historical `current_quality_summary` 為 `0/85` 且 `items.length=0`、validator 正常，static assets `200`、health/ready `200/200`、doctor canonical paths 正常。本批不改 API count、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3812 / prioritize history scope warnings over page ranges

- `#拆解問題` / `#差距分析` / `#語意含義`：歷史稽核 renderer 在有 `items_offset` 時優先輸出頁碼範圍，若同頁 `items_returned > items_limit`，操作員看不到 bounded scope contradiction。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先用 `offset=2 / returned=2 / total=4 / limit=1 / truncated=true` 取得 RED，再將既有 shared consistency warning 放到 page-range 分支前；正常 pagination 仍維持原文案。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：更新 history renderer cache-buster、前端契約與 API/operator/architecture 說明；focused regression `302 passed`，official live historical page 1/2 為 `5/59`、`limit=5`、`truncated=true`，page 2 正常顯示第 6-10 份且 warning count `0`，static assets `200`、health/ready `200/200`、doctor canonical paths 正常。本批不改 API count、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3811 / align watchlist quality gap scope labels

- `#拆解問題` / `#差距分析` / `#語意含義`：watchlist 主品質摘要的未展開文案只看 `items_truncated` 與缺口總數，沒有驗證 `items_returned <= items_limit`，與歷史稽核及 target label 的 bounded contract 不一致。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先以 `items_limit=1 / items_returned=2 / items_total=2 / items_truncated=false` 取得 RED，再消費 shared `boundedItemsConsistent`；只在可比較的 bounded metadata 矛盾時顯示「範圍資料需確認」，保留 target 導覽與 legacy fallback。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：同步更新 watchlist helper cache-buster、API/operator/architecture 說明與前端契約測試；focused regression `301 passed`，official live daily `missing=2`、`returned=2/total=2`、`limit=5`、`truncated=false` 且 shared consistency `true`，static assets `200`、health/ready `200/200`、doctor canonical paths 正常。本批不改 API count、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3810 / enforce bounded history audit scope labels

- `#拆解問題` / `#差距分析` / `#語意含義`：歷史品質稽核 renderer 的未展開文案只看 `items_truncated` 與 `quality_metadata_missing_reports`，沒有檢查 `items_returned <= items_limit`；矛盾 payload 會被誤當成完整明細。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先用 `items_limit=1 / items_returned=2 / items_total=2 / items_truncated=false` 取得 RED，再共用 bounded consistency contract；只在 bounded 欄位可比對且矛盾時顯示「範圍資料需確認」，保留 target 導覽與 legacy fallback。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：同步更新 history renderer cache-buster、API/operator/architecture 說明與前端契約測試；focused history/report-quality/static/docs regression `300 passed`，official live historical `5/59` 且 `limit=5/truncated=true/hasNext=true`，static assets `200`、health/ready `200/200`、doctor canonical paths 正常。本批不改 API count、quality gate、queue、snapshot、artifact、index、review 或 rerun state。

## D3809 / enforce bounded item limits in quality target labels

- `#拆解問題` / `#差距分析` / `#語意含義`：current-quality 與 freshness 的 label 沒有檢查 `items_returned <= items_limit`；即使 returned 等於 total，只要超過 limit 仍可能被寫成完整清單。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先以 `limit=1 / returned=2 / total=2` 兩個反例取得 RED，再將 limit 納入 shared consistency；正常 payload 維持既有 label，矛盾資料改顯示「範圍資料需確認」並保留 target 導覽。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：API、operator guide、architecture map 同步說明 limit 邊界；audit frontend `27 passed`、focused `279 passed`，live freshness `5/28`、current-quality `5/85`，static assets `200`、health/ready `200/200`、doctor canonical paths 正常。

## D3808 / guard current-quality and freshness bounded labels

- `#拆解問題` / `#差距分析` / `#語意含義`：`current-quality` 與 freshness 的 target list 在 `returned < total` 且 `items_truncated=false` 時仍顯示完整 total，會把部分 navigation sample 誤報成全量。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先以 `1/22` 與 `1/2` 反例取得 2 個 RED，再由 shared bounded label 驗證 `items_truncated`；正常截斷維持既有 `顯示 returned/total`，矛盾或缺失旗標改顯示「範圍資料需確認」並保留 target 導覽。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：API、operator guide、architecture map 同步說明不把 total 冒充完整清單；audit frontend `25 passed`、focused `277 passed`，live freshness `5/28`、current-quality `5/85`，static assets `200`、health/ready `200/200`、doctor canonical paths 正常。

## D3807 / share bounded repair queue scope across operator entries

- `#拆解問題` / `#差距分析` / `#語意含義`：同一份 live daily payload 在 operator dashboard 已顯示 repair target `5 / 9`，watchlist「今日工作台」卻只顯示取樣 `20` 份；兩個操作入口對可見範圍的語意不一致。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先用真實形狀 fixture 取得 watchlist RED，再新增 `report_quality_queue_scope_helpers.js`，以同一個 fail-closed formatter 驗證非負整數、`returned <= required/limit` 與截斷旗標；更新 index load order/cache-buster，保留 legacy/矛盾資料的舊文案與既有 queue/mutation。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：API、operator guide、architecture map 明示 dashboard 與 watchlist 共用範圍規則；focused frontend/static/docs `275 passed`，official live formatter 兩入口均為 `5 / 9`，三個 static asset `200`，health/ready `200/200`、doctor canonical paths 正常。

## D3806 / surface bounded repair queue scope in operator dashboard

- `#拆解問題` / `#差距分析` / `#語意含義`：API 已有 repair queue 的 bounded metadata，但 operator dashboard 只讀總數與 action 分布；操作員看得到 5 筆 target，卻無法知道 sample 內完整 actionable count 是 9。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先新增有效截斷與矛盾 metadata 的 frontend RED tests，再以 fail-closed formatter 驗證非負整數、limit/required 邊界與 `items_truncated` 一致性；完整 fit、legacy 或矛盾資料不猜算，並保留既有 dashboard 文案與所有 queue/mutation 行為。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：API、operator guide、architecture map 明示只有一致的四欄 metadata 才顯示「修復 queue：顯示 N / 共 M」；frontend `23 passed`、跨層 `387 passed`、static history/filter `139 passed`，official live formatter 實測 `5 / 9`，health/ready `200/200`、doctor canonical paths 正常。

## D3805 / expose bounded report repair queue scope

- `#拆解問題` / `#差距分析` / `#語意含義`：live daily dashboard 的 repair sample 有 `action_required=9`，但 `items[]` 只回傳上限 5 筆；原 payload 沒有明示這是截斷結果，操作員可能把可見卡片數誤讀成完整修復數。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先新增 limit=1 與完整 fit 兩個 RED 測試，再讓同一 normalized limit 同時驅動 slicing 與 `items_limit/items_returned/items_truncated`；不改 action priority、report quality gate、daily queue 或 mutation。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：API、operator guide、architecture map 明示 `action_required` 是 sample 全量、`items[]` 是 bounded target list；repair queue + daily dashboard `98 passed`，official reload/live audit 確認 `9/5/truncated=true`，daily queue `23/5/18`、notification `5/5`、current-quality `165/85` 維持不變。

## D3804 / stabilize queue identity and notification artifact aliases

- `#拆解問題` / `#差距分析` / `#語意含義`：反例將 queue rank 拆成 priority/source 主排序、同分 identity tie-breaker 與 notification artifact identity 三層；確認同分 item 會受 iterator 順序影響，且 filename aliases 可能讓同一通知指向兩個檔案。
- `#證據基礎` / `#偏誤降低` / `#可驗證性`：先加入 route warning、same-report pipeline 與 conflicting filename tests 取得 RED，再只改 queue summary sort key 與 notification context normalization；queue/identity/notification/HCS scoped `266 passed`、完整套件 `8444 passed, 6 skipped, 75 subtests passed`，official reload 與 live audit 均 GREEN。
- `#受眾` / `#溝通設計` / `#責任`：API、operator guide、architecture map 明示 stable rank 與 single artifact identity，避免操作人員因上游順序或 alias 漂移看到不同待辦/報告；live 首屏 5 筆與 notification 對齊，非首屏仍由全量 `secondary_count=18` 邊界與 deterministic sort contract 覆蓋，並保留 suppression 與既有 priority policy。

## D3803 / make notification-repair queue targets explicit

- `#拆解問題` / `#差距分析` / `#語意含義`：全 action type contract table 對照 backend、notification/outbox 與 operator UI 後，發現 `fix_notification_delivery` 的 queue item 沒有 `target_panel`，但 frontend 會依 type 推導 `maintenance-panel`；這是 API/UI target drift，不是 notification 發送問題。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先在既有 notification-delivery health fixture 加入 `maintenance-panel / ops` assertion 取得 RED，再只在 queue item producer 補明確 target；保留 `suppress_notification=true`，避免故障通道自我通知。
- `#受眾` / `#溝通設計` / `#責任` / `#可驗證性`：API 與 operator UI 現在共享可讀的「查看通知通道」維護入口；focused test `1 passed`、scoped regression `1113 passed`、正式 reload 後 module/live smoke 與 health/ready/doctor 通過，文件檢查與 push 完成後收斂本批。

## D3802 / align candidate notification CTA with the operator workbench

- `#拆解問題` / `#語意含義` / `#差距分析`：live queue/notification 交叉表的首屏五筆一致，但 `review_candidate` 的 backend shared table 仍輸出 `open-ops / 查看候選`，frontend candidate mapping 與既有設計契約已輸出 `candidate-snapshot / 查看股票快照`；target `market-screener-panel / screener` 本身沒有漂移。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：先用候選 notification 反例取得 RED，再只改 `OPERATOR_ACTION_BY_TYPE`，不改候選排序、候選 callback 或 target fallback；message 與 `delivery_outbox` 共用同一組 CTA/target assertion。
- `#受眾` / `#溝通設計` / `#可驗證性` / `#責任`：文件明示外部通知使用與工作台相同的候選主 CTA，保留 UI 的三個候選操作；focused candidate `4 passed`、跨層 regression `1113 passed`、全套 `8441 passed, 6 skipped, 75 subtests passed`，official reload 後 live module smoke、queue cross-check、health/ready 與 doctor 均通過。

## D3801 / make queue secondary count canonical across consumers

- `#拆解問題` / `#責任` / `#語意含義`：live queue 將 `secondary_count` 放在 response 頂層，但 API/架構/操作指南以 `decision_queue.summary` 描述三個 queue count；notification plan 讀頂層，造成同一 queue 契約跨層級分裂。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：`queue_response()` 以同一 actionable/rendered slice 新增 `summary.secondary_count`，保留頂層 alias；notification、operator summary、watchlist 優先讀 summary，legacy payload 才 fallback，monitor placeholder 仍不計入。
- `#受眾` / `#可驗證性` / `#可逆性`：先以 queue、notification、operator summary、watchlist fixtures 取得 RED，再 GREEN；live `23` 件 queue、首屏 `5` 件、次要 `18` 件與 notification context 一致，未改排序、action 或任何 mutation state。

## D3800 / partition quality actions by conclusion freshness

- `#拆解問題` / `#證據基礎` / `#差距分析`：live latest scope 的 `quality_gate_action_counts` 只有 `manual_review=81`、`rerun_analysis=4`，但同一批報告已有 `current=137`、`needs_rerun=28`；canonical row 交叉表確認 action 應可分成 manual review `55/26` 與 rerun `3/1`，缺口在分母可讀性，不在 action predicate。
- `#偏誤降低` / `#最小變更` / `#責任`：新增 `quality_gate_action_counts_by_freshness`，沿用同一份 `report_freshness_bucket()` 與 `quality_gate_repair_item()`，前端只在收到 optional map 時追加「按資料新鮮度」；不把全量品質投影誤當 daily queue，也不改 picker、review、rerun 或 repair state。
- `#受眾` / `#溝通設計` / `#可驗證性` / `#可逆性`：後端契約、watchlist/history 顯示與 legacy fallback 均有測試；`788 passed`，live API 確認 nested action 加總等於全量 `81/4`，freshness `137/28/0`，UI formatter 顯示 current `55/3` 與 needs-rerun `26/1`；health/ready、static cache-buster、doctor canonical paths 均通過。

## D3799 / isolate evidence claim semantics from the gate

- `#拆解問題` / `#證據基礎` / `#責任`：import-boundary RED 明確指出 `evidence_exit_gate.py` 同時承擔 claim extraction、非 claim 過濾、semantic path mapping 與 numeric matching；這些都是純邏輯，與 sampling/verdict orchestration 不同責任。
- `#偏誤降低` / `#最小變更` / `#語意含義`：將 claim parser、path hint、best-match 與 numeric normalization 收斂到 `evidence_exit_gate_claims.py`，主 gate 只保留 sampling、snapshot flatten、candidate check 與 verdict；public import 與 canonical evidence 邊界不變。
- `#可驗證性` / `#可逆性` / `#受眾`：主模組 `426→202` 行、helper `346` 行；evidence gate `215 passed`、evidence + import-boundary `719 passed`，`py_compile`、`git diff --check` 通過。本批只改模組責任邊界，不改 verdict、tolerance、snapshot、artifact、index、review、rerun、repair 或 queue。

## D3798 / isolate current-quality item projections

- `#拆解問題` / `#證據基礎` / `#責任`：import-boundary RED 指出 `report_current_quality_summary.py` 把 status normalization、evidence residual accounting、blocker projection 與 item shaping 堆在 index/cache orchestration 旁，增加跨層修改風險。
- `#偏誤降低` / `#最小變更` / `#語意含義`：新增 `report_current_quality_item_helpers.py` 承接純 projection helper，主模組保留 report page collection、cache、aggregate 與既有 public builder；透過原有品質與 audit 測試守住 payload contract。
- `#可驗證性` / `#可逆性` / `#受眾`：主模組 `442→289` 行、helper `174` 行；quality summary/audit/dashboard/frontend targeted regression `107 passed`，後續 import-boundary 全套為 `719 passed`，不改 current scope、quality predicate、freshness、queue 或 mutation。

## D3797 / keep monitor fallback outside displayed work counts

- `#拆解問題` / `#語意含義` / `#證據基礎`：live queue 與既有 empty-state 測試交叉核對後，確認 `items` 的 UI 佔位與 `summary.displayed_count` 的工作分母不一致；空 queue 目前是 `monitor` 一項但 actionable 為零。
- `#偏誤降低` / `#責任` / `#最小變更`：只將空 queue 的 displayed denominator 歸零，保留 monitor compatibility，不把 queue source、排序或通知規則混入修正；先改測試取得 RED，再修 `backend/daily_decision_queue_summary.py` 取得 GREEN。
- `#受眾` / `#溝通設計` / `#可驗證性` / `#可逆性`：同步 API、operator guide、architecture contract；queue/dashboard/notification/docs/HCS scoped regression `369 passed`，正式 reload 後 live queue 與 notification context 均為 `23/5/18`，healthz/readyz、daily API、static asset `200`，doctor canonical paths 通過。

## D3796 / use canonical unverifiable claim counts with explicit missing reasons

- `#拆解問題` / `#證據基礎` / `#責任`：資料契約稽核發現 legacy gate 可能有 `unverifiable_count` 卻沒有 `unverifiable_reason_counts`；只聚合 reason map 會漏掉真實 residual。
- `#偏誤降低` / `#最小變更` / `#語意含義`：current-quality 以 gate 的 `unverifiable_count` 與可用 reason count 較大值作 `evidence_unverifiable_claims_by_freshness`，同一報告的 `evidence_unverifiable_reports_by_freshness` 只加一次；原因 map 為空時顯示「原因未記錄」，不製造 reason code，也不改 verdict。
- `#受眾` / `#溝通設計` / `#可驗證性` / `#可逆性`：先用 reasonless fixture 取得 RED，再 GREEN；正式驗證需包含 current-quality、watchlist/history、跨層品質、Node syntax、`py_compile`、`git diff --check`、live API/DOM、health/ready 與 asset。本批只改 read-only residual accounting。

## D3795 / separate unverifiable evidence claims from affected reports

- `#拆解問題` / `#證據基礎` / `#語意含義`：live current-quality 的不可驗證 residual 以 claim 原因數統計；needs-rerun `112` 是 claim 數，不代表 `112` 份報告，且同一報告可能有多個原因。
- `#偏誤降低` / `#責任` / `#最小變更`：新增 `evidence_unverifiable_reports_by_freshness`，每份含 residual 的報告在 `current`／`needs_rerun`／`unknown` 各計一次；shared helper 只有收到 optional report map 才附「涉及 N 份報告」，舊 payload 不猜報告數。
- `#受眾` / `#溝通設計` / `#可驗證性` / `#可逆性`：focused `346 passed`、evidence/content/quality cross-layer `513 passed`，Node syntax、`py_compile`、`git diff --check` 通過；正式 reload 後需核對 live claim/report 分母、health/ready、asset 與 doctor canonical paths。本批只改 read-only diagnostics，不改 evidence verdict、snapshot、artifact、review、rerun、repair 或 queue。

## D3794 / label quality action projection separately from daily queue

- `#拆解問題` / `#證據基礎` / `#語意含義`：live current-quality 的 `quality_gate_action_counts` 是全量最新報告的品質 gate 投影（`81` 筆人工審核、`4` 筆完整重跑），不是 daily decision queue；daily queue 目前是 `23` 件總待辦、首屏 `5` 件、次要 `18` 件，來源與分母不同。
- `#偏誤降低` / `#責任` / `#最小變更`：summary 新增 `quality_gate_action_scope`，明示 basis `quality_gate_repair_item_per_report` 與 `is_daily_queue=false`；新增 shared scope helper，只有明確收到這個 false flag 才顯示「唯讀品質投影，不等同今日待辦」，舊 payload fallback 原文，不改 queue、action picker 或任何 mutation。
- `#受眾` / `#溝通設計` / `#可驗證性` / `#可逆性`：先取得後端欄位與前端 scope formatter RED，再 GREEN；正式驗證需包含 current-quality、watchlist/history、dashboard/queue、Node syntax、`py_compile`、`git diff --check`、live API/DOM、health/ready、asset 與 doctor canonical paths。本批只改 read-only contract/UI，不把全量品質建議轉成今日待辦。

## D3793 / split unverifiable evidence reasons by conclusion freshness

- `#拆解問題` / `#證據基礎` / `#情境脈絡`：live current-quality 的全量 `evidence_unverifiable_reason_counts` 只有原因總數，無法回答 residual 是目前本文問題還是資料刷新後等待重跑；逐筆檢查定位到 `3324.TWO/v1`「潛在下行空間 -18.2%」，其本文是舊結論，刷新後 snapshot 沒有同語意 canonical 欄位。
- `#偏誤降低` / `#責任` / `#最小變更`：新增 `evidence_unverifiable_reason_counts_by_freshness` 與 item 的 `evidence_unverifiable_freshness_status`，watchlist/history 共用新 helper 顯示 freshness 與原因；不借用 `current_price`、情境目標、evidence gate artifact 或相同數值代算，該 residual 仍是 `unverifiable`，legacy payload 缺欄位維持相容。
- `#受眾` / `#溝通設計` / `#可驗證性` / `#可逆性`：先取得 nested summary RED，再 GREEN；focused `408 passed`、evidence/content/quality cross-layer `513 passed`，Node syntax、`py_compile`、`git diff --check` 通過。正式 reload 後 live `165` 份、`85` 份非通過、evidence `134/28/3`；不可驗證按 freshness 為 current `technical_level_not_canonical=1、analysis_metadata_not_evidence=5`、needs_rerun `112` 筆、unknown `0`，healthz/readyz `ok/ready`、新 helper `200`、doctor canonical paths 正確。本批只改 read-only projection/UI，不寫 snapshot、artifact、index、review、rerun、repair 或 queue state。

## D3792 / align data trust and daily report sample denominators

- `#拆解問題` / `#證據基礎` / `#語意含義`：D3791 live probe 顯示 data trust card 使用 8 份 `/api/reports` 樣本，但 daily dashboard 的 `report_scope.sampled_reports` 是 20；「資料新鮮 X / 抽樣 Y」與「近期報告取樣」不是同一個分母，容易造成品質信任誤讀。
- `#偏誤降低` / `#責任` / `#最小變更`：`operator_summary_panel.js` 將 report request limit 從 8 對齊為 20，沿用同一最新報告範圍與既有 `trustText` predicate；不把 dashboard summary 借作 data trust、不改資料信任規則或任何 mutation，cache-buster 更新為 `20260902-report-sample-scope`。
- `#可驗證性` / `#可逆性` / `#受眾`：先取得 request limit RED，再 GREEN；frontend/history/filter `294 passed`、dashboard/queue/repair/current-quality `230 passed`，Node syntax、`py_compile`、`git diff --check` 通過。正式 JS + live API/DOM 取得 data trust `資料新鮮 20 / 抽樣 20`、daily sample `20`、queue `23/5/18`、current quality `165/85`；本批只改 read-only sample scope，不寫 snapshot、artifact、index、review、rerun、repair 或 queue state。

## D3791 / expose total actionable queue count without inflating rendered items

- `#拆解問題` / `#受眾` / `#語意含義`：live `decision_queue.summary` 是 `total_actionable=23`、`displayed_count=5`、`secondary_count=18`，但 operator summary 標頭只顯示「5 件快速操作」；首屏 top-5 與總待辦的分母沒有在同一處說清楚。
- `#證據基礎` / `#偏誤降低` / `#最小變更`：`operator_summary_panel.js` 新增 queue count guard，只有 `total_actionable`、`displayed_count` 是整數，且 `displayed_count` 等於實際 rendered actionable count、`total_actionable` 大於顯示數時，才輸出「顯示 5 / 共 23 件快速操作」；缺 summary、legacy payload 或計數不一致時回到實際 rendered count，沒有自行猜測總量或改 queue payload。
- `#可驗證性` / `#可逆性` / `#責任`：先取得 header RED，再 GREEN；frontend/history/filter `158 passed`、dashboard/queue/repair/current-quality `230 passed`，Node syntax、`git diff --check` 通過。正式 JS + live API/DOM 取得 `header_matches_queue=true`、queue `23/5/18`、data trust card 未顯示 queue summary，current quality `165/85`；cache-buster 更新為 `20260902-queue-total-scope`。本批只改 read-only operator 呈現，不寫 snapshot、artifact、index、review、rerun、repair 或 queue state。

## D3790 / keep data trust card separate from daily queue summary

- `#拆解問題` / `#語意含義` / `#受眾`：operator summary 的元素標籤是「近期資料信任」，但 panel 原本以 daily queue summary 覆蓋它；live queue 的 `23 件待處理` 因而會被誤讀成資料信任狀態，混淆 queue、資料信任與報告品質的分母。
- `#責任` / `#最小變更` / `#溝通設計`：恢復 data trust card 只消費 `helpers.trustText(reportsValue)`，daily dashboard summary 保留給值班 warning 計數與 action list；新增 `20260902-data-trust-card-scope` cache-buster，避免瀏覽器使用舊 panel。只改 read-only UI routing，不改 API、品質 predicate 或任何 mutation。
- `#可驗證性` / `#可逆性` / `#證據基礎`：先以 DOM-shaped RED 重現 queue 覆蓋 data trust，再 GREEN；frontend/history/filter `157 passed`、dashboard/queue/repair/current-quality `230 passed`，Node syntax、`py_compile`、`git diff --check` 通過。官方 reload 後 live DOM 顯示 `近期資料正常 / 8 份近期報告`，action list 仍有「今日待處理」與 queue action，panel asset HTTP `200`，healthz/readyz `ok/ready`，doctor canonical paths 正確。

## D3789 / separate daily repair and freshness rerun scopes

- `#拆解問題` / `#差距分析` / `#語意含義`：live daily dashboard 的近期取樣 `20` 份顯示 `reports_needing_rerun=0`，但 repair queue 有 `2` 筆 `rerun_analysis`；前者是 freshness predicate，後者是 report repair predicate，原 operator text 會造成範圍誤讀。
- `#證據基礎` / `#責任` / `#最小變更`：summary 新增 `reports_needing_freshness_rerun`、`report_repair_action_counts` 與 `report_repair_rerun_required`；operator text 只在新欄位存在時顯示「報告修復：...；freshness需完整重跑...」，舊 payload 仍沿用原文。新增 cache-buster `20260902-report-repair-scope`；只做 read-only projection，不觸發 rerun、寫入 queue 或改變既有 freshness predicate。
- `#可驗證性` / `#可逆性` / `#受眾`：backend focused `106 passed`、frontend/history/filter `156 passed`，Node syntax、`py_compile`、`git diff --check` 與 static module guard `87 < 90` 通過。官方 reload 後 live summary 為 `report_repair_action_counts={manual_review:7, rerun_analysis:2}`、`report_repair_rerun_required=2`、`reports_needing_freshness_rerun=0`，全量分析新鮮度另為 `28 / 165`；dashboard text 已分開呈現，healthz/readyz `ok/ready`、asset HTTP `200`、doctor canonical paths 正確。

## D3788 / align current-quality item order with repair priority

- `#拆解問題` / `#差距分析` / `#效用`：全量 current-quality `85` 筆原本只依 gate 嚴重度與檔名排序；同為 blocked 時，priority `840` 的可重跑 Agent failure 可能排在 priority `1000` 的內容矛盾前，操作員首屏順序與既有 repair queue 不一致。
- `#決策樹` / `#責任` / `#可驗證性`：改用「品質嚴重度 →既有 quality action priority →檔名」的 deterministic key，新增 `items_sort_basis=quality_attention_then_action_priority_then_filename`；只改 read-only current projection 的排序，不改 gate status、action、截斷上限或任何 mutation，legacy frontend 仍可忽略新欄位。
- `#證據基礎` / `#表達` / `#可逆性`：新增排序比較組測試；current/repair/audit `100 passed`、完整品質跨層 `1412 passed in 222.04s`、frontend/history/filter/HCS `261 passed`，Node syntax、`py_compile`、`git diff --check` 通過。正式 reload 後 live `165` 份、`85` 筆品質項目、API `items_sort_basis` 正確且顯示 `5/85`；首屏先列低資料信心目標價與建議／報酬矛盾，healthz/readyz `ok/ready`、三個 action 資產 HTTP `200`，doctor canonical paths 正確。本批不寫 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3787 / surface canonical quality action reasons in operator UI

- `#受眾` / `#語意含義` / `#溝通設計`：live current-quality API 已有 `quality_action.title/detail`，但 watchlist 項目原本只顯示「建議處理：人工審核／完整重跑」，evidence rejected 或 conformance fallback 的操作員仍要進歷史查核才能知道原因。
- `#來源品質` / `#責任` / `#最小變更`：擴充既有 shared `formatQualityAction()`，有 title/detail 時附上「處理原因」與 canonical detail；沒有新欄位的 legacy payload 維持舊輸出，未改 action 判定、priority、blocks_auto_rerun 或任何 mutation。cache-buster 升為 `20260902-quality-action-detail`。
- `#可驗證性` / `#可逆性` / `#表達`：frontend/history/filter regression `194 passed in 9.13s`，Node syntax、44 行 helper guard、`git diff --check` 通過。官方 reload 後三個新資產 HTTP `200`，live board render `contains_detail=true` 且包含 Agent failure canonical detail；summary 維持 `165` 份、`85` 筆品質項目、`manual_review=81`、`rerun_analysis=4`，healthz/readyz `ok/ready`、doctor canonical paths 正確。本批只改善 read-only operator presentation。

## D3786 / reconcile retryable content blockers with freshness actions

- `#拆解問題` / `#差距分析` / `#證據基礎`：live current-quality 的 `0056.TW/v4`、`2367.TW/v2/v3` 顯示 `final_audit_critical` Agent 輸出失敗；原本 content gate 的 priority `1000` 會蓋過既有 conformance retry marker，讓完整重跑案例錯誤顯示人工審核。`1623.TW/v3` 同時有低資料信心目標價，不能沿用這個分流。
- `#偏誤降低` / `#責任` / `#最小變更`：新增 `report_quality_retry_actions.py` 共用辨識；只有 content blocking issues 全部是 `final_audit_critical` 且每個 canonical critical detail 都含既有 retry marker 時，才回傳 priority `840` 的 `rerun_analysis`、`完整重跑`、`blocks_auto_rerun=false`。混合 blocker、公司身分污染與其他非可重試內容風險仍維持 priority `1000` 人工審核；不改 status、verdict、snapshot、artifact、index 或自動觸發行為。
- `#可驗證性` / `#可逆性` / `#溝通設計`：新增純可重試、混合阻塞與純非可重試控制測試；focused repair/current `65 passed`、品質跨層 `1410 passed in 222.92s`、import boundary `503 passed` 並保留既有 `evidence_exit_gate.py` 426 行門檻失敗、Node syntax、`py_compile`、`git diff --check` 通過。官方 runtime reload 後 live `165` 份、`85` 筆品質項目為 `manual_review=81`、`rerun_analysis=4`；`0056.TW/v4` 與 `2367.TW/v3` 走完整重跑，`1623.TW/v3` 仍人工審核，healthz/readyz `ok/ready`、queue depth `0`、failed_recent `0`、三個 quality action 資產 HTTP `200`。本批只修正 read-only repair action projection。

## D3785 / expose the shared quality action and canonical action detail

- `#拆解問題` / `#差距分析` / `#受眾`：live current-quality 有 `165` 份報告、`85` 份非通過項目；原本 item 能顯示 blocker ID、原文與 freshness，卻沒有把既有 repair queue 的下一步動作帶到同一筆報告，操作員仍需跨頁判斷先人工核對或完整重跑。
- `#證據基礎` / `#偏誤降低` / `#責任`：新增唯讀 `quality_action` 與 aggregate `quality_gate_action_counts`，由共用 `quality_gate_repair_item()` 依既有三個品質 gate 優先級產生；`details.critical` 有 canonical 原文時，action detail 優先採用該原文，避免泛用 summary 蓋掉可核對證據。前端只顯示「建議處理」，`blocks_auto_rerun` 為真時明示「暫停自動重跑」，不自動觸發任何 action。
- `#可驗證性` / `#可逆性` / `#溝通設計`：先取得 action 與 canonical detail RED，再 GREEN；聚焦 repair/current/UI 回歸 `100 passed`，跨層品質回歸 `1406 passed in 223.07s`，Node syntax、`py_compile`、`git diff --check` 通過。正式 reload 後 live `quality_gate_action_counts=manual_review 85`，`0056.TW/v4` 與 `1623.TW/v3` action detail 均等於 canonical blocker 原文，healthz/readyz `ok/ready`、queue depth `0`、failed_recent `0`，三個 `20260902-quality-action` 資產 HTTP `200`。本批只改 read-only summary/UI diagnostics 與共用規則，不寫 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3784 / include every quality attention signal in item selection

- `#拆解問題` / `#差距分析` / `#責任`：current-quality aggregate 同時提供 conformance、content credibility 與 evidence 分布，但原本 `items` 只在 conformance 非 `passed` 時建立；若 current projection 只有 content blocker，aggregate 與「待查看」清單會不一致。
- `#偏誤降低` / `#最小變更` / `#溝通設計`：item selection 改為 conformance、content 或 evidence 任一未達正常狀態即列入，並以三者最嚴重等級排序；不改三個 status/verdict 值，也不擴張資料寫入或 action queue。現有 `non_passed_reports` envelope 沿用，前端仍可處理舊 payload。
- `#可驗證性` / `#可逆性`：先取得 content-only RED，再 GREEN；聚焦回歸 `199 passed`、跨層品質回歸 `1403 passed`，Node syntax、`py_compile`、`git diff --check` 通過。正式 reload 後 live `165` 份仍為 `items_total=85`，因現有 content blocker 同時已被 conformance 捕捉；status counts 維持 conformance `80/71/14`、content `93/59/13`、evidence `134/28/3`，`healthz=ok`、`readyz=ready`、queue depth `0`、failed_recent `0`，三個 detail 資產 `200`。本批只修正 read-only item selection，不寫 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3783 / expose canonical content blocker details per report

- `#拆解問題` / `#差距分析` / `#溝通設計`：live `13` 份 content blocker 中有 `12` 份是 `final_audit_critical`；只顯示 blocker ID 仍無法回答是哪個 agent 失敗、哪個結論矛盾或哪個資料信心門檻被觸發，操作員難以在「先重跑」與「先人工確認」間分流。
- `#證據基礎` / `#責任` / `#最小變更`：current-quality item 新增 `content_credibility_blocker_messages`；若 blocking issue details 有 canonical `critical` 原文，優先取其去重結果，否則退回 issue message。shared helper 只做訊息去重與分隔，watchlist 顯示「內容阻斷原因」並沿用既有 escape；缺少新欄位的舊 payload 仍可渲染，不改 blocker、status、verdict、snapshot 或 rerun 行為。
- `#可驗證性` / `#可逆性`：先取得 backend/helper/watchlist RED，再 GREEN；聚焦回歸 `198 passed`、跨層品質回歸 `1402 passed`，Node syntax、`py_compile`、`git diff --check` 通過。正式 reload 後 live `0056.TW`、`1623.TW`、`2367.TW` item 已回傳 canonical 原因，無 blocker 的 `2308.TW` 保持空清單；`healthz=ok`、`readyz=ready`、queue depth `0`、failed_recent `0`，三個 detail 資產 `200`。本批只改 read-only summary/UI diagnostics，不寫 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3782 / carry content blocker context into each report item

- `#拆解問題` / `#差距分析` / `#溝通設計`：live current summary 的 aggregate 已能看出 content blocker `13` 份及 freshness `current=5`／`needs_rerun=8`，但 item 只顯示 conformance reason，操作員仍不能在待查看清單直接知道單份報告的 content blocker ID 與是否先重跑。
- `#責任` / `#偏誤降低` / `#最小變更`：current-quality item 新增去重後的 `content_credibility_blocker_ids`，並在存在 blocker 時附 `content_credibility_freshness_status`；shared helper 將 ID 轉成白話標籤，watchlist item 顯示「內容阻斷」與「內容阻斷版本」。缺少新欄位的舊 payload 仍可渲染，不改 status、verdict、snapshot 或 rerun 行為。
- `#可驗證性` / `#可逆性`：先取得 item/helper RED，再 GREEN；聚焦回歸 `196 passed`、跨層品質回歸 `1400 passed`，Node syntax、`py_compile`、`git diff --check` 通過。正式 reload 後 `healthz=ok`、`readyz=ready`、queue depth `0`、failed_recent `0`，三個 context 資產 `200`，live aggregate 與既有 status distribution 維持不變。本批只改 read-only summary/UI diagnostics，不寫 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3781 / separate content blockers by conclusion freshness

- `#拆解問題` / `#差距分析` / `#情境脈絡`：live `13` 份 content blocker 中，`5` 份屬目前版本、`8` 份屬資料刷新後尚未完整重跑；只顯示 `blocked=13` 會把本文當下矛盾與舊結論待重跑混為一談。
- `#偏誤降低` / `#最小變更` / `#溝通設計`：新增 read-only `content_credibility_blocker_reports_by_freshness`，以每份報告為單位依 `current`／`needs_rerun`／`unknown` 分組；shared formatter 在 watchlist/history 顯示「內容阻斷版本」，不調整 blocker、status、verdict 或把 stale 報告誤標成通過。
- `#可驗證性` / `#責任`：先取得 freshness fixture RED，再 GREEN；聚焦回歸 `195 passed`、跨層品質回歸 `1399 passed`，Node syntax、`py_compile`、`git diff --check` 通過。正式 reload 後 `healthz=ok`、`readyz=ready`、queue depth `0`、三個新版資產 `200`，live map 為 `current=5`、`needs_rerun=8`、`unknown=0`。本批仍只改 read-only summary/UI diagnostics，不寫 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3780 / expose quality blocker responsibility in aggregate

- `#拆解問題` / `#差距分析` / `#溝通設計`：live current quality 已有 `165` 份報告的 conformance/content/evidence 狀態，但摘要只給 blocked/warning 數量；`final_audit`、`content_credibility`、`evidence_exit_gate` 與低資料信心目標價等阻斷原因無法在 watchlist/history 一眼辨識，操作人員仍需逐份展開。
- `#偏誤降低` / `#最小變更` / `#責任`：新增 read-only `report_conformance_blocker_counts` 與 `content_credibility_blocker_counts`，每份報告對同一 blocker ID 去重；conformance 合併 blocked decision-tree step，content 有 blocking issue 時優先採 issue、沒有 issue 才 fallback 到 blocked check，避免把同一個 final audit 重複計算。watchlist/history 共用白話 formatter，不改 status、verdict 或 evidence 邊界。
- `#可驗證性` / `#可逆性`：RED→GREEN 後 current-summary/frontend 聚焦回歸 `194 passed`、跨層品質回歸 `1398 passed`，Node syntax、`py_compile`、`git diff --check` 通過。正式 reload 後 healthz/readyz 為 `ok/ready`、三個新版本資產均 `200`；live blocker map 為 conformance `content_credibility=13`、`evidence_exit_gate=3`、`final_audit=12`，content `explicit_target_price_low_data_confidence=1`、`final_audit_critical=12`、`long_target_not_above_current_price=1`。本批只改 read-only aggregate/UI diagnostics，不寫 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3779 / classify the remaining generic pressure residual

- `#拆解問題` / `#差距分析` / `#溝通設計`：yearless close mapping 後，live current summary 的唯一 `no_matching_snapshot_path` 是 `6226.TW/v4`「近期壓力 34.0 TWD（心理關卡與目前最高價）」；它沒有 52 週欄位或 technical-level scalar 的明示證據，卻和既有 generic support residual 屬於同一人工確認類型。
- `#偏誤辨識` / `#偏誤降低` / `#最小變更`：將 exact normalized label `近期壓力` 納入既有 `technical_level_not_canonical` reason；只改診斷分類，維持 `unverifiable`、空 matched path，不把同值 `week_52_high` 或 `current_price` 借來核驗。完整 claim audit 仍保留 confidence、情境、風控與 legacy conclusion 的非證據界線。
- `#可驗證性` / `#可逆性` / `#責任`：先以 generic pressure RED，再 GREEN；evidence/quality `218 passed`、跨層回歸 `1396 passed`、`py_compile` 與 `git diff --check` 通過。正式 reload 後 live `165` 份 evidence `134 approved / 28 caution / 3 rejected`，`12` 個 mismatch 全部 `needs_rerun`，`technical_level_not_canonical=1`、`no_matching_snapshot_path=0`。本輪仍只改 read-only diagnostics，不改 tolerance、verdict、snapshot、artifact、index、review、rerun、repair 或 queue。

## D3778 / recover yearless close support from an exact date

- `#拆解問題` / `#差距分析` / `#證據基礎`：D3777 後 current residual 只剩 `6226.TW/v4` 的一筆可疑近期支撐與一筆沒有明示來源的近期壓力；snapshot 明確有 `price_history[2026-08-31] = 31.6`，報告也明確寫成 `8/31 收盤價`。
- `#偏誤辨識` / `#偏誤降低` / `#最小變更`：只在 technical support/pressure、收盤語意、月份對應年份唯一、報告值位於日期前且非新聞來源時建立 exact `price_history` path；跨年份歧義與新聞來源維持 `unverifiable`，34.0「心理關卡與目前最高價」不借用 52 週高點。
- `#可驗證性` / `#可逆性` / `#責任`：先取得 yearless-date RED，再 GREEN；evidence/quality `217 passed`、跨層回歸 `1395 passed`、`py_compile` 與 `git diff --check` 通過。正式 reload 後 6226 的 31.6 對到 `data.price_history[2026-08-31].prices[10]`，live `165` 份 evidence 為 `134 approved / 28 caution / 3 rejected`，mismatch `12` 筆全部 `needs_rerun`，`technical_level_not_canonical` 由 1 降為 0，僅保留 `no_matching_snapshot_path=1`。本輪仍只改 read-only gate/parser，不寫入 quality verdict、snapshot、artifact、index、review、rerun、repair 或 queue。

## D3777 / close evidence parser and persisted-path residuals

- `#拆解問題` / `#差距分析` / `#證據基礎`：fresh residual audit 顯示剩餘可修正缺口集中在 evidence claim extraction/path mapping，而不是 tolerance 或 verdict；包含千分位後接括號的 `8,207` 被截斷、code-style `short_previous_balance`、無年份的 daily net buy、52 週高點 source forms、支撐區間底、recommendation horizon 與 `normalized_financials` 說明文字。
- `#偏誤辨識` / `#偏誤降低` / `#最小變更`：只補明示 persisted key、可由唯一 snapshot price-history 年份解析的日期、明示 `week_52_high_twd` source、雙日期 price-history range、推薦期間欄位與 data-limitation non-claim；`FOMO/過熱評分` 維持 `analysis_metadata_not_evidence`。沒有 canonical source 的 `6226.TW/v4`「心理關卡／目前最高價」與「8/31 收盤價」近期支撐仍保留 `unverifiable`，不借用同值的 52 週高點或日期推測。
- `#可驗證性` / `#可逆性` / `#責任`：RED→GREEN 後 evidence gate `214 passed`、內容可信度 `957 passed`、跨層品質回歸 `1392 passed`，`py_compile` 與 `git diff --check` 通過。正式 runtime `healthz=ok`、`readyz=ready`、doctor canonical paths 通過；live `165` 份為 evidence `134 approved / 28 caution / 3 rejected`，`12` 個 mismatch 全部是 `needs_rerun`，current residual reason 仍明確為 `technical_level_not_canonical=1`、`no_matching_snapshot_path=1`。本批只改 read-only evidence extraction/diagnostics，不調整 tolerance、verdict、snapshot、artifact、index、review、rerun、repair 或 queue。

## D3776 / attribute evidence mismatches to conclusion freshness

- `#拆解問題` / `#差距分析` / `#證據基礎`：live current scope 的 13 筆 sampled `mismatch` 中，12 筆來自 `needs_rerun`、1 筆來自 current report；只顯示總 mismatch 會掩蓋「快照已更新、本文尚未重跑」與「目前版本仍有數值矛盾」的不同責任路徑。
- `#偏誤降低` / `#語意含義` / `#最小變更`：抽出共用 `report_freshness_bucket()`，current-quality summary 只統計真正的 `failed_count`，新增 claim-level 與 report-level freshness 分布；target 只在有 mismatch 時附上 `evidence_mismatch_freshness_status`，不把 unverifiable 或 gate verdict 重新分類。
- `#可驗證性` / `#責任`：RED→GREEN 以 current/needs-rerun/unknown fixture、共用前端 formatter、cache-buster 與 target rendering regression 鎖定契約；backend current/freshness/audit `37 passed`、frontend/history/filter `189 passed`、跨層回歸 `2191 passed`、Node syntax、helper line guard `44`、diff check 通過。正式 reload 後 healthz/readyz、helper cache-buster 與 live aggregate assertions 通過，doctor 確認 canonical paths 未漂移；實作 commit `615ec597`、文件記錄 commit `57000719`，已 push 至 `origin/main`。本輪只改 read-only diagnostics，不寫 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3775 / label unavailable canonical snapshot fields

- `#拆解問題` / `#差距分析` / `#來源品質`：唯一 `snapshot_field_unavailable` 是 `6141.TW/v4` 的 `Short Balance: 0 (or null/not provided...)`；snapshot 的 `short_balance` 是 `None`，backend 已正確維持 `unverifiable`，不把來源缺值當零。
- `#偏誤辨識` / `#偏誤降低` / `#溝通設計`：只補 shared helper 的 operator label「快照欄位不可用」與 cache-buster，不改既有 reason、candidate、verdict 或任何資料來源邊界。
- `#可驗證性` / `#可逆性` / `#責任`：full artifact 與 backend gate 不變；frontend focused `12 passed`、live helper `200` 顯示「快照欄位不可用」、Node syntax、helper line guard `44`、diff guards、push `4fc3db55` 通過。本批只改 read-only presentation，不寫 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3774 / classify unbacked growth-scenario revenue projections

- `#拆解問題` / `#差距分析` / `#來源品質`：fresh residual audit 的最後 3 筆 `missing_semantic_path` 是 `3653.TW/v1` 的 `保守 NT$357 億`，以及 `2367.TW/v1` 的 `保守 NT$185 億`、`樂觀 NT$265 億`；它們位於 5 年後年營收情境表，不是現況 revenue 或 scenario target。
- `#偏誤辨識` / `#偏誤降低` / `#最小變更`：只在 table first-cell 為 `保守`／`悲觀`／`中性`／`基準`／`樂觀`，且 context 明示情境預測、年營收或 CAGR 時輸出既有 `analysis_metadata_not_evidence`；不借用現況營收、分析師目標價或另一個情境值，有 candidate 時仍走一般核驗。
- `#可驗證性` / `#可逆性` / `#責任`：先取得 3 筆 residual RED，再完成 reason boundary、shared helper 白話標籤、canonical control 與文件；backend focused `201 passed`、shared frontend `11 passed`、跨層回歸 `2189 passed`，full artifact `164/2509` 為 `1637 verified / 733 unverifiable / 139 mismatch`，`analysis_metadata_not_evidence=104`、`missing_semantic_path=0`、`scenario_target_not_canonical=100`；正式 runtime 的兩份目標 artifact HTML/Markdown/data、health/ready、helper 均 `200`，三筆 live claim 均為 `unverifiable`／`analysis_metadata_not_evidence`／空 matched path，doctor、py_compile、Node syntax、line guard `349`、helper `44`、diff guards 通過，commit/push 待完成。本批只改 read-only diagnostics，不寫 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3773 / classify unbacked scenario table targets

- `#拆解問題` / `#差距分析` / `#來源品質`：fresh residual audit 找到 `1623.TW/v2` 的熊市情境 table target；表格有 `熊市` context 與 NT$178，但沒有 canonical parsed/structured target path，原本落在唯一 `no_matching_snapshot_path`。
- `#偏誤辨識` / `#偏誤降低` / `#最小變更`：只對 table first-cell `熊市`／`基本`／`牛市` context 分流 `scenario_target_not_canonical`；不借用 DCF、current price、quality metadata 或其他 target path，並保留 canonical `rerun_context.parsed.price_targets.bear` control。
- `#可驗證性` / `#可逆性` / `#責任`：先取得 no-canonical table RED，再完成 context boundary、canonical control 與文件；focused evidence `200 passed`、跨層回歸 `2187 passed`、full artifact `164/2509` 為 `1637 verified / 733 unverifiable / 139 mismatch`，`scenario_target_not_canonical=100`、`missing_semantic_path=3`、`no_matching_snapshot_path=0`；正式 runtime 的 HTML/Markdown/data、health/ready、helper 均 `200`，live claim 為 `unverifiable`／`scenario_target_not_canonical`／空 matched path，doctor、py_compile、line guard `349`、diff check、commit/push `83160ba8` 通過。本批只改 read-only diagnostics，不寫 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3772 / refine generic support and explicit agent-score boundaries

- `#拆解問題` / `#差距分析` / `#來源品質`：fresh residual audit 找到兩筆一般 `近期支撐`、一筆 `支撐位` 與兩筆 `Agent 3 評分` 長敘述 claim；它們分別缺 canonical technical level，或是分析 metadata label 被敘述文字包住。
- `#偏誤辨識` / `#偏誤降低` / `#最小變更`：擴充 exact normalized technical-level set 至 `近期支撐`／`支撐位`，並只對 explicit `Agent 3 評分`／`Agent 3 score` context 使用既有 `analysis_metadata_not_evidence`；不改正常 `risk_price`、price-history 或 canonical analysis path。
- `#可驗證性` / `#可逆性` / `#責任`：先取得 generic-level／long-label RED，再完成 reason mapping、shared helper、canonical controls 與文件；backend focused `199 passed`、shared helper `10 passed`、跨層回歸 `2186 passed`，full artifact `164/2509` 維持 `1637 verified / 733 unverifiable / 139 mismatch`，`analysis_metadata_not_evidence=101`、`technical_level_not_canonical=6` 且 `no_matching_snapshot_path=1`。正式 reload 後 6282、2344、3653 目標 artifact 與 health/ready 均 `200`，3653 次要月末價仍 verified；helper、doctor、diff guards 與 push 通過。本批只改 read-only diagnostics，不寫 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3771 / classify narrative technical levels without canonical scalar

- `#拆解問題` / `#差距分析` / `#來源品質`：fresh residual audit 找到 `心理關卡`、`第二支撐`、`關鍵支撐區` 三筆敘事技術價位；它們有價格語意，但 snapshot 沒有可回溯的 canonical technical-level／`risk_price` scalar。
- `#偏誤辨識` / `#偏誤降低` / `#最小變更`：只對 exact normalized labels 輸出 `technical_level_not_canonical`；不借用 current price、target candidates 或附近 history，且保留 `data.risk_price` canonical control 的正常核驗。
- `#可驗證性` / `#可逆性` / `#責任`：先以三個 no-candidate fixture 取得 RED，再加入 reason mapping、shared helper/cache-buster、canonical control 與文件；backend focused `196 passed`、shared helper `10 passed`、跨層回歸 `2183 passed`，full artifact `164/2509` 維持 `1637 verified / 733 unverifiable / 139 mismatch`，新增 `technical_level_not_canonical=3` 且 `no_matching_snapshot_path=6`。正式 reload 後三個目標 artifact 的 HTML/Markdown/data 與 health/ready 均 `200`，helper、doctor、diff guards 與 push 通過。本批只改 read-only diagnostics，不寫 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3770 / classify intraday bulletin prices as news-source evidence

- `#拆解問題` / `#差距分析` / `#來源品質`：fresh residual audit 找到 `8039.TW/v4` 的盤中速報支撐價；snapshot 同時有 target candidates 與 `risk_price` 同值，但沒有盤中來源的 canonical path。
- `#偏誤辨識` / `#偏誤降低` / `#最小變更`：只把 `盤中速報` 納入既有 news-source boundary，輸出 `news_source_not_canonical`；不借用 target candidates、current price 或 risk price，也保留日期價格／52 週／River Chart 的既有專用 mapping。
- `#可驗證性` / `#可逆性` / `#責任`：先以同值 target/risk snapshot 取得 RED，再完成 reason mapping、反例 fixture 與文件；backend focused `194 passed`、跨層回歸 `2181 passed`，full artifact `164/2509` 維持 `1637 verified / 733 unverifiable / 139 mismatch`，`news_source_not_canonical=4` 且 `no_matching_snapshot_path=9`。正式 reload 後 8039 HTML/Markdown/data 與 health/ready 均 `200`，helper、doctor、diff guards 與 push 通過。本批只改 read-only diagnostics，不寫 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3769 / exclude provider error codes and duration tokens from evidence claims

- `#拆解問題` / `#差距分析` / `#來源品質`：fresh residual audit 找到 5 筆 fallback `429` 與 1 筆 `30-day` 被抽成 claim；前者是 provider error code，後者是期間文字，兩者都不應進入 numeric evidence。
- `#偏誤辨識` / `#偏誤降低` / `#最小變更`：在既有 `_is_non_claim_match()` 加入窄範圍 guard，只排除 fallback／error／不可用後的 4xx/5xx 與 duration suffix；`target price: 429 TWD` control 仍保留真正目標價，避免廣泛用數字值刪除規則。
- `#可驗證性` / `#可逆性` / `#責任`：先取得 parser RED，再完成 GREEN；backend focused `193 passed`、跨層回歸 `2179 passed`，full artifact `164/2509` 維持 `1637 verified / 733 unverifiable / 139 mismatch`，移除 6 個 provider/duration non-claims。正式 runtime reload、doctor、diff guards 與 push 通過。本批只改 read-only extraction boundary，不寫 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3768 / classify scenario targets without canonical scalar

- `#拆解問題` / `#差距分析` / `#來源品質`：fresh full artifact audit 找到 98 筆熊／基／牛情境 claim；它們有 scenario semantic marker，但 snapshot 沒有可回溯的 canonical scenario scalar，原本只顯示 `no_matching_snapshot_path`。
- `#偏誤辨識` / `#偏誤降低` / `#最小變更`：只對 exact normalized `熊市情境`、`基本情境`、`牛市情境`、`熊基牛情境` 輸出 `scenario_target_not_canonical`；不借用 `content_credibility`、DCF intrinsic value、current price 或其他 target path，且保留有 canonical `price_targets` 情境欄位時的正常核驗。
- `#可驗證性` / `#可逆性` / `#責任`：先以無 canonical scenario snapshot fixture 取得 RED，再加入 reason mapping、shared helper/cache-buster 與 canonical control；backend focused `192 passed`、shared helper `10 passed`、跨層回歸 `2179 passed`，full artifact `164/2515` 維持 `1637 verified / 739 unverifiable / 139 mismatch`，新增 `scenario_target_not_canonical=98` 且 `no_matching_snapshot_path=12`。正式 reload 後目標 artifact 的 HTML/Markdown/data 與 health/ready 均 `200`，helper、doctor、diff guards 與 push 通過。本批只改 read-only diagnostics，不寫 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3767 / classify stop-loss controls without canonical risk field

- `#拆解問題` / `#差距分析` / `#來源品質`：fresh residual audit 找到 13 筆 `防軋空停損點`／`價格停損條件`；它們有 stop-loss semantic marker，但 snapshot 沒有 canonical `risk_price`／stop-loss scalar，原本泛化為 `no_matching_snapshot_path`。
- `#偏誤辨識` / `#偏誤降低` / `#溝通設計`：新增 exact normalized label 的 `risk_control_not_canonical` reason；不把停損價借成 current price、壓力位或其他同值欄位，shared helper 顯示白話「風險控制沒有 canonical 欄位」。若有 `data.risk_price`，仍保留一般 matched/mismatch 判定。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED（stop-loss fixture `1 failed`、canonical field control passed），再 GREEN；backend focused `2 passed`、shared helper `10 passed`、完整 evidence `190 passed`、跨層回歸 `1862 passed`，full artifact `164/2515` 為 `1637 verified / 739 unverifiable / 139 mismatch`，`risk_control_not_canonical=13`、`no_matching_snapshot_path=110`。正式 reload 後 `2308_TW_v3_report_20260815_164400.html`、`3324_TWO_v3_report_20260815_183525.html`、`6282_TW_v3_report_20260815_195444.html` 的 HTML/Markdown/data、health/ready 均 `200`；stop-loss claims 均為 `unverifiable`／`risk_control_not_canonical`／空 matched path，helper/cache-buster `200`；doctor、diff guards 通過，push 待完成。

## D3766 / classify derived downside metrics without canonical scalar

- `#拆解問題` / `#差距分析` / `#來源品質`：fresh full artifact audit 找到 11 筆 `潛在下行空間` 百分比 claim；這是由現價／目標價推導的 derived metric，snapshot 沒有 canonical `downside_pct` scalar，原本只得到泛化 `no_matching_snapshot_path`。
- `#偏誤辨識` / `#偏誤降低` / `#最小變更`：只對 exact normalized label `潛在下行空間`／`potentialdownside` 在沒有 candidate 時輸出既有 `derived_metric_not_canonical`；不自行重算、不借 `current_price`／`target_price` 路徑，也保留有 `data.downside_pct` 時的正常 verified/mismatch 行為。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED（derived-downside fixture `1 failed`、canonical field control passed），再 GREEN；focused `2 passed`、完整 evidence `188 passed`、跨層回歸 `1860 passed`，full artifact `164/2515` 為 `1637 verified / 739 unverifiable / 139 mismatch`，`derived_metric_not_canonical=13`、`no_matching_snapshot_path=123`。正式 reload 後 `1623_TW_v2_report_20260815_154718.html` 與 `2308_TW_v1_report_20260815_161733.html` 的 HTML/Markdown/data、health/ready 均 `200`，兩筆 downside claims 均為 `unverifiable`／`derived_metric_not_canonical`／空 matched path；doctor、diff guards 通過，push 待完成。

## D3765 / route currency-prefixed legacy recommendation horizons

- `#拆解問題` / `#差距分析` / `#責任`：residual audit 找到四筆 legacy recommendation table claim 以 `NT$209.0；6個月`、`NT$254.0；12個月` 等格式出現；它們沒有 persisted parsed/structured context 或 canonical target path，但前綴金額使既有 legacy horizon regex 沒有命中。
- `#偏誤辨識` / `#偏誤降低` / `#限制條件`：只在 normalized label 符合幣別前綴數值＋3/6/12 個月，且 raw row 明示 `最終投資建議` 時輸出 `legacy_conclusion_without_snapshot_path`；不借 `analyst_target`、另一個 horizon 或 content metadata，parsed context 存在時仍是 `missing_semantic_path`。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED（1 failed、185 deselected，另有一次編譯括號錯誤已定位修正），再 GREEN；focused `3 passed`、完整 evidence `186 passed`、跨層回歸 `1858 passed`，full artifact `164/2515` 為 `1637 verified / 739 unverifiable / 139 mismatch`，`legacy_conclusion_without_snapshot_path=207`、`missing_semantic_path=8`。正式 reload 後 `1623_TW_v2_report_20260815_154718.html` 與 `3324_TWO_v3_report_20260815_183525.html` 的 HTML/Markdown/data、health/ready 均 `200`；四個 currency-prefixed horizon claims 均為 `unverifiable`／`legacy_conclusion_without_snapshot_path`／空 matched path。doctor、diff guards 與 push 通過。

## D3764 / classify derived margin-short ratios for operators

- `#拆解問題` / `#差距分析` / `#來源品質`：residual audit 找到 `6226.TW/v4` 的 `券資比 1.25%` 與 `0052.TW/v4` 的 `券資比 0.75%`；snapshot 只有融資／融券餘額，沒有 canonical ratio scalar，原本泛化為 `missing_semantic_path`。
- `#偏誤辨識` / `#偏誤降低` / `#溝通設計`：新增 exact `derived_metric_not_canonical` reason，仍維持 `unverifiable`，不自行推導、不把 component balance 當 ratio；shared quality helper 顯示「衍生指標沒有 canonical 欄位」，並以新 cache-buster 讓 history/watchlist 載入最新文字。
- `#可驗證性` / `#責任`：先取得 RED（backend 1 failed、frontend 1 failed），再 GREEN；backend focused `1 passed`、完整 evidence `185 passed`、frontend `10 passed`、跨層回歸 `1857 passed`，full artifact `164/2515` 為 `1637 verified / 739 unverifiable / 139 mismatch`，`derived_metric_not_canonical=2`、`missing_semantic_path=12`。正式 reload 後兩份 ratio artifact HTML/Markdown/data 均 HTTP `200`，live reason 正確，shared helper/cache-buster、current-quality summary、health/ready、doctor、diff guards 通過；待完成本批 push。

## D3763 / bind narrative S&P 500 change to the SPY path

- `#拆解問題` / `#差距分析` / `#證據基礎`：residual audit 找到 `2887.TW/v4` 的 `S&P 500 與台股加權指數近期震盪（Change 1d: -1.03% ~ -1.09%）`，原本因 KV label 截斷而是 `missing_semantic_path`；snapshot 有 `SPY.change_1d_pct=-1.0331` 與 `^TWII.change_1d_pct=-1.0965`，必須保留 symbol identity。
- `#偏誤辨識` / `#偏誤降低` / `#限制條件`：只有同句同時出現 S&P 500、台股加權指數與 Change 1d 才映射第一個值到 `data.global_market_context.items[spy].change_1d_pct`；沒有 SPY field 或只有台股數值時不借用其他 symbol。
- `#可驗證性` / `#抽樣` / `#描述統計`：先取得 RED（2 failed、183 deselected），再 GREEN；focused `2 passed`、完整 evidence `185 passed`、跨層回歸 `1822 passed`，full artifact `164/2515` 為 `1637 verified / 739 unverifiable / 139 mismatch`，`missing_semantic_path=14`。正式 reload 後 `2887_TW_v4_report_job_8afe44a2d4e6.html` 的 HTML/Markdown/data 與 health/ready 均 HTTP `200`，live `Change 1d` verified 到 SPY path，doctor、diff guards 通過；待完成本批 push。

## D3762 / separate analysis scores from snapshot evidence

- `#拆解問題` / `#差距分析` / `#受眾`：residual audit 找到 99 筆 exact analysis-rubric labels（品牌、網路效應、轉換成本、成本優勢、專利技術、FOMO、聰明錢派發與 Score），它們是報告中的分析分數，但沒有 canonical snapshot candidate，操作員目前只能看到泛化的 `missing_semantic_path`。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：新增 exact label-only `analysis_metadata_not_evidence` reason；不把數字分數借成財務／行情 evidence，不改 `unverifiable`、verdict、snapshot、artifact、index、review、rerun、repair 或 queue。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED（1 failed、182 deselected），再 GREEN；focused `1 passed`、完整 evidence `183 passed`、跨層回歸 `1820 passed`，full artifact `164/2515` 維持 `1636 verified / 740 unverifiable / 139 mismatch`，`analysis_metadata_not_evidence=99`、`missing_semantic_path=15`。正式 reload 後 `1623_TW_v1_report_20260815_153238.html` 的 HTML/Markdown/data 與 health/ready 均 HTTP `200`；live 品牌評分為 `analysis_metadata_not_evidence`、Price mismatch 仍可見，doctor、diff guards 通過；待完成本批 push。

## D3761 / map exact standalone `Price` without hiding stale values

- `#拆解問題` / `#差距分析` / `#證據基礎`：full artifact audit 找到 `1623.TW/v1` 的 `Price: 209.0 TWD`，snapshot 有 `data.current_price=201.0`；原本沒有 exact English `Price` path，造成 `missing_semantic_path`，無法把內容過期問題交給人工核對。
- `#偏誤辨識` / `#偏誤降低` / `#限制條件`：只對 standalone exact `Price` 映射 current-price path；`Price Target` 以 exact label boundary 排除，不把目標價借成現價，也不把 mismatch 放寬成 verified。這只做 read-only evidence mapping，不寫 snapshot、artifact、index、review、rerun、repair 或 queue。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED（1 failed、1 passed），再 GREEN；focused `2 passed`、完整 evidence `182 passed`，full artifact `164/2515` 為 `1636 verified / 740 unverifiable / 139 mismatch`，`missing_semantic_path=114`、`snapshot_value_mismatch=139`。正式 reload 後 `1623_TW_v1_report_20260815_153238.html` 的 HTML/Markdown/data 與 health/ready 均 HTTP `200`，live claim 維持 `Price=209.0 TWD` 對 `data.current_price=201.0` 的 `snapshot_value_mismatch`，doctor、import/docs/diff guards 通過；待完成本批 push。

## D3760 / map `vs Sale Today` to the borrowed-short sale path

- `#拆解問題` / `#差距分析` / `#來源品質`：full artifact audit 找到 `9921.TW/v4` 的 `Borrowed Short Return Today: 463k vs Sale Today: 156k`；`vs Sale Today` 的 156k 與 snapshot `borrowed_short_sale_today=156000` 同值，但原本沒有專用 label/path mapping。
- `#偏誤辨識` / `#偏誤降低` / `#限制條件`：只對精確 `vs Sale Today` 建立 `borrowed_short_sale_today` + `shares_to_thousands`；只有 unit=`k` 才換算 raw shares。return claim 仍只能走 `borrowed_short_return_today`，不做最近數字或跨 path fallback。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `1 passed`、完整 evidence `180 passed`，full artifact `164/2515` 為 `1636 verified / 741 unverifiable / 138 mismatch`，`missing_semantic_path=115`，其餘 reason 不變；正式 reload 後 health/ready `200/200`、8080 `127.0.0.1`，目標 HTML/Markdown/data 均 HTTP `200`，Markdown 保留 463k/156k claim、data 的兩個 TWSE 借券欄位為 463000/156000；本批不改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3759 / map FRED US CPI evidence to its canonical macro path

- `#拆解問題` / `#差距分析` / `#來源品質`：full artifact audit 的唯一窄可修 residual 是 `6282.TW/v1` 的 `US CPI YoY: 3.3039%`；snapshot 的 FRED `data.macro_indicators.indicators.us_cpi_yoy.value` 同值存在，原本因沒有 macro field hint 而是 `missing_semantic_path`。
- `#偏誤辨識` / `#偏誤降低` / `#限制條件`：只接受 `US CPI YoY`／`CPI YoY`／`美國 CPI 年增率` 到 exact `us_cpi_yoy.value`；同值的 `^TNX`、全球市場節點、其他宏觀欄位與 `summary_text` 不借用，缺 path 仍 `no_matching_snapshot_path`／`unverifiable`。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；CPI positive/boundary focused `2 passed`、完整 evidence `179 passed`，full artifact `164/2515` 為 `1635 verified / 742 unverifiable / 138 mismatch`，`missing_semantic_path=116`，其餘 reason 不變；正式 reload 後 health/ready `200/200`、8080 `127.0.0.1`，目標 HTML/Markdown/data 均 HTTP `200`，HTML 保留 `Evidence gate: caution` 與 CPI claim、data macro status `success`；本批不改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3758 / classify explicitly unavailable short-balance evidence

- `#拆解問題` / `#差距分析` / `#來源品質`：full artifact audit 的唯一窄 residual 是 `6141.TW/v4` `Short Balance: 0 (or null/not provided as a significant number)`；snapshot 的 `short_balance` 真實為 `None`，所以「沒有 candidate」代表來源不可用，不是數字 0 或錯誤 path。
- `#偏誤辨識` / `#偏誤降低` / `#限制條件`：只在 `short_balance` marker、原文明示 null／N/A／not provided／unavailable、且 canonical candidate 為空時輸出 `snapshot_field_unavailable`；一般 short balance 仍照既有 exact path verified，margin／borrowed-short／其他籌碼欄位不借用。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `2 passed`、完整 evidence `178 passed`、HCS/docs/import `639 passed`，line guard `349`、`py_compile`、`git diff --check` 通過。full artifact `164/2515` 維持 `1634 verified / 743 unverifiable / 138 mismatch`，`no_matching_snapshot_path` `135→134` 並新增 `snapshot_field_unavailable=1`；本批不改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3757 / surface evidence reason counts in current-quality views

- `#拆解問題` / `#差距分析` / `#受眾`：current-quality summary 只有「證據關卡需注意幾份」，但 persisted gate 已有 `unverifiable_reason_counts`；watchlist target 也只顯示 conformance reason，操作員無法快速分流數值 mismatch 與研究來源邊界。
- `#來源品質` / `#語意含義` / `#溝通設計`：後端只讀彙總同一 current scope 的既有 reason counts，單筆 target 保留自己的 counts；共用 helper 用固定中文標籤、數量排序與未知 code 原樣保留，兩個入口維持相同語意。
- `#可驗證性` / `#描述統計` / `#責任`：先用新增 backend/frontend tests 取得 RED，再 GREEN；focused `35 passed`、完整 evidence `177 passed`、品質/evidence/conformance `998 passed`、import/current-quality/frontend `539 passed`、HCS/docs/static `274 passed`，helper line guard `44`、evidence gate line guard `349`、Node syntax／`py_compile`／`git diff --check` 通過。full artifact `164/2515` 維持 `1634 verified / 743 unverifiable / 138 mismatch`；reload 後 live health/ready `200`、8080 `127.0.0.1`、current summary `164` 份、`evidence_failed_count=10` 與 aggregate reason counts 正常，三個 helper cache-buster HTTP `200`。這輪不改 verdict/status、sampled claim、snapshot、artifact、index、review、rerun、repair 或 queue；full artifact 與 current persisted/sample scope 仍分開解讀。

## D3756 / classify research-source evidence boundaries

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `5871.TW/v4` 的 `目標價：130元（Factset預估值）` 與 `7795.TW/v4` 的 `目標價：605元（參考市場研究觀點）`；兩者沒有同路徑 canonical snapshot，但原本只顯示 `no_matching_snapshot_path`，不利於判斷是欄位缺漏還是研究來源限制。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：新增 `research_source_not_canonical` read-only reason；FactSet／券商研究／市場研究仍不可核驗，不借用 current price、DCF、EPS、其他 provider 或同值欄位，verdict 與 evidence status 不變。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `2 passed`、完整 evidence `177 passed`、品質/evidence/conformance `998 passed`、line guard `349`、`py_compile`、`git diff --check` 通過。full artifact `164 reports / 2515 claims` 為 `1634 verified / 743 unverifiable / 138 mismatch`，reason 為 `confidence_metadata_not_evidence=283`、`legacy_conclusion_without_snapshot_path=203`、`missing_semantic_path=117`、`no_matching_snapshot_path=135`、`news_source_not_canonical=3`、`research_source_not_canonical=2`、`snapshot_value_mismatch=138`。正式 reload 後兩筆 research target 均維持 `unverifiable`／空 path並分類為 `research_source_not_canonical`；本批不改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3755 / classify Chinese catalyst prices as non-canonical news evidence

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `6226.TW/v4` 的 `近期低點/支撐參考：15.1（2026-06-25 催化劑提到之價格）`；中文「催化劑」且省略幣別時，既有 generic `risk_price` fallback 可能在 snapshot 同值時誤判為 verified。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：將 `催化劑` 與 `新聞`／`market_catalysts` 使用相同來源邊界，不要求 TWD／元才阻擋；即使同值、同日或存在 `data.risk_price`，也不借用 `price_history` 或 generic risk path。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `6 passed`、完整 evidence `176 passed`、品質/evidence/conformance `998 passed`、import/docs `640 passed`、line guard `349`、`py_compile`、`git diff --check` 通過。full artifact `164 reports / 2515 claims` 為 `1634 verified / 743 unverifiable / 138 mismatch`，reason 為 `confidence_metadata_not_evidence=283`、`legacy_conclusion_without_snapshot_path=203`、`missing_semantic_path=117`、`no_matching_snapshot_path=137`、`news_source_not_canonical=3`、`snapshot_value_mismatch=138`。正式 reload 後 live 6226 target 維持 `unverifiable`／空 path 並分類為 `news_source_not_canonical`，Markdown/data/health/ready 均 HTTP `200`；current projection 為 conformance `80 passed / 74 warning / 10 blocked`、content `99 passed / 57 warning / 8 blocked`、evidence `135 approved / 26 caution / 3 rejected`；本批不改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3754 / infer a yearless month extremum only from a unique snapshot year

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `6213.TW/v4` 的 `367.41 TWD（6 月份高點轉支撐）`，snapshot 的 2026-06 canonical month-high 同值，但 claim 省略年份使既有 matcher 落到 `no_matching_snapshot_path`。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：無年份只接受帶 `M 月`／`M 月份` 的月份語意，且 snapshot 該月份年份唯一、數值直接位於月份語意前、沒有新聞／催化劑；報價前的數字、跨年份與新聞 claim 不映射，明寫年份仍沿用 exact month path。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `3 passed`、完整 evidence `175 passed`、品質/evidence/conformance `1173 passed`、line guard `349` 通過，full artifact `2515 claims: 1634 verified / 743 unverifiable / 138 mismatch`，`no_matching_snapshot_path=138`。正式 reload 後 live 6213 target verified 到 `data.price_history[month=2026-06].high`，Markdown/data/health/ready 均 HTTP `200`，current quality 為 evidence `135/26/3`、content `99/57/8`、conformance `80/74/10`，本批未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3753 / map compact institutional total only with category context

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `2885.TW/v4` 的 Institutional Trading 區段在 `Foreign`、`Investment Trust` 後列出 bare `Total: 48,055.45`；snapshot 有唯一 `data.institutional_trading.total_net_buy_thousand_shares=48,055.45`，但 parser 沒有把 compact label 綁到總額欄位。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只接受 `Total` 前兩行同時含 `Foreign` 與 `Investment Trust` 的上下文，孤立 `Total`、一般同值欄位與分類 claim 不借用總額 path；既有 Foreign／Investment Trust 仍只核對各自 category fields。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `2 passed`、完整 evidence `172 passed`、品質/evidence/conformance `1170 passed`、import/docs `640 passed`、line guard `349` 通過，full artifact `2515 claims: 1633 verified / 744 unverifiable / 138 mismatch`，`missing_semantic_path=117`。正式 reload 後 live 2885 target verified 到 `data.institutional_trading.total_net_buy_thousand_shares`，Markdown/data/health/ready 均 HTTP `200`，current quality 為 evidence `135/26/3`、content `99/57/8`、conformance `80/74/10`，本批未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3752 / separate historical support from later news values

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `6141.TW/v4` 的 `關鍵支撐位：30.1 TWD。此為 2026-07-31 之近期低點。此外，2026-07-22 新聞提及之漲停價 42.35 TWD`；30.1 與 canonical `data.price_history[2026-07-31].prices[10]` 一致，但同一行後段新聞 value 使原 parser 無法分離兩個語意。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只在完整日期前後有括號或 `此為` 明示 claim 關聯、且日期到句段邊界沒有新聞／催化劑語意時映射 exact daily path；後續新聞 value、直接催化劑句與後文另述歷史價不綁定，避免把同一行的新聞數字借給歷史支撐位。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused D3752 tests `2 passed`、完整 evidence `170 passed`、品質/evidence/conformance `1168 passed`、line guard `349` 通過，full artifact `2515 claims: 1632 verified / 745 unverifiable / 138 mismatch`，`news_source_not_canonical=2`。正式 reload 後 live 6141 target verified 到 `data.price_history[2026-07-31].prices[10]`，Markdown/data/health/ready 均 HTTP `200`，current quality 為 evidence `135/26/3`、content `99/57/8`、conformance `80/74/10`，本批未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3751 / map dated support and pressure evidence without later-text binding

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `1102.TW/v4` 的 `35.63`／`33.00`、`2324.TW/v4` 的 `36.0`、`2031.TW/v4` 的 `37.9` 都能對到 exact daily `price_history`，但支撐／壓力 label 沒有 semantic path。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只接受支撐／壓力、完整日期、價格單位與明示價格／月底價／高低點／收盤語意，並要求日期緊接在 claim 數值的單位括號後；中文 `催化劑`、新聞來源與後文另述的歷史價格不映射，避免同值或鄰近日期借證據。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `7 passed`、完整 evidence `168 passed`、品質 `1166 passed`、line guard `349` 通過，full artifact `2515 claims: 1631 verified / 746 unverifiable / 138 mismatch`，`missing_semantic_path=118`。正式 reload 後 1102、2324、2031 target 全部 verified，Markdown/data/health/ready 均 HTTP `200`，current quality 為 evidence `135/26/3`、content `99/57/8`、conformance `80/74/10`，本批未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3750 / map dated latest-price evidence to exact history point

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `6226.TW/v4` 的 `最新價格 (2026-07-24): 18.8 元` 與 `data.price_history[2026-07-24].prices[11]=18.8` 一致，但 parser 沒有把完整日期 latest-price label 綁到 snapshot。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只接受完整日期與元／TWD 單位，建立 exact daily path；日期缺失時即使 `current_price` 同值也維持 `no_matching_snapshot_path`，不把當前價當作歷史日期證據。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `2 passed`、完整 evidence `164 passed`、品質 `1162 passed`、line guard `349` 通過，full artifact `2515 claims: 1627 verified / 750 unverifiable / 138 mismatch`，`missing_semantic_path=118`。正式 reload 後 live API target verified 到 `data.price_history[2026-07-24].prices[11]`，Markdown/data/health/ready 均 HTTP `200`，current quality 為 evidence `135/26/3`、content `99/57/8`、conformance `80/74/10`，本批未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3749 / extract complete three-month price series without guessing year

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `2618.TW/v4` 的 `觀察近三個月價格（6/30: 42.78, 7/31: 43.3, 8/21: 42.6）` 只被抽出第一筆，`7/31` 與 `8/21` 漏出 evidence gate；canonical snapshot 同時提供三個 exact daily `price_history` points。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只對明示「觀察近三個月價格」的同一行補抽後續 date/value pairs；要求前文年份與 snapshot 該月份年份都唯一且一致，`2025/2026` 月份歧義保留 `missing_semantic_path`，不以月份或數值相近猜測。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `2 passed`、完整 evidence `162 passed`、品質 `1160 passed`、line guard `348` 通過，full artifact `2515 claims: 1626 verified / 751 unverifiable / 138 mismatch`，`missing_semantic_path=119`。正式 reload 後 live API 三筆 target 均 verified 到 `data.price_history[2026-06-30].prices[9]`、`[2026-07-31].prices[10]`、`[2026-08-21].prices[11]`，Markdown/data/health/ready 均 HTTP `200`，current quality 維持 evidence `134/27/3`、content `99/57/8`、conformance `80/74/10`，本批未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3748 / map indexed global-market changes by symbol and horizon

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `2337.TW/v4` 的 SMH 1d/5d change claims 被截成 `rketcontext[11].change1/5dpct`，而 snapshot 有 `items[smh].change_1d_pct=-2.2808`、`change_5d_pct=-1.0943`。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只保存此類截斷 label 的完整原行，要求 indexed path 與附近 `(SMH)` 同時存在；以 claim label 的 1d/5d token 選對欄位，禁止 5d 借用 1d、SMH 借用 QQQ、或無 symbol 時泛配。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `2 passed`、完整 evidence `160 passed`、品質 `1158 passed`、line guard `349` 通過，full artifact `2513 claims: 1623 verified / 752 unverifiable / 138 mismatch`，`missing_semantic_path=120`。正式 reload 後 live API 兩筆 target 均 verified 到 `data.global_market_context.items[smh].change_1d_pct`／`change_5d_pct`，Markdown/data/health/ready `200/200/200/200`，整份報告仍保留 `caution` 與人工確認，本批未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3747 / map current quote evidence and surface stale snapshot mismatch

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `2308.TW/v2` 的 `當前報價：1,885.0 TWD` 沒有 current-price semantic path；snapshot canonical `data.current_price=1,750.0`，兩者相差 `7.1618%`。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只新增 exact `當前報價` alias；一致值可 verified，不一致值必須保留 `snapshot_value_mismatch`，無 `current_price` 時不借用 `current_ratio`、其他 ticker 或 content metadata。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `3 passed`、完整 evidence `158 passed`、品質 `1156 passed`、line guard `349` 通過，full artifact `2513 claims: 1621 verified / 754 unverifiable / 138 mismatch`，`missing_semantic_path=122`。正式 reload 後 live API target 命中 `data.current_price=1750.0` 並判定 mismatch，Markdown/data/health/ready `200/200/200/200`，整份報告維持 `rejected`，本批未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3746 / map compact 5-day net-buy evidence without horizon fallback

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `1810.TW/v4` 的 `5-day: 4,504.85k (Net Buy)` 被 KV regex 截成 label `day`，而 canonical snapshot 有同值且唯一語意的 `last_5_trading_days_net_buy_thousand_shares`。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只接受 `day` parser artifact、raw `5-day:` 與 `Net Buy` 三個條件；`10-day`、daily total、30-day total 與只有同值的其他欄位不跨欄位核驗。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `2 passed`、完整 evidence `155 passed`、品質 `1153 passed`、import/docs `640 passed`、`py_compile`、`git diff --check`、line guard `349` 通過，full artifact `2513 claims: 1621 verified / 755 unverifiable / 137 mismatch`，`missing_semantic_path=123`。正式 reload 後 live API target verified 到 `data.institutional_trading.last_5_trading_days_net_buy_thousand_shares=4504.85`，Markdown/data `200/200`、health/ready `200/200`、queue depth `0`；整份報告仍為 `caution`，本批未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3745 / parse external Previous chip balances without false claims

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `2027.TW/v4` 的 English margin/short balance 行，在 unit 括號後的外置 `Previous:` 被 KV regex 吞成 `thousand shares). Previous=26` 假 claim；真正 `26,504`／`375` 沒有進入 evidence sample。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只接受 `Margin|Short balance`、主值、括號單位與外置 `Previous` 的完整句型；誤判 label 含括號且以 `Previous` 結尾時略過。前值只走既有 local-context `margin_previous_balance`／`short_previous_balance`，不以同值或鄰近欄位 fallback。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `2 passed`、完整 evidence `153 passed`、品質 `1151 passed`、`py_compile`、`git diff --check`、line guard `349` 通過，full artifact `2513 claims: 1620 verified / 756 unverifiable / 137 mismatch`，`missing_semantic_path=124`。正式 reload 後 live API target previous claims verified 到 `data.chip_data.twse_margin_short_sales.margin_previous_balance=26504`／`short_previous_balance=375`，Markdown/data `200/200`、health/ready `200/200`、queue depth `0`；整份目標報告仍保留 `caution` 與其他 claim 的人工確認，本批未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3744 / map historical high-percentile PE band without generic fallback

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `2367.TW/v2` 的 `67.1x (歷史高分位帶)：45.63 TWD` 與 `data.pe_river_chart.bands.67.1x[4]=45.63` 一致，但既有 matcher 只涵蓋 `中高分位帶`。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只在 exact `x歷史高分位帶` 且 raw text 明示倍率時映射 band-specific path；沒有該 band 不借用 `pe_ratio`、`multiples` 或其他價格值，generic fallback 反例保留 `unverifiable`。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `2 passed`、完整 evidence `152 passed`、品質 `1150 passed`、line guard `349` 通過，full artifact `2512 claims: 1618 verified / 757 unverifiable / 137 mismatch`，`missing_semantic_path=125`。正式 reload 後 live API 的目標 claim verified 到 `data.pe_river_chart.bands.67.1x[4]`、Markdown/data `200/200`，health/ready `200/200`、active jobs `0`，current quality 為 conformance `80/74/10`、content `99/57/8`、evidence `134/27/3`，未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3743 / map exact Chinese borrowed-short fields without ratio fallback

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `6226.TW/v4` 的 `借券餘額：286000 張`、`當日借券賣出：40000 張` 都有唯一 canonical snapshot field，但中文 label 沒有命中既有 English hint。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只新增兩個 exact aliases，分別映射 borrowed short sale balance／today；不把 `借券還券`、`券資比`、`Total` 或其他 component value 互相借用，既有 shares-to-lots 邊界保留。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `1 passed`、完整 evidence `150 passed`、品質 `1148 passed` 通過，full artifact `2512 claims: 1617 verified / 758 unverifiable / 137 mismatch`，`missing_semantic_path=126`。正式 reload 後 live API 的兩筆目標 claim 都 verified、Markdown/data `200/200`，health/ready `200/200`、active jobs `0`，current quality 為 conformance `80/74/10`、content `99/57/8`、evidence `134/27/3`，未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3742 / map exact price-sales evidence without EPS collision

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `3653.TW/v3` 的 `PS: 31.18` 與 canonical `data.ps_ratio=34.65`，但 `PS`／`P/S`／`Price/Sales` 沒有 semantic path；短標籤又容易與 `EPS` 產生邊界碰撞。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只新增 exact price-sales aliases 與 `P/S` 邊界 matcher；`EPS` 維持 `data.eps`，缺少 `ps_ratio` 或數值不一致不借用 PE／EPS／其他 valuation field。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `2 passed`、完整 evidence `149 passed`、品質 `1147 passed`、line guard `348` 通過，full artifact `2512 claims: 1615 verified / 760 unverifiable / 137 mismatch`，`missing_semantic_path=128`。正式 reload 後 live API 的 `PS:31.18` 命中 `data.ps_ratio=34.65` 並保留 mismatch，health/ready `200/200`、active jobs `0`，current quality 為 conformance `80/74/10`、content `99/57/8`、evidence `134/27/3`，未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3741 / map exact US 10Y and VIX global-market evidence labels

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `US 10Y Yield`、`US 10Y Treasury Yield` 與 `VIX` 都有 snapshot 的 `tnx.latest`／`vix.latest`，但 exact label 沒有 path；`US CPI YoY` 沒有同語意 canonical node，不能借用 TNX 或其他市場數值。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只新增 exact US 10Y／VIX alias；錯值仍回到各自指定 path 判 `mismatch`，US 10Y 不跨配 VIX、VIX 不跨配 TNX，CPI 維持 `missing_semantic_path`。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `3 passed`、完整 evidence `147 passed`、品質 `1145 passed`、line guard `349` 通過，full artifact `2512 claims: 1615 verified / 761 unverifiable / 136 mismatch`，`missing_semantic_path` 降至 `129`。正式 reload 後 live API 重驗 `3324.TWO` verified、`6282.TW` 兩筆 mismatch、CPI unverifiable，health/ready `200/200`、active jobs `0`，current quality `164` 份為 conformance `80/74/10`、content `99/57/8`、evidence `134/27/3`，未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3740 / split composite 52-week high-low evidence claims

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `6226.TW/v4` 的 `52 週高低：28.95 / 6.25 (market_data)` 只抽出第一個數值，第二個低點未進 evidence gate；canonical snapshot 同時有 `data.week_52_high` 與 `data.week_52_low`。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只在 `週高低` label、slash-separated pair 與同句 `market_data` 同時成立時拆出 secondary claim；generic `高低` 不推論 52 週欄位，第一／第二數值各自綁定 high／low，缺欄位或 mismatch 不 fallback。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `4 passed`、完整 evidence `144 passed`、品質 `1142 passed`、line guard `349` 通過，full artifact `2512 claims: 1614 verified / 764 unverifiable / 134 mismatch`，`missing_semantic_path` 降至 `132`，複合 residual `0`。正式 reload 後 live API Markdown/data HTTP `200/200`，兩筆目標 claim verified 到 `data.week_52_high`／`data.week_52_low`，current quality `164` 份為 conformance `80/74/10`、content `99/57/8`、evidence `134/27/3`，health/ready `200/200`、active jobs `0`，未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3739 / map explicit dated close for bottom-boundary labels

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `2301.TW/v4` 的 `強勁底部分界：207.09 TWD（2026-07-31 收盤價）` 與 `price_history` 同日值一致，但 label 沒有進既有 dated-price semantic path。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只把 `底部` label 在同時有明確日期、收盤／close、TWD／元且相鄰數值一致時接到 `price_history[YYYY-MM-DD]`；`平台位置`、無收盤語意、新聞／催化劑與 mismatch 不借用價格節點。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `2 passed`、完整 evidence `140 passed`、品質 `1138 passed`、import/docs、`py_compile` 與 line guard `349` 通過，full artifact 為 `2510 claims: 1611 verified / 765 unverifiable / 134 mismatch`，reason `missing_semantic_path=133`；正式 reload 後 live API 驗證 `2301.TW/v4` 目標 claim，current quality 為 evidence `135/26/3`、content `99/57/8`、conformance `80/74/10`，health/ready `ok/ready`、doctor canonical paths 與 queue depth `0`、failed_recent `0`、failed_stale `10` 通過，未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3738 / map borrowed-short-return wording without sale fallback

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `2885.TW/v4` 的 `Today's borrowed short return: 525,000` 與 `2891.TW/v4` 的 `return: 2,844,160` 都能對到 snapshot 的 `borrowed_short_return_today`，但既有 hint 只涵蓋另一種詞序；`9921.TW/v4` 的 `vs Sale Today` 則沒有足夠語意可直接當還券量。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：新增 explicit `Today's borrowed short return` alias，並只在同一 borrowed-short-sale claim 中把 compact `return` 對到 `chip_data.twse_margin_short_sales.borrowed_short_return_today`；禁止跨到 `borrowed_short_sale_today`，`vs Sale Today` 保留人工確認。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `3 passed`、完整 evidence `138 passed`、品質 `1136 passed`、import/docs、`py_compile` 與 line guard `349` 通過，full artifact 為 `2510 claims: 1610 verified / 766 unverifiable / 134 mismatch`，reason `missing_semantic_path=134`；正式 reload 後 live API 驗證兩個 borrowed-return claim，`vs Sale Today` 仍 `unverifiable`，current quality 為 evidence `135/26/3`、content `99/57/8`、conformance `80/74/10`，health/ready `ok/ready`、doctor canonical paths 與 queue depth `0`、failed_recent `0`、failed_stale `10` 通過，未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3737 / map exact institutional category labels without total fallback

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `2885.TW/v4` 的 `Foreign: 22,509.2`、`Investment Trust: 3,144.84` 與 snapshot category fields 一致，但兩個 exact label 沒有 semantic path；同一段的 `Total: 48,055.45` 沒有足夠語意，不應直接借用總額欄位。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只新增 `Foreign`／`外資` 與 `Investment Trust`／`投信` 到各自 `net_buy_thousand_shares_by_category` path；generic `Total` 保留 `missing_semantic_path`，不因數值接近或相等跨 category/total source。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `2 passed`、完整 evidence `135 passed`、品質 `1133 passed`、import/docs、`py_compile` 與 line guard `349` 通過，full artifact 為 `2510 claims: 1608 verified / 768 unverifiable / 134 mismatch`，reason `missing_semantic_path=136`；正式 reload 後 live API 驗證兩個 category claim，`Total` 仍 `unverifiable`，current quality 為 evidence `135/26/3`、content `99/57/8`、conformance `80/74/10`，health/ready `ok/ready`、doctor canonical paths 與 queue depth `0`、failed_recent `0`、failed_stale `10` 通過，未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3736 / map compact English last-5 institutional net-buy labels

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `6505.TW/v4` 的 `Last 5 days Net Buy: 22,514.34k` 與 snapshot 的 `institutional_trading.last_5_trading_days_net_buy_thousand_shares=22514.34` 一致，但 normalized label `last5daysnetbuy` 沒有命中既有 alias。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只新增 compact English alias 到專用 5-day institutional path；即使與 `total_net_buy_thousand_shares` 同值也不跨欄位核驗，缺少專用 field、daily value 或其他 institutional category 仍保留人工確認。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `5 passed`、完整 evidence `133 passed`、品質 `1131 passed`、import/docs `640 passed`、`py_compile`、`git diff --check` 與 line guard `349` 通過，full artifact 為 `2510 claims: 1605 verified / 771 unverifiable / 134 mismatch`，reason `missing_semantic_path=139`；正式 reload 後 live API 直接驗證目標 claim 為 `verified → data.institutional_trading.last_5_trading_days_net_buy_thousand_shares=22514.34`，整份報告維持 `caution`，current quality 為 evidence `135/26/3`、content `99/57/8`、conformance `80/74/10`，health/ready `ok/ready`、doctor canonical paths 與 queue depth `0`、failed_recent `0`、failed_stale `10` 通過，未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3735 / map explicit monthly close evidence for prior-high labels

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `6278.TW/v4` 的 `波段前高：214.85 TWD（2026 年 5 月收盤價）` 與 `price_history` 的 2026-05 月末值一致，但 month-end matcher 漏掉 `前高` label，造成 canonical claim 落到 `missing_semantic_path`。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只在 raw claim 明示指定月份 `收盤價`／月底收盤語意、label 含 `前高`、月份年份唯一、相鄰數值一致且非新聞來源時建立 `data.price_history[month-end=YYYY-MM]` path；`平台位置`、非收盤語意、月份歧義與真實 mismatch 不借用月末值。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `11 passed`、完整 evidence `131 passed`、品質 `1129 passed`、import/docs `640 passed`，full artifact 為 `2510 claims: 1604 verified / 772 unverifiable / 134 mismatch`，reason `missing_semantic_path=140`；正式 reload 後 live API 直接驗證目標 claim 為 `verified → data.price_history[month-end=2026-05]=214.85`，current quality 維持 evidence `135/26/3`、content `99/57/8`、conformance `80/74/10`，health/ready、doctor 與 queue 通過，未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3734 / map explicit 52-week low evidence for defense-line labels

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `8422.TW/v4` 的 `長期防線：19.15 TWD（52 週最低價）` 已有 `data.week_52_low=19.15`，但 label 不在既有支撐／壓力集合，造成 canonical claim 落到 `missing_semantic_path`。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只在 raw claim 同時有防線語意、明示 52 週最高／最低與 TWD／元數值，且數值與對應 snapshot field 一致時建立 `week_52_high`／`week_52_low` path；沒有 52 週 marker 的一般防線不借用週低點來源，仍保留 `unverifiable`。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `7 passed`、完整 evidence `129 passed`、品質 `1127 passed`、import/docs `640 passed`，full artifact 為 `2510 claims: 1603 verified / 773 unverifiable / 134 mismatch`，reason `missing_semantic_path=141`；正式 reload 後 live API 直接驗證目標 claim 為 `verified → data.week_52_low=19.15`，current quality 維持 evidence `135/26/3`、content `99/57/8`、conformance `80/74/10`，health/ready、doctor 與 queue 通過，未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3733 / map explicit 52-week extremes for numbered pressure labels

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `6426.TW/v4` 的 `波段壓力二：294.0 TWD（52 週最高價）` 已有 `data.week_52_high=294.0`，但固定 label 清單漏掉編號／階段式壓力語意，造成可核驗 claim 落到 `no_matching_snapshot_path`。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只在 raw claim 同時有壓力／支撐語意、明示 52 週最高／最低與 TWD／元數值，且數值與對應 snapshot field 一致時建立 `week_52_high`／`week_52_low` path；沒有 52 週 marker 的一般或編號式 label 不借用週高低點來源，仍保留 `unverifiable`。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `5 passed`、完整 evidence `127 passed`、品質 `1125 passed`、import/docs `640 passed`、`py_compile`、`git diff --check` 與 line guard `349` 通過。full artifact 為 `2510 claims: 1602 verified / 774 unverifiable / 134 mismatch`，reason `no_matching_snapshot_path=143`；正式 reload 後 live API 直接驗證目標 claim 為 `verified → data.week_52_high=294.0`，health/ready、doctor 與 queue 通過，current quality 維持 evidence `135/26/3`、content `99/57/8`、conformance `80/74/10`，未改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3732 / classify compact legacy horizons without inventing target evidence

- `#拆解問題` / `#差距分析`：full artifact audit 找到 legacy v1/v2/v3 的 compact `最終投資建議` row；`避免／持有／放空；3個月`、`6個月`、`12個月` 缺少 persisted parsed／structured context，原本卻與一般 semantic mapping 缺口混在一起。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只有 raw text 明示 `最終投資建議`、horizon label 為 3/6/12 個月且 context 全空時改用 `legacy_conclusion_without_snapshot_path`；有 context 仍是 `missing_semantic_path`，一般營收月份、`analyst_target`、content metadata 與其他 horizon 不借證據，status／verdict 不變。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `5 passed`、完整 evidence `125 passed`、品質 `1123 passed`、import/docs、`py_compile`、`git diff --check` 與 line guard `349` 通過。full artifact 為 `2510 claims: 1601 verified / 775 unverifiable / 134 mismatch`，reason `missing_semantic_path=142`、`legacy_conclusion_without_snapshot_path=203`；live historical API 已驗證 `3653.TW/v3`、`3324.TWO/v2`、`6282.TW/v2`，current summary 維持 evidence `135/26/3`、content `99/57/8`、conformance `80/74/10`，health/ready、doctor、queue `0` 通過，未改動 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3731 / map explicit month-end closing prices without widening evidence

- `#拆解問題` / `#差距分析`：full artifact audit 找到 `7 月底收盤價`、`2026 年 5 月底收盤價` 等 claim 已有 canonical `price_history` 月末節點，卻被當成沒有 matching path；同時要保留 `月底的平台位置` 與非明示收盤語意的人工確認邊界。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：只在支撐／壓力／高低點語意、明示 `月底收盤價`／`月末收盤價`、唯一月份節點與相鄰數值一致時映射 `data.price_history[month-end=YYYY-MM]`；第二個月底收盤值獨立抽取，新聞／催化劑、未明示收盤、平台位置、年份歧義與真實 mismatch 不借用 path。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `4 passed`、完整 evidence `122 passed`、品質/evidence/conformance `1120 passed`、import/docs、`py_compile`、`git diff --check` 與 line guard `349` 通過。full artifact 為 `2510 claims: 1601 verified / 775 unverifiable / 134 mismatch`，reason `no_matching_snapshot_path=144`；live current `164` 份為 evidence `135/26/3`、content `99/57/8`、conformance `80/74/10`，health/ready、doctor、queue `0` 通過，未改動 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3730 / expose stale-analysis context without weakening evidence verdicts

- `#拆解問題` / `#差距分析`：live `6282.TW/v4` 的 2 個 evidence mismatch 與 `decision_freshness=needs_rerun` 同時成立；這是快照更新後舊結論未重跑，不是 tolerance 或 semantic mapping 誤判。先以 response-time projection 的真實 row 取得 RED，保留 `rejected` 與 mismatch。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：沿用 `build_decision_freshness()` 只在 `requires_rerun` 時加 `freshness_context`；content warning 只複製狀態、結論／快照時間與原因，不帶 sampled claim raw text。current、approved 與無 stale marker 的 gate 不新增上下文。
- `#可驗證性` / `#描述統計` / `#責任`：RED→GREEN focused `136 passed`、品質 `1116 passed`、import/docs `640 passed`、full artifact `1594/781/134`，live current `164` 份為 evidence `135/26/3`、content `99/57/8`、conformance `80/74/10`，需重跑 `27` 份；health/ready、doctor、queue `0` 通過，未改動 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3729 / preserve comma-grouped integers and ratio source boundaries

- `#拆解問題` / `#差距分析`：full artifact audit 找到兩個不同的 false mismatch：`2027.TW/v4` 的句末千分位值 `1,177,000.` 被 KV regex 回退成 `1,177`；`6226.TW/v4` 的 `券資比` label 同時含有 `融券餘額`／`融資餘額`，被 generic balance hint 綁到 `margin_previous_balance=2367`。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：句點後只有在有空白且接下一句文字時才允許完整千分位 claim，避免 `1623.TW` ticker 被放寬；券資比／margin-short ratio 沒有 canonical ratio scalar 時明確返回空 semantic path，不用兩個 component balances 自行推導 verified，也不改既有真 mismatch。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `4 passed`、完整 evidence `117 passed`、品質/evidence/conformance `1114 passed`、import `504 passed`、docs `136 passed`、line guard `349`、`py_compile`、`git diff --check` 通過。full artifact 為 `1594 verified / 781 unverifiable / 134 mismatch`，reason `missing_semantic_path=198`；`2027.TW/v4` 已 verified、`6226.TW/v4` 維持 unverifiable。正式 reload 後 current `164` 份為 content `99/57/8`、conformance `80/74/10`、evidence `135/26/3`；healthz/readyz、queue depth `0`、failed_recent `0` 通過，未改動 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3728 / keep descriptive targets on canonical structured evidence

- `#拆解問題` / `#差距分析`：`2618.TW/v4` 的 `航空運輸業，目標價：43.75元` 被 generic target hint 帶入 DCF bear `32.04`，同時 structured target 的 `近 1-2 週` 前綴可能先產生數字 `1`。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：描述性 target label 只映射到同 snapshot 的 structured target path，不繼承 `valuation`／`dcf`；`近` 開頭的 horizon prefix 先排除，讓 `43.75` 與 `45.65` 保留為 canonical target values。exact target、FactSet、scenario／DCF 與無 source path 的人工確認邊界保留。
- `#可驗證性` / `#描述統計` / `#責任`：RED→GREEN target focused `7 passed`、完整 evidence `114 passed`、品質/evidence/conformance `1111 passed`、import `504 passed`、docs `136 passed`、line guard `349`、`py_compile`、`git diff --check` 通過。live current `164` 份為 content `99/57/8`、conformance `80/74/10`、evidence `135/26/3`；full artifact 為 `1593 verified / 780 unverifiable / 136 mismatch`，`2618.TW/v4` 43.75 命中 `rerun_context.structured_outputs.24.target_price`；healthz/readyz `ok/ready`、queue depth `0`、failed_recent `0`、failed_stale `10`，未改動 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3727 / keep later monthly extremum from rebinding prior support

- `#拆解問題` / `#差距分析`：`2344.TW/v4` 的同句支撐價 `179.5` 與後面的 `130.0（2026-07 低點）` 被月份極值 regex 共用同一 path；前值不是該日期的價位，卻被判成 mismatch。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：月份低點／高點只在 reported value 與日期前最近數字一致時建立 `price_history[month=YYYY-MM].low|high`；前一個情境價保持 `unverifiable`，不以同值、近鄰文字或另一個 claim 借證據，month-end、逐日、新聞與真實 mismatch 邊界保留。
- `#可驗證性` / `#描述統計` / `#責任`：先取得 RED，再 GREEN；focused `4 passed`、完整 evidence `112 passed`、品質/evidence/conformance `1109 passed`、import `504 passed`、docs `136 passed`、line guard `349`、`py_compile`、`git diff --check` 通過。live current `164` 份分布為 content `99/57/8`、conformance `80/74/10`、evidence `135/26/3`；full artifact 為 `1592 verified / 780 unverifiable / 137 mismatch`，`2344.TW/v4` 的 179.5 為 `unverifiable`／空 matched path；healthz/readyz `ok/ready`、queue depth `0`、failed_recent `0`、failed_stale `10`，未改動 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3726 / preserve numeric horizons and classify confidence metadata

- `#拆解問題` / `#差距分析`：全量 artifact audit 發現同一個 regex 邊界同時造成 `個月目標` 截斷與 `資料信心分數` 被錯放入一般 evidence missing-path 統計；前者損失語意，後者混淆資料可信度 metadata 與來源證據。
- `#偏誤辨識` / `#偏誤降低` / `#來源品質`：保留 `3/6/12個月` 的完整 label，並將 confidence claim 的來源邊界標成 `confidence_metadata_not_evidence`；不把 legacy target、FactSet／新聞或 DCF 同值數字互相借用，數值 mismatch 與 `unverifiable` verdict 邊界不變。
- `#可驗證性` / `#描述統計` / `#責任`：RED→GREEN focused `5 passed`、品質/evidence/conformance `1108 passed`、import `504 passed`、docs `136 passed`、line guard `349`、`py_compile`、`git diff --check` 通過。live current 164 份的 sampled reason 為 `no_matching=39`、`confidence_metadata=30`、`legacy=29`、`missing=16`、`news=2`；full artifact ratio=1.0 為 `1592 verified / 779 unverifiable / 138 mismatch`，`個月` 殘片 `0`，health/ready `ok/ready`、queue `0`、failed_recent `0`，未改動 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3725 / expose verified evidence sample counts

- `#拆解問題` / `#差距分析`：live non-approved evidence warning 已有 sampled、failed、unverifiable，但沒有直接揭露其中多少 claim 已 status=`verified`；操作員容易把「抽樣量」誤讀成「已核對量」。
- `#偏誤辨識` / `#偏誤降低` / `#可驗證性`：新增 `verified_count` 與 `evidence_verified_count`，只計算同一份 read-only gate 的 verified sampled claims；不改抽樣、tolerance、verdict、semantic path 或任何 persisted state，29 個 non-approved warning 全數保留 caution／rejected 邊界。
- `#來源品質` / `#責任`：先取得 RED，再以最小變更 GREEN；focused `2 passed`、完整品質/evidence/conformance `1105 passed`、import `504 passed`、docs `136 passed`、line guard `349`、`py_compile`、`git diff --check` 通過。reload 後 `3653.TW/v4` 為 `19/3/2/0/1`（claims/sampled/verified/failed/unverifiable），全量 content `99/57/8`、conformance `80/74/10`、evidence `135/26/3`；healthz/readyz、queue depth `0`、failed_recent `0` 通過，未改動 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3724 / keep numeric table value cells out of evidence labels

- `#拆解問題` / `#差距分析`：live `3653.TW/v1` 的 `NT$464 億 | 18%` 不是一個名為 `NT$464 億` 的欄位；原 regex 跨 table cell 配對，將上一格數值當成下一格 label。
- `#偏誤辨識` / `#偏誤降低` / `#可驗證性`：只排除 label 本身已含數字＋貨幣／單位的 table value-cell；正常 `營收 | NT$464 億` 仍可核驗，legacy target、FOMO、新聞價格與真實 mismatch 不放寬。
- `#來源品質` / `#責任`：RED→GREEN focused `1 passed`、完整品質/evidence/conformance `1104 passed`、import `504 passed`、`py_compile`、`git diff --check`、line guard `349` 通過。reload 後 164 份分布維持 content `99/57/8`、conformance `80/74/10`、evidence `135/26/3`；`missing_semantic_path 21→16` 僅反映移除假 table claim，queue depth `0`、failed_recent `0`，未修改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3723 / align evidence credibility warnings with current read-only gates

- `#拆解問題` / `#差距分析`：current evidence projection 已是 `approved`，但 recorded content credibility 仍可能殘留 `non_approved_evidence_gate`；問題在 merge 的 stale issue 邊界，而不是 evidence gate 本身失敗。
- `#來源品質` / `#可驗證性` / `#偏誤降低`：warning 只加入 compact claim counts 與 unverifiable reason counts，不複製 sampled claim 原文；只有 current alignment passed 且 evidence approved 才 suppress 三個 evidence-alignment issue，caution／rejected 不被隱藏。
- `#責任`：RED→GREEN focused content `6 passed`、projection `10 passed`、完整品質/evidence/conformance `1103 passed`、import `504 passed`、docs `136 passed`、`py_compile`、`git diff --check` 通過。reload 後 live 全量 `164` 份為 content `99/57/8`、conformance `80/74/10`、evidence `135/26/3`；`non_approved_evidence_gate` `36→29`，`1102.TW/v4` 的 approved projection 不再帶 stale issue，remaining caution 保留摘要。healthz/readyz `ok/ready`、queue depth `0`、failed_recent `0`，未修改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3722 / explain legacy conclusions without persisted canonical context

- `#拆解問題` / `#差距分析` / `#來源品質`：live `v1/v2/v3` legacy snapshot 的短／中／長期目標與長期潛力數字仍存在 Markdown，但 `rerun_context.parsed`、`structured_outputs` 都是空值；它們不是可以借用同值數字的 canonical evidence，也不應和一般 mapping 缺口混在一起。
- `#偏誤辨識` / `#偏誤降低` / `#可驗證性`：新增 `legacy_conclusion_without_snapshot_path`，只在明確結論 label、空 legacy context 且沒有 canonical path 時使用；status 仍為 `unverifiable`，不讀 persisted `content_credibility`／`report_conformance` 當來源，不改 verdict、抽樣、snapshot、artifact 或 queue。parsed context 存在的反例仍維持 `missing_semantic_path`。
- `#責任`：先取得 RED 再 GREEN；focused evidence `106 passed`、品質/evidence/conformance `1100 passed`、import `504 passed`、docs `136 passed`、line guard `349`、`py_compile` 通過。正式 reload 後全量 `164` 份 quality 為 content `92/64/8`、conformance `80/74/10`、evidence `135/26/3`；read-only 全量 projection reason 為 `legacy_conclusion_without_snapshot_path=28`、`missing_semantic_path=21`、`news_source_not_canonical=2`、`no_matching_snapshot_path=69`。healthz/readyz `ok/ready`、queue depth `0`、failed_recent `0`，未修改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3721 / bind legacy River Chart band prices to valuation bands

- `#來源品質` / `#語意含義` / `#可驗證性`：`2308.TW/v2` 的 `P/E 河流圖 2025 年最高位階（59.6x 區間）：1,379.14 TWD` 是 River Chart band 對應價格，不是 generic `pe_ratio`；snapshot 的 `59.8x` band 價格 `1,383.77` 在既有 1% tolerance 內。
- `#偏誤辨識` / `#偏誤降低`：RED 重現 generic P/E 同值會把 claim 誤判 approved；新增只針對 `P/E 河流圖` + `x` 區間／位階／band + 價格單位的 `pe_river_chart.bands` path，沒有 band series 仍 `unverifiable`，既有精確倍數 band 與 generic PE 反例保留。
- `#責任`：RED→GREEN focused evidence `104 passed`、完整品質/evidence/conformance `1098 passed`、import `504 passed`、docs `136 passed`、`py_compile`、line guard `349` 通過；live `2308.TW/v2` River Chart claim verified，但整份報告仍因其他缺少語意路徑維持 caution。全量 evidence `135/26/3`、conformance `80/74/10`、content `92/64/8`；healthz/readyz、canonical runtime paths、queue depth `0`、failed_recent `0` 通過。不修改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3720 / keep valuation multiples out of trade price candidates

- `#拆解問題` / `#差距分析`：`8438.TW/v4` 的 `28.2x PE band` 與 `18x PE band` 是估值倍數，不是交易目標／支撐價格；原 `price_candidates()` 會把它們混進 `[60.35, 50.0, 38.52]` 的真實上下行情境。
- `#偏誤辨識` / `#偏誤降低` / `#可驗證性`：新增 exact valuation-context guard，只在數字後接 `x/倍` 且後方明示 `PE`、`P/E`、本益比、估值或 band 時移除；沒有明示估值語境的 `28.2x` 反例保留，避免變成廣泛 `x` token suppression。
- `#責任`：RED→GREEN focused input/trade `2 passed`、完整品質/evidence/conformance `1096 passed`、import `504 passed`、docs `136 passed`、`py_compile`、line guard `349`、input helper `99` 通過；source dry-run 與 live projection 都將 8438 候選由 `[60.35, 28.2, 50.0, 38.52, 18.0]` 收斂為 `[60.35, 50.0, 38.52]`，真實多情境 warning 保留。live current quality 為 `164` 份，content `92/64/8`、conformance `80/73/11`、evidence `135/25/4`；healthz/readyz、canonical runtime paths、queue depth `0`、failed_recent `0` 通過。不修改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3719 / exclude percentage tokens and refresh stale issue details

- `#拆解問題` / `#差距分析`：`8039.TW/v4` 的 `回檔逾 10%` 是停損幅度，不是價格；原 parser 會產生 `stop_loss_candidates=[227.0, 10.0]`。即使 current check 已修正，recorded-first merge 還會把舊診斷帶回 API。
- `#偏誤辨識` / `#偏誤降低` / `#可驗證性`：增加 signed decimal/scientific percentage token guard；同一 issue id 合併時改由 current projection 優先，recorded issue 僅補 current 沒有的項目。真正多層停損、target 上下行條件與其他非區間候選不放寬。
- `#責任`：RED→GREEN 品質/evidence/conformance `1094 passed`、import `504 passed`、docs `136 passed`、line guard `349`、input helper `99`、py_compile 通過；live ambiguous 維持 `37`，但 `percent_as_stop_candidate=0`，8039 warning/check details 已無 `10.0`。content `92/64/8`、conformance `80/73/11`、evidence `135/25/4`，healthz/readyz、queue depth `0`、failed_recent `0` 通過；未修改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3718 / separate contextual reference prices from trade scenarios

- `#拆解問題` / `#差距分析`：`46.6 TWD（挑戰 52 週高點 46.63 TWD 壓力位）` 的 46.63 是參考高點，不是第二個目標；`419.15 TWD 至 52 週高點 460.0 TWD` 則是明示兩端區間，兩者都不應被同一個多情境 warning 誤處理。
- `#偏誤辨識` / `#偏誤降低` / `#可驗證性`：新增獨立 price-context helper，只在括號內且明示高低點／壓力支撐時移除參考價，並以 52 週標籤辨識 contextual range；真正的「上看 120」、無括號上下行雙價與其他候選仍保留。
- `#責任`：RED→GREEN focused context/trade `4 passed`、內容可信度輸入／trade/projection `102 passed`、品質/evidence/conformance `1091 passed`、import `504 passed`、evidence `102 passed`、input helper `99`、line guard `349`、py_compile 通過。live ambiguous `51→37`，content `92/64/8`、conformance `80/73/11`、evidence `135/25/4`；未修改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3717 / recognize unit-annotated explicit price ranges

- `#拆解問題` / `#差距分析`：`反彈目標 121.0 TWD 至 130.5 TWD` 的兩個數字由 `至` 明確連成價格區間，不應與多個獨立情境價混為一談。
- `#偏誤辨識` / `#偏誤降低` / `#可驗證性`：RED 重現幣別單位讓區間 regex 漏判；新增兩端附近的 `NT$`、`$`、`TWD`、`元` 支援，並保留非區間多候選 warning，避免以寬鬆 parsing 放過真正歧義。
- `#責任`：RED→GREEN focused trade-setup/projection `13 passed`、品質/evidence/conformance `1087 passed`、import `504 passed`、docs `136 passed`、line guard `349`、py_compile 通過。正式 reload 後 live `ambiguous_trade_setup_price_inputs` 由 `64` 降為 `51`，`2303.TW/v4` 的 stale warning 已移除；content 為 `79 passed / 77 warning / 8 blocked`、evidence 為 `135 approved / 25 caution / 4 rejected`。未修改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3716 / explain non-canonical news evidence

- `#拆解問題` / `#差距分析` / `#來源品質`：D3715 的 source guard 已正確保留新聞價格人工確認，但 `missing_semantic_path` 無法告訴操作員這是來源邊界而非欄位遺漏。
- `#偏誤辨識` / `#可驗證性` / `#表達`：新增 `news_source_not_canonical` reason code；只在新聞／催化劑價格沒有 canonical path 時使用，52 週高低點與 River Chart 的 verified path 不受影響。
- `#責任`：RED→GREEN focused evidence `102 passed`、品質/evidence/conformance `1085 passed`、import `504 passed`、line guard `349`、py_compile 通過。live reason 分布為 `no_matching_snapshot_path=69`、`missing_semantic_path=49`、`news_source_not_canonical=2`，verdict 與 queue 不變，未修改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3715 / keep news prices out of canonical risk fields

- `#拆解問題` / `#差距分析` / `#來源品質`：`8438.TW/v4` 的 `55.8 TWD` 與 `2491.TW/v4` 的 `31.75 TWD` 都明示來自新聞／`market_catalysts`，不能因 snapshot 恰有同值就證明它們是 canonical `risk_price`。
- `#偏誤辨識` / `#偏誤降低` / `#可驗證性`：RED regression 複現「新聞支撐／壓力值被 risk_price verified」；新增只針對新聞來源與支撐／壓力／關卡／風險語意的 source guard，52 週高低點與 River Chart 專用 mapping 保留。
- `#責任`：RED→GREEN focused evidence `102 passed`、品質/evidence/conformance `1085 passed`、import `504 passed`、line guard `349`、py_compile 通過。正式 reload 後全量 `135 approved / 25 caution / 4 rejected`，sampled `433 verified / 120 unverifiable / 11 mismatch`；三筆 v4 新聞價格均維持 `unverifiable`，未修改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3714 / exclude compact month-day metadata claims

- `#拆解問題` / `#差距分析` / `#來源品質`：live `1102.TW/v4` 的 `08/17法說會後` 被誤判成 `8.0`，污染「核心催化劑」的 evidence sample；這是日期 metadata，不是投資數值。
- `#偏誤辨識` / `#偏誤降低` / `#可驗證性`：補上月日 token 緊接中文文字的 RED regression，並以 `(?!\d)` 保留第三位數字防線；`08/17 - 08/18`、完整日期、真正帶單位的值仍維持原解析邊界。
- `#責任`：RED→GREEN focused evidence `101 passed`、品質/evidence/conformance `1084 passed`、import `504 passed`、line guard `349`、py_compile 通過。正式 reload 後 `1102.TW/v4` 為 `approved`；全量 evidence 為 `135 approved / 25 caution / 4 rejected`、`433 verified / 120 unverifiable / 11 mismatch`，未修改 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3713 / preserve semantic boundary for same-value candidates

- `#拆解問題` / `#差距分析` / `#來源品質`：live `no_matching_snapshot_path=71` 中，數值相同的候選多落在歷史價格、新聞/URL、日期 metadata、SLA 或已渲染分析文字；數值相同不等於同一 claim source。
- `#偏誤辨識` / `#偏誤降低` / `#可驗證性`：新增 `熊市情境` 對 `price_history_ranges` 的反例測試，確保情境目標沒有 canonical target path 時仍是 `unverifiable`，不因最近數字而通過。
- `#責任`：RED→GREEN focused evidence `100 passed`、品質/evidence/conformance `1083 passed`、line guard `349`、py_compile 通過；本輪只增加 regression evidence，不改 verdict、snapshot、artifact、index、review 或 queue。

## D3712 / bind PE River band to multiple-specific path

- `#拆解問題` / `#問對問題` / `#語意含義`：`2367.TW/v2` 的 `43.2x（中高分位帶）：29.38 TWD` 是特定倍數下的 band value，不是任意 P/E 或 River Chart multiples 值；若只按數值找最近 band，可能跨 band 誤配。
- `#最小變更` / `#偏誤降低` / `#責任`：從 raw claim 保留 `43.2x` 身份，建立 `pe_river_chart.bands.43.2x` path marker；multiples、其他 band 與 generic P/E 同值均維持不可互借。
- `#可驗證性` / `#來源品質`：RED→GREEN 覆蓋 exact band 正例與 multiples/generic P/E 反例；focused evidence `99 passed`、品質/evidence/conformance `1082 passed`、import `504 passed`、HCS/docs `136 passed`、line guard `349`、py_compile 通過。正式 reload 後 target 命中 `data.pe_river_chart.bands.43.2x[4]`，diff `0.0%`、`verified`；全量 164 份為 evidence `134 approved / 26 caution / 4 rejected`，`missing_semantic_path=50`，其他 mismatch 與人工確認邊界保留。

## D3711 / bind Operating Cash Flow to dedicated field

- `#拆解問題` / `#問對問題` / `#語意含義`：`1623.TW/v3` 的 `Operating Cash Flow: -0.1898B` 是營業現金流，不是 `Free Cash Flow`；snapshot 同時提供兩個不同欄位，不能因數值或 B 單位相似而跨欄位核驗。
- `#最小變更` / `#偏誤降低` / `#責任`：新增 `operating cash flow -> operating_cash_flow` exact hint，放在 FCF hint 前；只有同語意 path 可用，raw-only 或只有 FCF 時不自動借用。
- `#可驗證性` / `#來源品質`：RED→GREEN 覆蓋 dedicated snapshot 正例與 FCF 反例；focused evidence `97 passed`、品質/evidence/conformance `1080 passed`、import `504 passed`、line guard `349`、py_compile 通過。正式 reload 後 target claim 命中 `data.operating_cash_flow`，diff `0.1054%`、`verified`；全量 163 份為 evidence `134 approved / 25 caution / 4 rejected`，`missing_semantic_path=50`，既有 mismatch、衍生分數與人工確認邊界保留。

## D3710 / bind PE River Chart to dedicated multiples path

- `#拆解問題` / `#問對問題` / `#語意含義`：`3653.TW/v3` 的 River Chart 分位數是獨立 valuation source，不能因數值看起來像 P/E 就直接借用 `data.pe_ratio`。
- `#最小變更` / `#偏誤降低` / `#責任`：新增 `river chart -> pe_river_chart.multiples` 專用 hint，置於泛用 P/E hint 前；snapshot 無專用欄位或只有 generic P/E 時仍維持人工確認。
- `#可驗證性` / `#來源品質`：RED→GREEN 覆蓋專用 snapshot 正例與 generic P/E 同值反例；focused evidence `95 passed`、品質/evidence/conformance `1078 passed`、import `504 passed`、HCS/docs `136 passed`、line guard `349`、py_compile 通過。正式 reload 後 162 份為 evidence `133 approved / 25 caution / 4 rejected`，558 筆 sampled claim 為 `425 verified / 122 unverifiable / 11 mismatch`，`missing_semantic_path` 降至 `51`；3653 v3 的 32.5x 命中 `data.pe_river_chart.multiples[0]`，真實 PE mismatch、信心與目標價人工確認仍保留。healthz/readyz 為 `ready`，watchlist 既有任務持續由 worker 處理且 `failed_recent=0`；沒有清除、重試或刪除 queue。

## D3709 / exclude cutoff metadata clock minutes

- `#拆解問題` / `#問對問題` / `#語意含義`：`market_data (截至 2026-08-19 07:50)` 的分鐘 `50` 被誤認為 scalar claim，造成資料 metadata 與投資數字混淆。
- `#最小變更` / `#偏誤降低` / `#責任`：只在 metadata label、數字前緊接 `HH:` 且符合資料時間語意時略過分鐘 match；不把所有時間或一般 `HH:MM` 文字一律當非 claim，不改 canonical matching。
- `#可驗證性` / `#來源品質`：RED→GREEN 覆蓋 plain cutoff clock fixture，既有 ISO timestamp、日期範圍與數值 evidence 回歸保持通過；focused evidence `93 passed`、line guard `349`、py_compile 通過。

## D3708 / exclude month-day range prefixes from scalar claims

- `#拆解問題` / `#問對問題` / `#語意含義`：`3037.TW/v4` 的法人敘述以 `08/17 - 08/18` 開頭，generic KV parser 把第一個 `08` 當成法人數字；這是日期前綴誤抽取，不是缺少法人 canonical path 的資料問題。
- `#最小變更` / `#偏誤降低` / `#責任`：只擴充既有 `_SHORT_DATE_SUFFIX_RE`，在 label 後接月日且後續為範圍 dash、文字或行尾時略過該 match；不建立 aggregate 推測、不借用每日資料、不改其他 unit 或 semantic mapping。
- `#可驗證性` / `#來源品質`：RED→GREEN 覆蓋 `08/17 - 08/18` 反例與既有日期/價格測試；focused evidence `92 passed`、line guard `349`、py_compile 通過，3037 live Markdown+snapshot 不再產生 `8` claim。

## D3707 / explain evidence gate unverifiable reasons

- `#拆解問題` / `#問對問題` / `#語意含義`：全量 current evidence 仍有大量人工確認 claim，但單一 `unverifiable` 狀態無法直接分辨「沒有安全語意路徑」與「有語意但 snapshot 沒有對應資料」，降低修復優先順序的可判讀性。
- `#最小變更` / `#偏誤降低` / `#責任`：只在 read-only sampled claim 增加 `verification_reason_code`、`candidate_count`，並在 gate 摘要增加 `unverifiable_reason_counts`；不改 semantic matching、tolerance、抽樣、verdict 或 persisted state。
- `#可驗證性` / `#來源品質`：RED→GREEN 覆蓋 verified、mismatch、missing semantic path 與 no matching snapshot path；focused evidence gate `91 passed`、`evidence_exit_gate.py=349`、`py_compile` 通過。操作手冊與架構圖同步寫明衍生評分、新聞價格、跨 provider 值仍不得借用最近數字。

## D3706 / split secondary source-anchored price claims

- `#拆解問題` / `#問對問題` / `#語意含義`：同一個 `近期支撐` 行可能同時寫心理關卡、新聞價格與歷史收盤平台；只抽第一個數字會遮住可驗證來源，也可能讓整行被錯誤視為單一證據。
- `#最小變更` / `#偏誤降低` / `#責任`：只對支撐／壓力／高點／低點 label 且第二筆數字後有 `price_history`、月份收盤或月底高低點錨點時建立「次要價位」claim；month-end matcher 要求月份標記前最近數字等於該 claim，第一筆與新聞上下文不跨配。
- `#可驗證性` / `#來源品質`：RED→GREEN fixture 覆蓋 `3653` 兩筆支撐、`2491` 新聞價＋月底低點；dry-run 全量 162 份只增加 `3653`／`2491` 各 1 個 claim，整體 evidence 分布不變，`3653` 次要價位 verified。
- `#可驗證性` / `#責任`：evidence gate `90 passed`、品質/evidence/conformance `1073 passed`、import boundary `504 passed`、HCS/docs `136 passed`、line guard `evidence_exit_gate.py=349`；正式 reload 後 `3653.TW/v4` 為 `19 claims / 3 sampled / 1 unverifiable / caution`，3445 次要價位 verified、5000 第一筆保留人工確認；`2491.TW/v4` 為 `18 claims / 3 sampled / 1 unverifiable / caution`，新聞價未交叉配對；healthz/readyz、queue depth `0` 與 failed_recent `0` 通過，未寫入 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3705 / bind unique yearless month-end support to price history

- `#問對問題` / `#拆解問題` / `#語意含義`：`3406.TW/v4` 的 `7 月底低點` 是「月底資料點」而非泛稱月內最低價；要先確認 snapshot 是否只有一個可推定年份，不能用報告生成時間直接補年。
- `#最小變更` / `#限制條件` / `#責任`：flatten 新增 `price_history[month-end=YYYY-MM]`，claim 只在明示月底／月末、支撐／壓力／高點／低點，且該月份年份唯一時映射；原逐日與 `month=YYYY-MM` 極值 paths 不改，新聞來源與跨年份歧義拒絕自動映射。
- `#偏誤降低` / `#演繹` / `#可驗證性`：RED→GREEN fixture 覆蓋唯一年份正例、跨年份歧義、exact-path mismatch 與月底新聞反例；以 `3406` snapshot dry-run 證實 481.0 命中 `data.price_history[month-end=2026-07]`，其他 161 份報告 verdict 不變。
- `#可驗證性` / `#責任`：evidence gate `88 passed`、品質/evidence/conformance `1071 passed`、import boundary `504 passed`、HCS/docs `136 passed`、line guard `evidence_exit_gate.py=349`；正式 reload 後 `3406.TW/v4` 為 `10 claims / 3 sampled / 0 unverifiable / approved`，month-end target verified；`8438.TW/v4` 的新聞壓力仍為 caution，全量 evidence 為 `132/23/7`，healthz/readyz、queue depth `0` 與 failed_recent `0` 通過，未寫入 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3704 / bind month-level support and pressure to price-history extrema

- `#拆解問題` / `#差距分析` / `#語意含義`：`7711.TW/v4` 的 292.5 是 2026 年 7 月月內低點，`2491.TW/v4` 的 40.15 是 2026 年 6 月月內高點；snapshot 只保存逐日 `price_history`，原 parser 沒有月份極值的 canonical marker。
- `#最小變更` / `#責任`：flatten 時保留既有逐日 paths，另以 `month=YYYY-MM` 建立同月 `low`／`high` synthetic paths；只有 claim 明示年月且帶支撐／壓力／高點／低點語意時才映射，不以同月份任意數字猜測。
- `#偏誤降低` / `#可驗證性`：RED→GREEN fixture 覆蓋月低支撐正例、月低數值 mismatch、月高壓力正例；逐日日期、52 週、新聞壓力與錯月份反例維持保守邊界。
- `#可驗證性` / `#責任`：evidence gate `84 passed`、品質/evidence/conformance `1067 passed`、import boundary `504 passed`、HCS/docs `136 passed`、line guard `evidence_exit_gate.py=349`；正式 reload 後 `7711.TW/v4` 為 `16 claims / 3 sampled / 0 unverifiable / approved` 且月低 target verified，`2491.TW/v4` 的月高 target verified 但整份維持 `1 unverifiable / caution`；healthz/readyz、canonical storage、queue depth `0` 與 failed_recent `0` 通過，未寫入 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3703 / map explicit 52-week-high pressure variants

- `#拆解問題` / `#差距分析` / `#語意含義`：`6715.TW/v4` 與 `2903.TW/v4` 都把壓力位明確說成 52 週最高價，但 label 分別是 `關鍵壓力`／`關鍵壓力位`，原規則未能穩定綁定 `data.week_52_high`。
- `#最小變更` / `#責任`：只對兩個 exact labels 且 raw text 明示 `52週最高價` 或 `Week 52 High` 時回傳 `week_52_high`；plain pressure 沒有 52 週語境時不套用。
- `#偏誤降低` / `#可驗證性`：RED→GREEN fixture 覆蓋 6715-like、2903-like 正例與 plain-pressure 反例；正式 reload 後 `6715` 為 `14 claims / 3 sampled / 0 unverifiable / approved`、`2903` 為 `13 claims / 3 sampled / 0 unverifiable / approved`，兩筆均命中 `data.week_52_high`。
- `#可驗證性` / `#責任`：evidence gate `81 passed`、品質/evidence/conformance `1064 passed`、import boundary `504 passed`、HCS/docs `136 passed`，line guard `evidence_exit_gate.py=349`；既有 mismatch、新聞價格、人工信心/衍生評分邊界均保留，healthz/readyz、canonical paths 與 RQ failed_recent `0` 通過。

## D3702 / bind daily institutional values to exact dates

- `#拆解問題` / `#差距分析` / `#語意含義`：`1402.TW/v4` 的 daily institutional section 明示 `Last 10 trading days daily total net buy`，每筆 `Aug NN` 都對應 snapshot 的 date/value object；原 evidence gate 沒保留日期 identity。
- `#最小變更` / `#責任`：只對具備序列標題、年份與月份日期 label 的 claim 建立 exact `daily_total_net_buy_last_10[YYYY-MM-DD].net_buy_thousand_shares` path；不把同值跨日期配對，也不替 standalone month-day claim 猜來源。
- `#偏誤降低` / `#可驗證性`：RED→GREEN fixture 覆蓋正確日期、錯日期 mismatch 與無上下文 unverifiable；正式 reload 後 API 直接重驗 `1402_TW_v4_report_job_521d42345300.html` 為 `34 claims / 6 sampled / 0 unverifiable / approved`，日期列均命中 date-specific path。
- `#可驗證性` / `#責任`：evidence gate `78 passed`、品質/evidence/conformance `1061 passed`、import boundary `504 passed`、HCS/docs `136 passed`，line guard `evidence_exit_gate.py=349`；既有四捨五入 tolerance、人工信心/衍生評分邊界與原始資料均保留，healthz/readyz、canonical paths 與 RQ failed_recent `0` 通過。

## D3701 / exclude institutional lookback metadata from scalar claims

- `#拆解問題` / `#差距分析` / `#語意含義`：`6141.TW/v4` 的 `` `institutional_trading`: 30-day lookback, latest date ... `` 中 `30` 只表示資料回溯期間；它不是淨買超、持股或任何 snapshot scalar。
- `#最小變更` / `#責任`：只在 backtick `institutional_trading` 後接 `N-day lookback` 的完整句型排除數字；未加入廣泛的 `institutional_trading` label marker，保留真正帶值的 institutional trading claim。
- `#偏誤降低` / `#可驗證性`：RED→GREEN fixture 同時驗證 metadata 不產生 claim、`institutional_trading: 30.0k` 仍可抽取；live `6141.TW/v4` 收斂為 `15 claims / 3 sampled / 0 unverifiable / approved`。
- `#可驗證性` / `#責任`：evidence gate `75 passed`、品質/evidence/conformance `1058 passed`、import boundary `504 passed`、HCS/docs `136 passed`，line guard `evidence_exit_gate.py=349`；healthz/readyz、canonical paths 與 RQ failed_recent `0` 通過。未寫入 artifact、snapshot、index、review、rerun、repair 或 queue。

## D3700 / bind dated extremum inside a mixed pressure sentence

- `#拆解問題` / `#差距分析` / `#語意含義`：`2455.TW/v4` 把 `2026-05-29 高點` 與 `52 週高點` 放在同一個「近期壓力位」句子；第一個值是有日期的歷史極值，第二個值是另一個 canonical field，原本兩者都因 label 不夠具體而無法完整核驗。
- `#最小變更` / `#責任`：只在 claim text 中偵測日期緊接 `高點`／`低點` 的 inline extremum，產生 exact `price_history[YYYY-MM-DD]` marker；排除 52 週 label，並在 `market_catalysts`／新聞語境下保留人工確認，不改 raw report、snapshot 或 persisted gate。
- `#偏誤降低` / `#可驗證性`：RED→GREEN fixture 覆蓋 2455-like mixed pressure 正例與 dated-news pressure 反例；live `2455.TW/v4` target claim verified，matched path 為 `data.price_history[2026-05-29].prices[8]`，`8438.TW/v4` 的 55.8 新聞價格仍為 unverifiable。
- `#可驗證性` / `#責任`：evidence gate `74 passed`、品質/evidence/conformance `1057 passed`、import boundary `504 passed`、HCS/docs `136 passed`，line guard `evidence_exit_gate.py=349`；healthz/readyz、doctor canonical paths 與 RQ failed_recent `0` 通過。其餘 content credibility、交易計畫多情境目標與人工核對邊界保留，未寫入 artifact、snapshot、index、review、rerun、repair 或 queue。

## D3699 / exclude catalyst-group period tokens from scalar claims

- `#拆解問題` / `#差距分析` / `#語意含義`：`3055.TW/v4` 的 `Recent catalysts: 5-day jump ...` 是新聞群組標題，不是單一資料欄位；generic KV parser 卻先抓到 `5`，讓 evidence sample 多出一筆無 canonical path 的 unverifiable claim。
- `#最小變更` / `#責任`：只將完整 `Recent catalysts`／`近期催化劑` labels 加入 non-claim markers；`data.recent_catalysts` 仍是新聞陣列，32.16%／84.05% 不使用最近數字或跨來源 fallback。
- `#偏誤降低` / `#可驗證性`：RED→GREEN fixture 同時覆蓋英文與中文的 5-day／5 日期間 token；live `3055.TW/v4` 收斂為 `16 claims / 3 sampled / 0 unverifiable / approved`，其餘資料信心與 dated pressure/support 維持人工確認。
- `#可驗證性` / `#責任`：focused evidence `73 passed`、品質/evidence/conformance `1055 passed`、import boundary `504 passed`、HCS/docs `136 passed`，line guard `evidence_exit_gate.py=349`；正式 reload 後 target filtered current summary `1 audited / 1 approved`，full current summary `165` 份為 evidence `136/23/6`、content `76/81/8`、conformance `71/81/13`；healthz/readyz、doctor canonical paths 與 RQ failed_recent `0` 通過，未寫入本輪程式修正以外的 artifact、snapshot、index、review、rerun、repair 或 queue。

## D3698 / bind dated high-point evidence to price history

- `#拆解問題` / `#差距分析` / `#語意含義`：`6226.TW/v4` 的「近期高點：22.05 (2026-06-30)」是日期和值的明確歷史極值，但沒有 `收盤價`、單位或欄位路徑，原 matcher 無法把它連到 `data.price_history`。
- `#最小變更` / `#責任`：只對有日期的高／低點 label 產生 exact `price_history[YYYY-MM-DD]` marker；排除 `52 週` 與 `market_catalysts`／新聞來源，保留同值錯日期的 mismatch，不使用最近數字 fallback。
- `#偏誤降低` / `#可驗證性`：RED→GREEN fixture 覆蓋日期正確、同值錯日期與新聞高點反例；正式 live `6226.TW/v4` target claim verified，matched path 為 `data.price_history[2026-06-30].prices[10]`，同報告既有交易計畫多情境價格警示仍保留。
- `#可驗證性` / `#責任`：evidence gate `72 passed`、品質/evidence/conformance `1054 passed`、import boundary `504 passed`、HCS/docs `136 passed`，line guard `evidence_exit_gate.py=349`。正式 reload 後 target filtered current summary `1 audited / 1 approved`；full current summary `165` 份為 evidence `135/24/6`、content `79/78/8`、conformance `74/78/13`；healthz/readyz、doctor canonical paths、RQ queue depth `0` 與 failed_recent `0` 通過，未寫入 artifact、snapshot、index、review、rerun、repair 或 queue。

## D3697 / exclude daily-trend date tokens from scalar evidence claims

- `#拆解問題` / `#差距分析` / `#語意含義`：`近 10 日每日趨勢` 是一行日期／數值序列，generic KV parser 卻把 `7/21` 的月份 `7` 當成 label value，造成一筆假性的 unverifiable claim。
- `#最小變更` / `#責任`：只把 exact sequence labels `近 10 日每日趨勢`、`daily trend` 加入 non-claim markers；不把 `daily_total_net_buy_last_10` 的部分文字重述當成完整 series verification，也不影響其他 scalar institutional claims。
- `#偏誤降低` / `#可驗證性`：RED→GREEN fixture 確認日期 token 不再生成 claim；live `6226.TW/v4` 不再出現這筆 sampled claim，report 仍保留其他品質警示，沒有被錯誤升級。
- `#可驗證性` / `#責任`：evidence gate `69 passed`、品質/evidence/conformance `1052 passed`、import boundary `504 passed`、HCS/docs `136 passed`，line guard `evidence_exit_gate.py=349`。正式 reload 後 live `165` 份為 evidence `135/24/6`、claims `434 verified / 138 unverifiable / 8 mismatch`、content `80/77/8`、conformance `75/77/13`；healthz/readyz、doctor canonical paths、RQ queue depth `0` 與 failed_recent `0` 通過，未寫入 artifact、snapshot、index、review、rerun、repair 或 queue。

## D3696 / convert borrowed-return raw shares to report lots

- `#拆解問題` / `#差距分析` / `#來源品質`：`6226.TW/v4` 報告寫 `當日借券還券：0 張`，但 TWSE TWT93U provider 解析出的 `borrowed_short_return_today` 是 raw shares；直接 path mapping 會把不同單位當成同一數字。
- `#最小變更` / `#責任`：只對 exact `當日借券還券` 且 claim unit 為 `張` 啟用 `raw shares / 1000` 的 view-time candidate conversion；不改 snapshot schema、不影響 `borrowed_short_sale_balance` 的既有 shares claim，也不把其他借券欄位泛化。
- `#偏誤降低` / `#可驗證性`：RED→GREEN 三個 fixture 鎖定 40 張→40,000 shares、錯單位 40,000 張必須 mismatch、0 張可驗證；live target verified，但同報告另一筆近 10 日趨勢仍 unverifiable，整份 report 沒有被升級。
- `#可驗證性` / `#責任`：evidence gate `68 passed`、品質/evidence/conformance `1051 passed`、import boundary `504 passed`、HCS/docs `136 passed`，line guard `evidence_exit_gate.py=349`。正式 reload 後 live `165` 份為 evidence `135/24/6`、claims `434 verified / 138 unverifiable / 8 mismatch`、content `80/77/8`、conformance `75/77/13`；healthz/readyz、doctor canonical paths、RQ queue depth `0` 與 failed_recent `0` 通過，未寫入 artifact、snapshot、index、review、rerun、repair 或 queue。

## D3695 / map named global-market latest values by symbol

- `#拆解問題` / `#差距分析` / `#語意含義`：`Taiwan Weighted Index`、`USD/TWD`、`WTI Crude Oil` 都是 global market snapshot 的明確 label，但原 parser 沒有把 latest value 與 `^TWII`、`TWD=X`、`CL=F` 的 symbol identity 綁定，舊報告數字因此無法區分「可驗證」與「已漂移」。
- `#最小變更` / `#責任`：只新增三個 exact label mapping 到 `global_market_context.items[twii/twdx/clf].latest`，保留 `WTI` bare alias 不自動推測；snapshot 的 symbol path 仍由既有 flatten logic 提供。
- `#偏誤降低` / `#可驗證性`：RED→GREEN 三個 fixture 覆蓋同值 verified、同 symbol 錯值 mismatch、EWT 同值不可交叉命中，以及 bare WTI 反例；live `USD/TWD` 在 tolerance 內 verified，Taiwan Index/WTI 舊值轉為 mismatch，既有人工審核邊界保留。
- `#可驗證性` / `#責任`：evidence gate `65 passed`、品質/evidence/conformance `1048 passed`、import boundary `504 passed`、HCS/docs `136 passed`，line guard `evidence_exit_gate.py=349`。正式 reload 後 live `165` 份為 evidence `135/24/6`、claims `433 verified / 139 unverifiable / 8 mismatch`、content `80/77/8`、conformance `75/77/13`；healthz/readyz、doctor canonical paths、RQ queue depth `0` 與 failed_recent `0` 通過，未寫入 artifact、snapshot、index、review、rerun、repair 或 queue。

## D3694 / map paired English 52-week-low evidence

- `#拆解問題` / `#差距分析` / `#語意含義`：`2885.TW/v4` 的 `52-week high: 72.3 / low: 31.7476` 被拆成 `week high` 與 bare `low`；snapshot 有 `data.week_52_low=31.747572`，但單獨 `low` 沒有足夠語意保證。
- `#最小變更` / `#責任`：只在同一 raw claim 明示 `52-week high ... / low ...` 時把 `low` 綁到 `data.week_52_low`；獨立 `low` fixture 保持 unverifiable，不使用最近數字或其他低點欄位 fallback。
- `#偏誤降低` / `#可驗證性`：RED→GREEN 兩個 fixture 鎖定 paired 正例與 bare-label 反例；live reload 後 `2885.TW/v4` low verified，matched path 正確，既有 6 個 mismatch、confidence/情境/派生 claim 的人工覆核邊界不變。`6226` 借券還券因 raw shares 對報告張數的單位差異仍保留人工確認。
- `#可驗證性` / `#責任`：evidence gate `62 passed`、品質/evidence/conformance `1045 passed`、import boundary `504 passed`、HCS/docs `136 passed`，line guard `evidence_exit_gate.py=349`。正式 reload 後 live `165` 份為 evidence `135/26/4`、claims `432 verified / 142 unverifiable / 6 mismatch`、content `80/77/8`、conformance `75/79/11`；healthz/readyz、doctor canonical paths、RQ queue depth `0` 與 failed_recent `0` 通過，未寫入 artifact、snapshot、index、review、rerun、repair 或 queue。

## D3693 / map English weekly-high and annual-growth labels

- `#拆解問題` / `#差距分析` / `#語意含義`：`4989.TW/v4` 的 `52 Week High: 125.0` 有 `data.week_52_high`，`2308.TW/v1` 的 `Net Income Growth (Latest Annual): 70.6%` 有 `data.latest_annual_net_income_growth`；原 parser 沒有對應英文 label hint。
- `#最小變更` / `#責任`：新增 `weekhigh/weeklow` → `week_52_high/week_52_low`，以及 `incomegrowthlatestannual` → `latest_annual_net_income_growth`；不把 Week High 對到 Week Low，也不把 generic `earnings_growth` 當成年度淨利成長證據。
- `#偏誤降低` / `#可驗證性`：RED→GREEN 四個 fixture 鎖定兩個正例與兩個跨欄位反例；正式 reload 後兩筆 live claim 均 verified，既有 6 個 mismatch、confidence/情境/派生 claim 的人工覆核邊界不變。
- `#可驗證性` / `#責任`：evidence gate `60 passed`、品質/evidence/conformance `1043 passed`、import boundary `504 passed`、HCS/docs `136 passed`，line guard `evidence_exit_gate.py=349`。正式 reload 後 live `165` 份為 evidence `134/27/4`、claims `431 verified / 143 unverifiable / 6 mismatch`、content `79/78/8`、conformance `74/80/11`；healthz/readyz、doctor canonical paths、RQ queue depth `0` 通過，未寫入 artifact、snapshot、index、review、rerun、repair 或 queue。

## D3692 / map explicit institutional natural-language labels

- `#拆解問題` / `#差距分析` / `#語意含義`：`2885.TW/v4` 的 `Dealer: 22,401.41` 與 `6505.TW/v4` 的 `Total Net Buy (30 days): 118,065.81k` 都有 snapshot canonical source，但原 parser 只接受明示 field path 或五日淨買進 label。
- `#最小變更` / `#責任`：新增 exact `Dealer`／`自營商` → `institutional_trading.net_buy_thousand_shares_by_category.dealer`，以及 `Total Net Buy (30 days)` → `institutional_trading.total_net_buy_thousand_shares`；Dealer 對 total path 的反例保持 unverifiable，不做跨欄位 fallback。
- `#偏誤降低` / `#可驗證性`：RED→GREEN 三個 fixture 鎖定兩個正例與一個跨欄位反例；正式 reload 後兩筆 live claim 均 verified，既有 6 個 mismatch、confidence/情境/派生 claim 的人工覆核邊界不變。
- `#可驗證性` / `#責任`：evidence gate `56 passed`、品質/evidence/conformance `1039 passed`、import boundary `504 passed`、HCS/docs `136 passed`，line guard `evidence_exit_gate.py=349`。正式 reload 後 live `165` 份為 evidence `133/28/4`、claims `429 verified / 145 unverifiable / 6 mismatch`、content `79/78/8`、conformance `74/80/11`；healthz/readyz、doctor canonical paths、RQ queue depth `0` 通過，未寫入 artifact、snapshot、index、review、rerun、repair 或 queue。

## D3691 / use adjacent margin context for latest-balance evidence

- `#拆解問題` / `#差距分析` / `#語意含義`：live `2359.TW/v4` 的「融資餘額變化」在前一行，「最新餘額：9,626 張」在下一行；snapshot 同時有 `data.chip_data.twse_margin_short_sales.margin_balance=9626`，但 claim raw line 沒有保留前文，原規則只能回報 unverifiable。
- `#最小變更` / `#責任`：extractor 只保存最多兩行的局部 context，不改對外 `raw_text`；evidence gate 只在 exact label `最新餘額` 且相鄰 context 明示融資／融券時回指 `margin_balance`／`short_balance`，無上下文反例維持 unverifiable。
- `#偏誤降低` / `#可驗證性`：先以同一行與跨一行 fixture RED，再 GREEN；live 全量重驗 `2359.TW/v4` verified，matched path 為 `data.chip_data.twse_margin_short_sales.margin_balance`。既有 6 個 mismatch、confidence/情境/派生 claim 的人工覆核邊界不變。
- `#可驗證性` / `#責任`：evidence gate `53 passed`、品質/evidence/conformance `1036 passed`、import boundary `504 passed`、HCS/docs `136 passed`，line guard `evidence_exit_gate.py=349`。正式 reload 後 live `165` 份為 evidence `132/29/4`、claims `427 verified / 147 unverifiable / 6 mismatch`、content `79/78/8`、conformance `74/80/11`；healthz/readyz、doctor canonical paths、RQ queue depth `0` 通過，未寫入 artifact、snapshot、index、review、rerun、repair 或 queue。

## D3690 / map v4 weekly targets to their explicit trade-setup path

- `#拆解問題` / `#差距分析` / `#語意含義`：live current scope 的 9 筆 `週目標` 全是 v4，報告值與 `rerun_context.structured_outputs.24.target_price`、`rerun_context.parsed.trade_setup.target_price` 一對一相符；原本 parser 沒有 `週目標` hint，只能回報 unverifiable。
- `#最小變更` / `#責任`：只新增 `週目標` → `parsed.trade_setup.target_price` / `structured_outputs.24.target_price` path；不把期間或情境文字泛化成 target，不消費 `content_credibility.checks[*].details.target_price` 這類重述欄位。
- `#偏誤降低` / `#可驗證性`：新增 v4 target path fixture；live 逐一重驗 9 筆，全部 verified。3 個月/6 個月/12 個月目標、熊/基本/牛市情境、信心與護城河分數仍保留人工確認，既有 6 個真實 mismatch 不變。
- `#可驗證性` / `#責任`：evidence gate `50 passed`、品質/evidence/conformance `1033 passed`、import boundary `504 passed`、HCS/docs `136 passed`，line guard `evidence_exit_gate.py=349`。正式 reload 後 live `165` 份為 evidence `131/30/4`、claims `426 verified / 148 unverifiable / 6 mismatch`、content `79/78/8`、conformance `74/80/11`；healthz/readyz、doctor canonical paths、RQ queue depth `0` 通過，未寫入 artifact、snapshot、index、review、rerun、repair 或 queue。

## D3689 / bind current-price and 52-week-high labels to canonical fields

- `#拆解問題` / `#差距分析` / `#語意含義`：`8422.TW/v4` 的 `當前價位` 有 `market_data.current_price_twd` 明示來源；`2357.TW/v4` 與 `2834.TW/v4` 的壓力位分別寫明 `52 週最高價`，數值又與 snapshot 的 `current_price`/`week_52_high` 一致，但 label/path parser 原本將它們留在 unverifiable。
- `#最小變更` / `#責任`：新增 `當前價位` current-price hint，並擴充 52 週 pattern 支援 `最高價`、`此為 52 週最高價` 等固定短句；只有在報告 claim 數字等於對應 snapshot field 時才回傳 canonical path，普通 `market_data`、歷史高點與多數字句子不套用。
- `#偏誤降低` / `#可驗證性`：新增 current-price、52-week-high 與 sentence-connector fixtures；live 三份報告均 verified，既有 cross-number/date leakage、真實 mismatch、confidence/情境人工審核邊界維持。
- `#可驗證性` / `#責任`：evidence gate `49 passed`、品質/evidence/conformance `1032 passed`、import boundary `504 passed`、HCS/docs `136 passed`，line guard `evidence_exit_gate.py=349`。正式 reload 後 live `165` 份為 evidence `122/39/4`、claims `417 verified / 157 unverifiable / 6 mismatch`、content `73/84/8`、conformance `69/85/11`；healthz/readyz、doctor canonical paths、RQ queue depth `0` 通過，未寫入 artifact、snapshot、index、review、rerun、repair 或 queue。

## D3688 / map the exact natural-language five-day net-buy label

- `#拆解問題` / `#差距分析` / `#語意含義`：報告會寫 `Last 5 trading days net buy`，但既有 evidence gate 只接受明示的 `last_5_trading_days_net_buy_thousand_shares` path；`9921.TW/v4` 的 `12,467.35k` 與 `2885.TW/v4` 的 `7,068.03 (thousand shares)` 因而被保守地留在 unverifiable，雖然 snapshot 有唯一同語意欄位。
- `#最小變更` / `#責任`：只把 normalized label `last5tradingdaysnetbuy` 映射到 `institutional_trading.last_5_trading_days_net_buy_thousand_shares`；`Daily total net buy`、30 日 `total_net_buy` 與明示 field path 仍各自走原規則，不使用最近數字或跨序列 fallback。
- `#偏誤降低` / `#可驗證性`：新增自然語言正例與每日淨買進反例；live 直接以 Markdown+snapshot 重驗兩份 historical v4，五日淨買進為 verified，daily label 仍 unverifiable。宏觀報告舊日期值、FOMO/論文健康度與缺乏 canonical path 的派生 claim 沒有被這次規則放寬。
- `#可驗證性` / `#責任`：evidence gate `46 passed`、品質/evidence/conformance `1029 passed`、import boundary `504 passed`、HCS/docs `136 passed`，line guard `evidence_exit_gate.py=349`。正式 reload 後 current latest scope 維持 `165` 份 evidence `119/42/4`、content `70/87/8`、conformance `66/88/11`；healthz/readyz、doctor canonical paths、RQ queue depth `0` 通過，未寫入 artifact、snapshot、index、review、rerun、repair 或 queue。

## D3687 / exclude derived trade-plan health metadata from evidence claims

- `#拆解問題` / `#差距分析` / `#語意含義`：`交易計畫健康度: 6/10` 是報告自身的衍生品質分數，沒有 canonical data snapshot path；把它當來源數字只會增加人工核對 warning，不能證明資料事實。
- `#最小變更` / `#責任`：只加入 `交易計畫健康度` non-claim marker，保留 confidence 的既有 unverifiable boundary，並讓 content credibility/calibration 繼續負責 confidence 可信度，不把 metadata 排除延伸到一般交易價格。
- `#偏誤降低` / `#可驗證性`：新增 derived health score fixture；完整 live reload 後 evidence approved 增加、rejected/blocked 真實問題維持，3653/6282/2308/1623 的 mismatch 仍可見。
- `#可驗證性` / `#責任`：evidence gate `44 passed`、品質/evidence/conformance `1027 passed`、import boundary `504 passed`、HCS/docs `135 passed`，line guard `evidence_exit_gate.py=349`。正式 reload 後 live `165` 份 evidence `119/42/4`、claims `411 verified / 163 unverifiable / 6 mismatch`，content `70/87/8`、conformance `66/88/11`；healthz/readyz、doctor canonical paths、RQ queue depth `0` 通過，未寫入 artifact、snapshot、index、review、rerun、repair 或 queue。

## D3686 / map profitability fields and reject short-date prefixes

- `#拆解問題` / `#差距分析` / `#來源品質`：live caution claim 中 `毛利率`、`殖利率` 分別可在 `data.gross_margin`、`data.dividend_yield` 找到 canonical 值；另一筆 `8/19 融資餘額` 把日期前綴 `8` 當成數字，形成 false mismatch。
- `#最小變更` / `#責任`：只補 `gross_margin`、`gross_margin_raw`、`dividend_yield`、`dividend_yield_raw` hints，加入 `張` 單位，並在月日後接中文、英文或標點時跳過 date prefix；不把 confidence、交易計畫健康度、護城河評分或情境數字映射到任意 snapshot 值。
- `#偏誤降低` / `#可驗證性`：新增正確毛利率／殖利率與 `8/19` 日期 fixture；`3008.TW/v4` false mismatch 消失，`3653.TW/v3` 與其他 4 個真實 mismatch/rejected 保留。
- `#可驗證性` / `#責任`：evidence gate `43 passed`、品質/evidence/conformance `1026 passed`、import boundary `504 passed`、HCS/docs `135 passed`，line guard `evidence_exit_gate.py=349`。正式 reload 後 live `165` 份 evidence `90/71/4`、claims `382 verified / 197 unverifiable / 5 mismatch`，content `53/104/8`、conformance `49/105/11`；healthz/readyz、doctor canonical paths、RQ queue depth `0` 通過，未寫入 artifact、snapshot、index、review、rerun、repair 或 queue。

## D3685 / parse emphasized Markdown evidence against canonical fields

- `#拆解問題` / `#差距分析` / `#語意含義`：報告 Markdown 廣泛使用 `**label:** value`；parser 未消費 emphasis token 時，`3017.TW/v4` 的 current claim count 會是 `0`，把格式漏讀誤判成沒有證據，而 P/B、ROE、Beta 又已有明確 snapshot 欄位可核驗。
- `#最小變更` / `#責任`：`_KV_RE` 與 `_TABLE_CELL_RE` 只允許 separator 後的 `*_\`` token；field hints 只補 `pb_ratio`、`roe`、`beta` 的既有 canonical paths。錯值仍走 mismatch/rejected，不以最近數字或跨語意欄位補證據。
- `#偏誤降低` / `#來源品質`：新增 Markdown emphasis 正確值與錯值 fixtures，確認 3017 v4 的三筆抽樣全數 verified；保留 `3653.TW/v3` rejected/blocked 反例，沒有把不可核驗或真正矛盾降級成 approved。
- `#可驗證性` / `#責任`：evidence gate `41 passed`、品質/evidence/conformance `1024 passed`、import boundary `504 passed`、HCS/docs `135 passed`，line guard `evidence_exit_gate.py=349`。正式 reload 後 current quality `165` 份為 evidence `59/102/4`、content `30/127/8`、conformance `26/128/11`；3017 v4 `10 claims / 3 sampled / 3 verified / 0 unverifiable / approved`，仍有交易價格情境歧義 warning。healthz/readyz、doctor canonical paths、RQ queue depth `0` 通過，未寫入 artifact、snapshot、index、review、rerun、repair 或 queue。

## D3684 / preserve symbol identity for global market evidence

- `#拆解問題` / `#差距分析` / `#偏誤辨識`：`global_market_context.items` 同時保存 SPY、QQQ、VIX、利率與其他 proxy；原 evidence path 只有 list index，報告的 `QQQ, change_5d_pct` 沒有 symbol-specific path，只能被標為 unverifiable。
- `#最小變更` / `#責任`：只對 `global_market_context.items` 的 mapping path 加入 normalized `symbol`，並只接受 raw claim 同時含明示 symbol 與 `change_5d_pct`；沒有 symbol、metric 不同或資料缺失時維持人工核對，不使用同值 fallback。
- `#來源品質` / `#偏誤降低`：加入 SPY/QQQ 交叉同值反例，確認 QQQ claim 不會命中 SPY；真正 mismatch、其他 unverifiable、final-audit critical 與 rejected evidence gate 不降級。
- `#可驗證性` / `#責任`：先取得 QQQ claim RED，再 GREEN；evidence gate `38 passed`，品質/evidence/conformance `135 passed`，import boundary `504 passed`，HCS/docs `135 passed`，line guard `evidence_exit_gate.py=349`。正式 reload 後 evidence `69 approved / 95 caution / 1 rejected`、claims `181 verified / 150 unverifiable / 2 mismatch`；conformance `49 passed / 108 warning / 8 blocked`、content `51/106/8`，evidence matrix coverage `165/165 passed`。healthz/readyz、doctor canonical paths、RQ queue depth `0` 通過，未寫入 artifact、snapshot、index、review、rerun、repair 或 queue。

## D3683 / rebuild legacy recommendation coverage from canonical source audit

- `#拆解問題` / `#差距分析` / `#語意含義`：legacy snapshot 的 `rerun_context.parsed` 缺失且 `evidence_matrix=[]`；normalized index recommendation 雖可形成 projection context，`evidence_matrix_rows()` 卻因空 persisted key 提前返回，讓 21 份 history row 被標成 `missing_final_recommendation_evidence`，即使 canonical `data + source_audit` 有成功來源。
- `#最小變更` / `#責任`：只在 `_project_from_index_recommendation()` 的 read-only projection clone 移除空矩陣，讓既有 builder 從同一 snapshot 的 `data + source_audit` 重建最終建議列；非空 persisted matrix 維持原語意，正式 evaluator、snapshot、artifact、index、review、rerun、repair 與 queue 不變。
- `#偏誤降低` / `#來源品質`：不把「能重建 evidence row」解讀成報告已通過；若 canonical source audit 不可用，重建列仍會是 unusable warning，既有 final-audit critical、evidence mismatch 與 rejected gate 不降級。
- `#可驗證性` / `#責任`：先以空矩陣 + 成功 source audit 取得 RED，再 GREEN；projection/evidence `14 passed`、content/audit/conformance `69 passed`、import boundary `504 passed`、`git diff --check` 與 compile 通過。正式 reload 後 live 165 份 `evidence_matrix_coverage` 全數 passed，missing/unusable final recommendation evidence `0`；conformance `48 passed / 109 warning / 8 blocked`、content `50/107/8`、evidence `68 approved / 96 caution / 1 rejected`，`3653.TW/v3` 仍 blocked/rejected。historical `1222` 份、coverage `90.59%`、filtered `3653.TW/v3` current latest blocked/rejected；healthz/readyz、doctor canonical paths、RQ queue depth `0` 通過，未寫入 artifact、snapshot、index、review、rerun、repair 或 queue。

## D3682 / separate historical coverage from current latest projection

- `#拆解問題` / `#差距分析` / `#受眾`：historical audit 的 persisted metadata coverage 與目前規則重驗不是同一個 evidence layer；live `3653.TW/v3` 同篩選有 5 個 indexed versions，但原頁沒有 latest current mismatch/blocked 可見性。
- `#最小變更` / `#責任`：新增 `build_filtered_indexed_current_quality_summary()`，沿用 current report-history projection，明示 `historical_filter_current_latest`、`latest_per_ticker_pipeline`、同一 `q`/`pipeline` filters 與獨立 `audited_reports` 分母；歷史 route 使用 `item_limit=0`，不重複 target、不改 persisted coverage。
- `#來源品質` / `#偏誤降低` / `#語意含義`：前端以獨立 helper 顯示「目前版本品質（只看最新版本）」，不把 current status 當成歷史 gate 已修復，也不由 Markdown 重建缺 gate。
- `#可驗證性` / `#責任`：focused backend/current/audit/frontend/daily `85 passed`；正式 reload 後 filtered historical `5 versions / 20.0% persisted coverage`，current latest `1 report / conformance blocked=1 / content blocked=1 / evidence rejected=1`，healthz/readyz `200`、doctor canonical paths/queue 正常，未寫 artifact、index、review、rerun、repair 或 queue。

## D3665 / make full freshness findings directly navigable

- `#差距分析` / `#受眾`：D3664 已顯示全量 `22` 份 stale，但 aggregate 不能告訴操作員要開哪一份；daily queue 保持近期 20 份 sample，不應把 full audit 的唯讀證據誤轉成自動工作。
- `#最小變更` / `#溝通設計`：新增 `decision_freshness_items.v1`，固定 bounded sample 上限 5，回傳 `items_total/items_returned/items_limit/items_truncated`；Watchlist target 沿用既有 history navigation，沒有新的 mutation path。
- `#來源品質` / `#偏誤降低` / `#可驗證性`：summary 與 items 各自驗證 scope/selection basis 與分母一致；RED→GREEN 後 `825 passed`，live `165/143/22/0`、`5/22 truncated`、board target 與 health/readiness/queue/doctor 均通過。

## D3664 / expose full latest freshness without changing quality coverage

- `#差距分析` / `#可驗證性`：live full latest scope 是 `165` 份、`143 current / 22 needs_rerun`，但 daily action sample 只有近期 `20` 份且全 current；單看 `summary.reports_needing_rerun=0` 不能代表全量分析已新鮮。
- `#最小變更` / `#責任`：新增 `report_freshness_summary`，只在 indexed latest quality audit envelope 附加 scope-bound `decision_freshness_summary`；watchlist/operator 以獨立文字顯示全量 stale count，quality metadata coverage、repair queue、review、rerun 與 persisted state 不互相替代。
- `#來源品質` / `#偏誤降低` / `#可驗證性`：freshness count 必須滿足 `current + needs_rerun + unknown = audited`，scope 與 selection basis 不符就不顯示；RED→GREEN 後目標回歸 `815 passed`，live API 為 `165 audited / 143 current / 22 needs_rerun / 0 unknown`，health/readiness、queue depth `0`、canonical paths 與兩個 cache-buster assets 均通過。

## D3663 / label the report-count scope in the daily dashboard

- `#差距分析` / `#可驗證性`：live dashboard 的 `reports_needing_rerun=0` 與 `report_repairs_required=16` 是近期 20 份 report sample；同一 response 又有 165 份 full latest-per-ticker/pipeline quality audit，沒有 scope label 時容易把 sample count 誤讀成全量結論。
- `#最小變更` / `#責任`：保留既有 summary count 與 queue 行為，新增 `summary.report_scope` 宣告 `daily_report_sample` 和 sample size；operator summary 只增加範圍文字，不改 freshness predicate、audit、artifact、snapshot、index、review 或 rerun。
- `#可驗證性` / `#來源品質`：先以 backend/frontend scope fixture RED 再 GREEN；dashboard/frontend/audit/docs `278 passed`；live scope `20`、full audit `165`、audit gap `2` 全在 sample 外，health/readiness/queue 均正常。

## D3662 / surface stale analysis in report reading notices

- `#差距分析` / `#內容可信度`：live report row 可同時是 `data_trust=fresh` 與 `decision_freshness=needs_rerun`；原本 HTML/Markdown 閱讀提示只呈現資料新鮮，沒有把「分析本文未重跑」放進使用前限制，容易把新資料誤讀成新結論。
- `#最小變更` / `#責任`：current report row 的 freshness 與 stale-analysis 欄位以 view-time projection 注入共同 reading notice；新增「分析新鮮度」檢查，需重跑時顯示完整重跑與現行原因，原始 artifact、data snapshot、index、review、rerun、repair 與 queue 不變。
- `#可驗證性` / `#來源品質`：values、HTML/Markdown notice 與 history storage regression 先 RED 再 GREEN；storage/notice `77 passed`、import/docs `573 passed`；live `165` 份 indexed reports 的 HTML/Markdown `330` 個 response 為 `143 current / 22 stale`、錯誤 `0`，runtime `healthz=ok`、`readyz=ready`、queue depth `0`。

## D3661 / align execution summary explanations across HTML and Markdown

- `#差距分析` / `#語意含義`：current gate status 已更新後，HTML execution note 與 Markdown 的 gate/摘要仍沿用 persisted explanation；操作員會看到 warning 卻讀到「抽樣數字均可」的相反理由。
- `#最小變更` / `#組成`：新增 focused execution-summary view repair helper，同步 HTML 三個 status 與 evidence note、Markdown 三個 status 與三個摘要；只在 current projection context 生效，Final audit、Report lint 與 raw data 維持既有來源。
- `#可驗證性` / `#來源品質`：HTML note/Markdown summary 先 RED 再 GREEN；storage `49 passed`、preview `121 passed`、execution/data-trust `70 passed`、HTTP `9 passed`、import boundary `504 passed`、docs/HCS `135 passed`。

## D3660 / make Markdown quality notice replacement state-symmetric

- `#差距分析` / `#偏誤降低`：Markdown repair 只有在新 notice 是 warning/blocked 時才替換，current passed 或 pending 會讓舊 warning 留在 response；這是狀態轉換方向不對稱，不是單一報告內容問題。
- `#最小變更` / `#可驗證性`：移除 severity-specific early return；只要有有效 notice context，既有 Markdown notice 就完整替換，缺少 notice 時也補上。raw Markdown、data snapshot、HTML、index 與 queue 不變。
- `#來源品質` / `#研究複製`：raw latest scope 對照發現 `107` 份 mismatch；反向 current-passed fixture 先 RED 再 GREEN，Markdown targeted `14 passed`、storage `49 passed`、reading notice `23 passed`。

## D3659 / align Markdown download with current quality projection

- `#差距分析` / `#媒介`：HTML 與報告列表已顯示 current quality warning，但 Markdown download 仍輸出 artifact 內的「已通過已知檢查」；操作員若以 Markdown 進行離線核對會得到相反判讀。
- `#最小變更` / `#責任`：HTML/Markdown 共同查詢 `report_quality_notice_context`，Markdown 只替換 response-time reading notice；data download 不取得 projection，實體檔案與 snapshot 維持原值。
- `#可驗證性` / `#來源品質`：Markdown regression 先 RED 再 GREEN；storage suite `48 passed`，驗證 response warning、raw Markdown unchanged、raw data unchanged。

## D3658 / align execution summary with current quality gate projection

- `#差距分析` / `#一致性`：D3657 讓完整 HTML 頂部閱讀提示使用 current gate，但頁面下方 execution summary 仍顯示 artifact 內的 `approved/passed`；同一個報告入口因此同時傳達兩套品質結果。
- `#最小變更` / `#責任`：只在 response-time current projection context 存在時，覆蓋 Evidence gate、Content credibility、Report conformance 的可見值與 aria label，並加上 `data-quality-source=current-projection`；Final audit、Report lint 與原始資料仍保持 persisted，實體 artifact 不改寫。
- `#可驗證性` / `#來源品質`：storage regression 先 RED 再 GREEN；`1 passed`、storage `47 passed`，live execution summary 與 `/download/data` 分別驗證 current view 與 persisted snapshot。

## D3657 / align full report HTML reading notice with current quality projection

- `#差距分析` / `#受眾`：live history row 已把 3324 v4 的 current evidence/content 警示呈現出來，但操作人員點開完整 HTML 仍看到 persisted「已通過已知檢查」；列表與完整報告是同一個閱讀流程，不能讓入口各自使用不同品質狀態。
- `#最小變更` / `#責任`：新增 `report_history_quality_notice` lookup，在 view-time 讀取同一份 report index current row，將三個 current quality gate overlay 到 HTML reading notice；實體 HTML、Markdown、data snapshot、index 與 queue 維持原值，snapshot integrity invalid 仍優先使用阻擋提示。
- `#可驗證性` / `#來源品質`：storage RED→GREEN；`tests/test_report_storage_integration.py` `47 passed`、history/preview `119 passed`、import boundary `504 passed`；runtime reload 後 3324 v4 與 1623 v1/v2 完整 HTML 均為 warning，data download 仍為原始 persisted 值。

## D3656 / align composite conformance with current evidence and content gates

- `#差距分析` / `#偏誤辨識`：165 份 current row 中 106 份的 evidence/content 已有 warning 或 blocked，但 persisted `report_conformance` 仍是 passed；單看 composite status 會掩蓋 current quality warning。
- `#決策樹` / `#最小變更`：新增 read-only conformance projection，更新 evidence/content decision-tree steps 與 composite status；persisted conformance、review、quality coverage、snapshot 與 queue 不變，另提供 `report_conformance_projection.persisted_status`。
- `#可驗證性` / `#責任`：3324 live-shaped RED→GREEN；projection unit `2 passed`，接續跑完整 content/report-quality/conformance、HTTP、docs 與 import boundary 回歸。

## D3655 / recover legacy content evidence from normalized recommendation context

- `#差距分析` / `#來源品質`：全量 165 份 latest scope 中，1623 v1/v2 的 snapshot 沒有 `content_credibility` 與 parsed context，但 index recommendation、data trust、Markdown、evidence gate 都存在；不能把空 mapping 解讀成內容已通過，也不能因 legacy 缺口放棄可讀的 deterministic evidence。
- `#語意含義` / `#最小變更`：新增 recommendation-context projection，將 normalized `recommendation`、`confidence`、3/6/12 月目標映射回 evaluator aliases；以 `snapshot.recommendation_context` 標示來源，保持 persisted quality audit 與 download data 原值。
- `#可驗證性` / `#責任`：1623 live-shaped RED→GREEN；projection unit `6 passed`、history API `2 passed`，projection 結果含 warning 與 evidence check，不自動升級為 passed。

## D3654 / keep partial evidence projection from replacing full content checks

- `#差距分析` / `#偏誤辨識`：部分 legacy v1-v3 snapshot 只有空的 `rerun_context.parsed`，不能完整重算 content credibility；若直接把 evidence-only result 當完整 projection，v4 trade-plan fallback 會被提前跳過。
- `#最小變更` / `#語意含義`：partial projection 以 `_projection_scope=evidence_confidence` 標示，先讓原有 v4 fallback 完成，再合併 current evidence-confidence check；其他 persisted check、snapshot 與 download data 不變。
- `#可驗證性` / `#責任`：3653 legacy payload RED→GREEN；content/report-quality/conformance/preview `1198 passed`、history E2E `8 passed`、import boundary `504 passed`，module `349` 行。

## D3653 / keep evidence and content projections on one current context

- `#差距分析` / `#偏誤辨識`：D3652 的 evidence gate 已使用 current markdown/snapshot parser，但 content credibility 仍可能讀到 persisted `approved`，讓 API 同時呈現 evidence=`caution/rejected` 與 content=`passed`。
- `#最小變更` / `#語意含義`：建立 shallow `content_projection_snapshot`，只替換投影用的 `evidence_exit_gate`；原始 snapshot 與 download/quality/audit state 不變，v4 trade-plan fallback 也沿用同一 current gate。
- `#可驗證性` / `#責任`：history API regression RED→GREEN；projection/e2e `10 passed`、content/report-quality/conformance/preview `1197 passed`、import/lint/data-trust `578 passed`，保留 persisted gate 與 current projection 的可追溯差異。

## D3652 / project current evidence without rewriting history

- `#差距分析` / `#責任`：D3651 的程式規則已正確，但既有 `/api/reports` 仍直接顯示 persisted 舊 evidence gate；若只看 API，操作員會看不到 current parser 對舊 artifact 的修正。
- `#可驗證性` / `#偏誤降低`：新增 read-only evidence projection，row primary gate 使用 current markdown + snapshot evaluation，`evidence_exit_gate_projection` 明示 current/persisted 差異；download data、snapshot hash、artifact、review、rerun、repair、queue 不變。
- `#語意含義` / `#最小變更`：`missing_quality_fields` 與 indexed quality audit 仍以 persisted gate 計算，避免把 projection 當成 metadata 已補齊；RED→GREEN projection/e2e、preview/quality/audit、import/docs/HCS 回歸通過。

## D3651 / keep provider, field, and scenario semantics separate

- `#拆解問題` / `#偏誤辨識`：165 份 latest-per-ticker/pipeline 重掃顯示，FactSet/券商參考值、Forward PE、派生 EPS growth、情境表價格與 ticker identifier 仍可能共享同一個 broad label matcher；structured target 字串也同時包含 canonical target 與「52 週／突破位」敘述。
- `#來源品質` / `#語意含義`：provider-context claim 只尋找同 provider path；Forward PE、EPS growth、淨利率、scenario、risk 各自使用專屬 path hints，`conclusion_guardrails` 與 identifier metadata 不作證據；structured target 先移除 horizon prefix，再只取 canonical 首值。
- `#可驗證性` / `#責任`：無對應 provider/field path 就是 `unverifiable`，不因最近數字而 mismatch；全量 current-code rescan 保留 3 個可解釋的 PE/淨利率 mismatch 作人工核對，`39/125/1` verdict 與 `115/780/3` claim counts 均有 scope，未改任何 persisted state。

## D3650 / keep evidence matching semantic and fail closed

- `#拆解問題` / `#偏誤辨識`：live reports 的 `T07/T13`、資料日期、`N/A` source cells 與 `1-2週` range prefix 都是技術/格式 token，不是投資數字；confidence claim 則曾被全 snapshot 最近值補配，形成看似有證據的錯誤 mismatch。
- `#來源品質` / `#語意含義`：新增 confidence、moat、operating-margin、scenario path hints，排除 source audit、timestamp、hash、quality metadata 等 snapshot metadata；known semantic claims 只查對應路徑，unknown/no-candidate claim 改記 `unverifiable`，不再把任意數字當成支持證據。
- `#可驗證性` / `#責任`：`failed_count` 只計 `mismatch`，另保留 `unverifiable_count` 並將無可比對樣本降為 `caution`；RED→GREEN 後 focused evidence/conformance/content `53 passed`，live 2026-08-20 artifact rescan 為 `2 approved / 3 caution`、`3 verified / 0 mismatch / 4 unverifiable`，compile/diff check 通過，沒有 persisted state 或 queue mutation。

## D3649 / keep evidence claims away from periods and identifiers

- `#差距分析` / `#來源品質`：live `3706.TW v4` 的「近期催化劑：52U 液冷機櫃」被 evidence parser 當成 52，且長 label 把它錯配到自由現金流快照 4.14；同一類問題也會把 `5a357...` commit hash 前綴當成數字。
- `#拆解問題` / `#偏誤辨識`：numeric claim regex 改為長單位優先（`TWD` 不再被截成 `T`），要求數字後不得接英數/小數前綴，並排除週、月、年、天、日的期間後綴；EPS 明確語境的日期前綴仍由既有 EPS value override 保留。
- `#可驗證性` / `#最小變更`：真實 3706 artifact RED→GREEN，`caution / failed_count=1` 收斂為 `approved / failed_count=0`；`109.0 TWD` 保留，evidence/conformance/content `49 passed`、audit/docs/HCS `207 passed + 75 subtests`，未修改 persisted gate 或 queue state。

## D3648 / protect approved target-name substrings from peer contamination

- `#差距分析` / `#來源品質`：live `3711.TW v4` 的阻擋訊息是同業「日月光」出現 9 次，但 artifact 的目標正式名稱是「日月光投控」；逐次核對文字後確認是正式目標名稱內的合法子字串，不是模型把同業套成目標公司。
- `#拆解問題` / `#偏誤辨識`：`count_unqualified_alias()` 新增 `protected_aliases` span 過濾，只保護完整落在 `allowed_aliases` 內的同業名稱匹配；保留 `大亞` 未標示同業的既有污染測試，避免把合法 target alias 修正擴張成全面忽略同業名稱。
- `#可驗證性` / `#最小變更`：3711 真實 artifact RED→GREEN；`test_audit_rules` `72 passed + 75 subtests`、content credibility/projection/import-boundary `535 passed`，compile/diff check 通過，未修改任何 persisted report 或 queue state。

## D3647 / deduplicate confidence calibration warnings without erasing source evidence

- `#差距分析` / `#責任`：live `2308.TW v2` 的 final-audit warning 有兩句不同句尾但相同 agent、data trust、confidence 與 cap；根因是 structured-output warning 與 final-audit 各自組字串，且只做精確字串去重。
- `#最小變更` / `#偏誤降低`：新增 shared formatter 與 confidence-warning fingerprint；新報告在來源層只產生一筆，既有報告在 read-only credibility projection 只合併這個可辨識家族，保留 raw `report_conformance` 與非同義警示。
- `#可驗證性`：RED→GREEN 後 content/projection/prompt `55 passed`、audit `71 passed + 75 subtests`、import-boundary `504 passed`，compile/diff check 通過；runtime `2308.TW v2` projection 細節收斂為一筆，未寫 snapshot、artifact、index、review、rerun 或 queue。

## D3646 / remove bare month-day tokens from trade prices

- `#差距分析` / `#來源品質`：live `8070.TW v4` 的停損數值 `48.0` 後接括號日期 `8/18`；既有完整日期／帶單位日期清理沒有涵蓋裸月日，造成日期拆成兩個價格候選。
- `#拆解問題` / `#最小變更`：在 `content_credibility_inputs` 的 read-only normalization 增加合法月份 1-12、日期 1-31 的裸 `M/D` 清理；保留真正價格，並以明確的 `1/2 TWD` 非日期字串測試避免過度清理。
- `#可驗證性` / `#責任`：RED→GREEN 後 content-credibility/projection/input `909 passed`、selected quality/queue/docs/import `1031 passed`，compile/diff check 與 97 行 import-boundary 通過；runtime reload 後 `8070.TW v4` 由誤標 warning 回復 passed，全量 ambiguous warning `60 -> 59`。未寫 snapshot、artifact、index、review、rerun 或 queue。

## D3645 / surface ambiguous multi-scenario trade prices

- `#差距分析` / `#偏誤辨識`：live v4 的 `Neutral` 交易計畫可能在 target 或 stop-loss 欄位放入多個情境價位；`first_price()` 只取第一個數字，造成 check 以單一值呈現但沒有提醒原文其實是條件分支。
- `#拆解問題` / `#語意含義`：新增 `price_candidates()` 與明確價格區間辨識；多個非區間價格產生 `ambiguous_trade_setup_price_inputs` warning 並保留候選值，明確兩端區間不警示，且不把 Neutral 改成 Long/Short 或 blocker。
- `#可驗證性` / `#最小變更`：先以 live-shaped 多情境 target 取得 RED，再 GREEN；content-credibility/projection/input `908 passed`、price-parser/recommendation/target-detection `2601 passed`、selected quality/queue/docs/import `1031 passed`，compile/diff check 與正式 runtime reload 通過，live 三筆 v4 報告確實輸出候選值與 warning。只改 read-only credibility evaluation，不寫 snapshot、artifact、index、review、rerun 或 queue。

## D3644 / preserve quality-audit action semantics across queue boundaries

- `#差距分析` / `#責任`：live 品質稽核 action 的優先級與阻斷旗標仍在，但 audit item 到 daily queue 的 payload 邊界遺失 `severity`、`action_label`；直接消費 queue 的人只能從 detail 猜「阻斷／人工審核」。
- `#溝通設計` / `#偏誤降低`：讓 `report_quality_audit.items[]` 直接保留 repair item 的 `severity=blocked` 與 `action_label=人工審核`，與既有 `operator_action` 導覽 metadata 並存；不把 artifact marker、detail 文案或 priority 推論成 gate 結果。
- `#可驗證性` / `#最小變更`：先取得 RED，再 GREEN `3 passed`；只修正 read-only payload shaping，未改 queue 排序、review、rerun、artifact、index 或 persisted quality state。

## D3643 / prevent period ranges from becoming trade prices

- `#差距分析` / `#來源品質`：live `2308.TW v4` 的「1-2週目標價」被 `first_price()` 讀成 `1.0`，讓 trade-setup credibility check 看似 passed 卻檢查了錯誤目標。這是內容可信度的語意錯位，不是文案格式問題。
- `#拆解問題` / `#偏誤降低`：只在 input normalization 階段移除帶有週、月、年、日單位的單值或範圍數字，讓 `1-2週`、`1至2週`、`1 to 2 weeks` 不進價格 parser；既有單一價格、日期清理與 downstream price rules 維持不變。
- `#可驗證性` / `#責任`：先取得兩個 RED，再 GREEN；相關 content credibility/target detection 回歸 `1765 passed`，runtime 真實 `2308.TW v4` 目標值為 `1950.0`，只修正 read-only 解析，不寫 snapshot、artifact、index、review、rerun 或 queue。

## D3642 / expose unavailable confidence calibration without changing gate policy

- `#拆解問題` / `#偏誤辨識`：live `/api/reports` 顯示 `144/165` 份最新報告的 confidence calibration check 是外層 `passed`、內層 `status=unavailable`；缺少信心分數的報告因此留下了過度樂觀的 check status，projection merge 另會把舊 persisted passed check 重複帶出。
- `#語意含義` / `#可驗證性`：unavailable 分支改輸出 `status=unavailable` 與「無法完成資料可信度上限檢查」，current projection 對同一 check id 優先且去除重複；仍維持無 warning、無 blocker、整體 content-credibility status 與 shared confidence policy 不變。
- `#偏誤降低` / `#責任`：這是 evidence status 的忠實呈現，不把不可評估升級成投資阻斷，也不把 `data_trust`、confidence cap、report artifact、index 或 queue state 改寫。
- `#可驗證性`：先取得兩個 RED，再 GREEN；content credibility/conformance/projection `41 passed`，文件契約、runtime reload 與全量報告 API probe 待本輪收斂後封存。

## D3641 / align route-warning navigation across queue and notifications

- `#差距分析` / `#受眾`：live `decision_queue.items` 的 route warning 只有 route/warning id，notification message/outbox 已有 CTA；只讀 queue consumer 無法可靠開啟相同的 model-route panel。
- `#責任` / `#溝通設計`：`daily_decision_route_warnings` 重用 `operator_action_contract.navigation_context()`；provider quota、provider error、retry 與 quality route warnings 都輸出 `open-ops`、`查看路由`、`api-quota-panel`、`ops`，明確自訂 metadata 仍 authoritative。
- `#偏誤降低` / `#最小變更`：只補 navigation metadata，不改 `NON_ACTIONABLE_WARNING_IDS`、warning priority、model route、queue ordering、notification suppression 或 report/rerun state。
- `#可驗證性`：RED→GREEN 後 daily queue/dashboard/free notification `231 passed`，selected regression `1159 passed`，compile/diff check 通過；runtime reload 後維運頁顯示 `6` 筆 Provider 配額告警，live queue/message/delivery outbox 的可見 route warnings 四個 navigation fields 完全一致。

## D3640 / split report follow-up shaping from daily queue orchestration

- `#差距分析` / `#組成`：完整 import-boundary gate 顯示 `daily_decision_queue.py` 已達 257 行；它同時收集跨來源 action、排序 queue，並處理到期回測、重跑報告與日期解析，讓報告規則變更會擴大 queue owner 的耦合面。
- `#責任` / `#最佳化`：新增 `daily_decision_report_actions`，只承接 `backtest_due`、`rerun_report` 與 report-date parsing；queue 保留 orchestration、skip key、排序與 `queue_response`，不改 public `daily_decision_queue.v1` payload。
- `#可驗證性` / `#研究複製`：import-boundary RED→GREEN；完整 import-boundary `504 passed`，queue/dashboard/free notification `231 passed`，queue `165` 行、helper `111` 行，compile/diff check 通過；runtime/readiness 與既有 stale queue 狀態未被寫入。

## D3639 / separate provider errors from node failures in route observability

- `#拆解問題` / `#證據基礎`：live `model_route_budget` 的 `failures=0` 只代表節點 telemetry；同一 `api_usage_events` ledger 已有 provider quota/error，fallback 成功使路由摘要低估風險。先以 `job_id -> analysis_jobs.pipeline_id` 對回 route，不把 provider attempt 直接算成節點 failure。
- `#偏誤降低` / `#語意含義`：新增 bounded `recent_api_usage_events` sample 與 `provider_error_count`/`provider_quota_error_count`，warning 使用 `provider_quota_errors` 或 `provider_errors`；保留 reset-window API quota aggregate 與 route node metrics 的不同統計範圍，UI 以專用 Provider 文案呈現。
- `#責任` / `#最小變更`：provider ledger reader 抽成 `job_ops_dashboard_provider_errors`，只回傳 pipeline/model/status；不輸出 key slot、message、secret，不改 model route、Redis circuit、queue、report、rerun 或任何 persisted state。
- `#可驗證性`：RED→GREEN 後 model/runtime `150 passed`、static history `139 passed`、docs contract `69 passed`；Python/Node compile、dashboard import-boundary gate 與 `git diff --check` 通過，runtime health/readiness/doctor 及 in-app 維運頁 live smoke 通過。完整 import-boundary suite 仍有上一批 `daily_decision_queue.py` 的既有 257 行門檻失敗，本輪未觸碰該檔案。

## D3638 / keep report-repair navigation consistent across queue and notifications

- `#差距分析` / `#受眾`：live `report_repair` queue item 已有 filename，但沒有 CTA/target metadata；notification message/outbox 卻已有 `view-report`、`人工審核`、`active-jobs-panel/ops`，直接消費 queue 的入口會與通知漂移。
- `#拆解問題` / `#責任`：把帶 filename 的 repair payload 送入既有 `operator_action_contract`；保留 `report_quality_audit` 有 identity 才能進 targeted history 的限制，明確自訂 action/label/panel/tab 仍 authoritative。
- `#最小變更` / `#副作用`：只補 read-only navigation metadata，不改 repair priority、reason、blocks_auto_rerun、review、artifact、index、rerun 或 repair state；沒有 filename 的 quality action 不猜導覽。
- `#可驗證性`：先取得 RED，再 GREEN 通過 queue/notification/delivery/dashboard `309 passed`；runtime reload 後 queue/message/outbox 四個欄位一致，health/readiness、canonical paths 與 RQ 通過。

## D3637 / keep EPS evidence claims semantically aligned

- `#差距分析` / `#來源品質`：live `2603.TW v4` 的證據抽查把「7 月底」的日期數字當成 `Factset EPS 下修預警` 的 claim value `7`，人工看到的 mismatch 因而不是原文真正的 EPS `26`。
- `#拆解問題` / `#偏誤降低`：只對 label 已明確指向 EPS／每股盈餘的 claim，從 EPS 語句取相連數值；一般 key-value claim 維持原 parser，避免把日期 token 或其他欄位普遍改寫。
- `#倫理判斷` / `#最小變更`：修正證據呈現的忠實度，不把 `26` 與快照現有 EPS 值的真實差異改成通過；不回寫既有 snapshot、artifact、index、review、rerun 或 queue。
- `#可驗證性`：RED→GREEN 後 evidence/credibility/repair/audit/review `141 passed`；重載 runtime 的 health/readiness、canonical paths、RQ 與 daily `165/2/98.79%` 通過，既有 persisted gate 維持原值。

## D3636 / make quality-audit queue actions self-describing

- `#差距分析` / `#受眾`：live `decision_queue.items` 的品質稽核 action 只有 source/type/report identity，notification message/outbox 才有 CTA 與 target metadata；直接消費 queue 的下游仍要自行推導人工核對入口，可能與通知或工作台漂移。
- `#拆解問題` / `#責任`：新增共享 `operator_action_contract`，帶 filename 的 `report_quality_audit` + `manual_review` queue item 與 notification plan 都從同一組 source/type default 產生四個 metadata；queue 原有排序、dedupe、coverage 與其他來源維持不變。
- `#偏誤降低` / `#可驗證性`：明確傳入的 operator action/label/panel/tab 仍 authoritative；缺 filename 不套 targeted history default；只補 read-only 導覽 metadata，不核准 review、不重跑、不寫 snapshot、artifact、index 或 queue state。
- `#可驗證性`：RED→GREEN queue、notification、delivery、dashboard `308 passed`，history/static/docs `220 passed`，Node/Python compile 與 `git diff --check` 通過；runtime reload 後同一 daily response 顯示 queue/message/outbox 的 CTA、target panel/tab 一致，daily quality scope 為 `165` audited、`2` missing、`98.79%` coverage；browser desktop/mobile smoke 通過，390px 無水平溢出且 console 無錯誤。

## D3635 / align quality-audit target metadata with the history entry point

- `#差距分析` / `#受眾`：D3634 只同步 notification 的 CTA 文字與 action id；live message/outbox 仍帶 `active-jobs-panel/ops`，只依 target metadata 導覽的通知消費者會落到錯誤面板。
- `#拆解問題` / `#責任`：沿用現有 DOM contract `#history-quality-audit` 與 `#home-tab-analysis`，以 source+type default 輸出 `history-quality-audit/analysis`；上游明確 target panel/tab 仍 authoritative，frontend action model 也共享同一判斷。
- `#偏誤降低` / `#可驗證性`：只修正 navigation metadata，不改 quality scope、CTA custom override、review ledger、snapshot、artifact、index、rerun 或 queue state；一般 repair/provider/watchlist target 維持原值。
- `#可驗證性`：初始 notification、delivery、daily queue/dashboard、historical navigation `319 passed`；補齊文件契約與 cache-buster 後最終 selected suite `526 passed`，Node syntax 與 `git diff --check` 通過，runtime reload 後以同一 daily response 核對 queue/message/outbox，三者 target metadata 已一致。

## D3634 / keep notification CTAs aligned with quality-audit workbench

- `#差距分析` / `#受眾`：live daily dashboard 的品質稽核 action 已能從 operator summary 進 targeted history，但同一 action 在 `notification_plan.messages` 與 `delivery_outbox` 仍由 type-only `manual_review` default 變成「查看報告」，本機/外部通知因此失去人工核對範圍。
- `#拆解問題` / `#責任`：在 notification plan 的 default CTA 增加 `(source, type)` 優先查找；只有 `report_quality_audit` + `manual_review` 且帶 filename 才用 `quality-audit-review` / `前往人工核對`，上游明確自訂 `operator_action` 仍維持 authoritative，`report_repair` 維持 `view-report`。
- `#偏誤降低` / `#可驗證性`：保留原有 filename、pipeline、dedupe、delivery audit 與 read-only quality scope，不因通知 CTA 自動核准、重跑、寫 review、artifact、index 或 queue state；RED→GREEN notification plan、delivery audit、queue/dashboard focused regression 通過。
- `#可驗證性`：free notification plan + delivery audit `148 passed`，daily queue/dashboard quality notification focused `32 passed`；runtime reload 後以 canonical dashboard response 核對 message/outbox action 與 workbench action 一致。

## D3633 / route quality-audit queue actions into targeted human review

- `#差距分析` / `#受眾`：D3631 已讓完整 latest quality audit gap 出現在今日 decision queue，但 operator summary 仍把它當成一般 `manual_review`，只開啟報告；操作員還要自行切換 history 並重建 filename/pipeline 範圍。
- `#拆解問題` / `#責任`：沿用 watchlist、report preview 已使用的 `StockAgentOpenHistoricalQualityAudit({ query, pipeline })`，只在 `type=manual_review`、`source=report_quality_audit` 且 filename 存在時映射專用 action；一般 report repair 與非人工核對 action 不變。app wrapper 回傳既有 workspace Promise，讓工作台按鈕的 busy state 覆蓋載入。
- `#偏誤降低` / `#倫理判斷`：這是 targeted read-only navigation，不把 artifact marker 當成 gate pass，不自動核准 review、不 enqueue rerun，也不寫 snapshot、artifact、index、review 或 queue state；partial/unavailable/historical scope 仍不會進 daily queue。
- `#可驗證性`：先取得 dashboard mapping 與 operator delegation RED，再 GREEN；跨 history/quality evidence/static contracts `180 passed`，Node syntax 與 `git diff --check` 通過；補上 architecture/operator guide contract。

## D3632 / make temporal price ranges follow the latest available data date

- `#差距分析` / `#來源品質`：fixture 的最新價格資料日是 2026-07-01，但 extractor 以執行日 2026-08-21 切 5 年窗口，排除 2021-07-01 並把 return 從 142.0% 算成 72.86%。
- `#偏誤降低` / `#可驗證性`：以 `min(now, latest_data_date)` 作價格 history as-of，避免延遲或歷史資料被當成今天；同步校準 8f53dc81 後已變更 renderer 的 golden hash，保留 required markers。
- `#最小變更` / `#副作用`：只修正時間窗口與 stale golden fixture，不回寫報告 artifact、report index、review 或 runtime state；focused data-fetch/golden `22 passed`。

## D3631 / surface complete latest audit gaps in the read-only decision queue

- `#差距分析` / `#責任`：live daily audit 的 current gap 有完整明細與人工核對資訊，但既有 queue 只顯示 repair sample，讓 audit coverage 與 next-action surface 斷開。
- `#偏誤降低` / `#可驗證性`：只接受 `all_indexed_reports`、`latest_per_ticker_pipeline`、未截斷且明細數等於缺口數的 audit envelope；與 repair sample 依 filename/pipeline 去重，partial、unavailable、historical 不推論 action。
- `#最小變更` / `#副作用`：沿用既有 repair payload、manual-review CTA 與 rerun blocking metadata；queue item 只供 dashboard/notification presentation，不 enqueue、不寫 review、artifact、index 或 repair state。

## D3630 / skip unused current-quality projection during indexed audit

- `#最佳化` / `#責任`：profile 顯示 historical audit 每筆 row 都會執行 current-rule content projection，但 audit 只需要 persisted gate metadata、snapshot integrity 與 artifact/context evidence；若 persisted content gate 缺失，projection 也不會被採用。
- `#拆解問題` / `#可驗證性`：新增 `project_current_quality` hydration boundary；一般 report-history row 保持 projection，indexed quality audit 關閉 projection，並以 RED→GREEN 測試防止兩條責任邊界互相污染。
- `#來源品質` / `#偏誤降低`：historical profile 約由 `3.48s` 降至 `2.64s`，projection calls `1107 -> 0`；audit scope/coverage/missing counts 不變，未寫 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3629 / expose exact quality-gap overlap with the repair sample

- `#差距分析` / `#語意含義`：live daily audit 的 `2` 個 current gap 與 repair queue 的 `20` 筆 input sample 沒有交集；queue action 的 `2603.TW` warning 不是那兩個 metadata gap。只有 sample size 提示仍不足以回答「缺口是否已在 sample」。
- `#偏誤降低` / `#責任`：新增 `report_quality_audit.repair_sample_overlap`；完整 audit items 依 filename/pipeline 回報 exact in/out，`partial` 明確不推論未展開 items。這是 read-only scope calibration，不把 gap 自動加入 queue、不改 priority、rerun 或 mutation。
- `#可驗證性` / `#證據基礎`：backend RED→GREEN；dashboard/quality/history frontend `320 passed`、docs/HCS `135 passed`、import boundary `503 passed`、compile/diff check 通過；runtime reload、health/readiness/doctor、live scope/overlap 與新 cache-busted asset 均核對完成，未寫 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3628 / keep manual review revisions stable across index refreshes

- `#批判` / `#偏誤降低`：連續四次 live 讀取同一份 `1623.TW` v2 report revision 一致，但追查 index writer 後確認 `updated_at` 是 upsert time，`file_mtime` 是 filesystem refresh signal；把兩者當版本欄位會將 metadata refresh 誤判成內容變更。
- `#責任` / `#可驗證性`：`report_quality_revision()` 現在只使用 report identity 與 data snapshot/HTML/Markdown/data-file hashes；內容 hash 改變仍切換 revision，audit cache 的 index fingerprint 維持原責任。revision stability regression 先 RED 再 GREEN `35 passed`，未寫 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3627 / make quality audit and repair queue scopes explicit

- `#差距分析` / `#語意含義`：live daily response 同時有 latest-per-ticker/pipeline quality audit `165` 筆與 repair queue sample `20` 筆；不標範圍時，操作員可能把 quality gap 數誤讀成 queue 已涵蓋數。
- `#責任` / `#偏誤降低`：watchlist 只新增「修復 queue 範圍：取樣 N 份報告」的 presentation note，保留 quality audit 不進 daily queue 的責任邊界，不改 repair selection 或建立 action。
- `#可驗證性` / `#證據基礎`：以 scope fixture RED→GREEN，並補跑 static size、完整 quality/frontend、contracts、storage、runtime 與 live scope probe；未寫 snapshot、artifact、index、review、rerun 或 queue。

## D3626 / surface per-pipeline context readiness

- `#分析層次` / `#差距分析`：live context aggregate 顯示 v4 的 `29` 筆全部 `missing`，v1/v2/v3 則有 artifact fallback；只看總量會遮住模式級準備差異。
- `#溝通設計` / `#受眾`：history/watchlist 在既有「模式缺口」旁增加「模式上下文」，沿用 per-pipeline API map；它只改善工作排序，不把 artifact 前序段落寫成局部重跑授權。
- `#可驗證性` / `#責任`：新增 UI RED→GREEN 與 cache-buster 契約，預計補跑完整前端、quality、docs/import、runtime 與 live pipeline probe；不寫 snapshot、artifact、index、review、rerun 或 queue。

## D3625 / summarize read-only rerun context readiness

- `#差距分析` / `#效用`：live historical audit 的 `115` 筆缺口雖然全部要求完整重跑，但只有 `86` 筆有 artifact fallback，`29` 筆沒有局部上下文；D3624 的 execution summary 無法直接回答人工準備材料的分布。
- `#責任` / `#語意含義`：新增 `quality_metadata_missing_by_rerun_context`，把 context availability 與 execution strategy 分開；`artifact_fallback_available` 只描述可讀前序 Agent sections，不升格為局部重跑授權，`not_evaluated` 只表示沒有可信 status。
- `#可驗證性` / `#證據基礎`：backend、history、watchlist 先 RED，再 GREEN `66 passed`；後續以 docs contract、full quality/frontend/storage/runtime、live audit 與 cache-buster probe 驗證，未寫 snapshot、artifact、index、review、rerun 或 queue。

## D3624 / summarize read-only rerun execution strategy

- `#差距分析` / `#效用`：live historical audit 的 `115` 筆 structured quality 缺口全部要求完整重跑，其中 `86` 筆只有 artifact fallback、`29` 筆沒有局部上下文；原本只在 item detail 顯示，工作台無法先做策略排序。
- `#責任` / `#語意含義`：新增 `quality_metadata_missing_by_rerun_execution`，只聚合 verified snapshot 的缺口 item，沿用 repair predicate 的四種 `rerun_execution_status`，另以 `not_evaluated` 保留 provenance 不足的缺口；history/watchlist 顯示白話策略，但不 enqueue、改 freshness 或把 artifact fallback 當成授權。
- `#可驗證性` / `#證據基礎`：backend、history、watchlist 先 RED 再 GREEN `3 passed`；再補跑完整 quality/audit/conformance、storage/history、import/docs/HCS、frontend HTTP、live API/asset/doctor 與 post-push sanity，保留 current/historical scope 與既有 after-refresh 分類。

## D3623 / keep pre-refresh provenance classification consistent across surfaces

- `#差距分析` / `#偏誤辨識`：D3622 已產生 `quality_metadata_before_refresh`，但 audit aggregator、`/api/reports` row mapper、preview/history helper 與 watchlist summary 仍只理解 after/no-refresh；同一份證據會被 backend 統計成 `no_refresh_provenance`，前端則沒有白話來源。
- `#責任` / `#語意含義`：新增共用 reason-code classifier，統一輸出 `before_refresh`、`after_refresh`、`no_refresh_provenance`；before 只有在 pre-refresh trace 覆蓋目前缺口時成立，after 仍是中性刷新歸因，no-refresh 仍不代表從未刷新。所有呈現只讀，不改 gate、coverage、review、rerun 或 queue。
- `#可驗證性` / `#證據基礎`：五個入口先 RED 再 GREEN；quality/audit/repair/preview/frontend/history/navigation `257 passed`，並補跑完整 contracts、runtime path、live audit 與 post-push probe，確認舊 snapshot 與新 provenance 的語意分流。

## D3622 / record pre-refresh quality evidence provenance

- `#差距分析` / `#偏誤辨識`：live indexed audit 的 `1623.TW` v1/v2 都有 `refreshed_from_report`，但舊 snapshot 沒有刷新前 gate 狀態；將 `after_refresh` 直接解讀成「刷新造成缺失」會把時間關係誤當成因果。
- `#責任` / `#語意含義`：data-only refresh 在寫入 snapshot 前保存 optional `quality_metadata_refresh_provenance`，只記錄三個 gate contract 的 `recorded_fields` 與 `missing_fields`。repair 只有在目前缺口被刷新前清單覆蓋時使用「刷新前已有品質證據缺口」與 `quality_metadata_before_refresh`，否則維持既有中性 after-refresh 分類；不從 artifact 重建 gate、不改 audit 分母、不觸發 rerun。
- `#可驗證性` / `#證據基礎`：先以 refresh integration、snapshot preservation、repair before/after classification 與 indexed audit serialization 取得 RED，再 GREEN；後續補跑 quality/audit/conformance、history/storage、import boundary、docs/HCS、frontend HTTP、compile/diff 與 live read-only probe。舊 1623 snapshot 不被回寫，預期仍維持中性分類。

## D3621 / reuse one snapshot context during report-row hydration

- `#差距分析` / `#偏誤辨識`：profile 證實 `row_to_report()` 對同一份 snapshot 重複讀取 7 次，100 筆列表 row 共 700 次；projection 也在 row mapper 與 `_content_credibility()` 重複計算，這是 read-only API hydration 的固定成本，不是資料品質差異。
- `#責任` / `#組成`：由 row mapper 建立一次 snapshot context，明確傳入 decision tracking、freshness、preview、company/memory/gate/integrity/text helpers，並用 sentinel 區分「尚未計算」與「已計算為 None」的 projection；不引入全域快取，也不改 storage、artifact、index、review、rerun、repair 或 queue ownership。
- `#可驗證性` / `#效用`：snapshot reuse regression 先 RED（`calls=7`）再 GREEN（`calls=1`）；tracking/temporal `12 passed`、history/storage/preview `167 passed`、quality/credibility `118 passed`、補充跨層 `69 passed`、import boundary `503 passed`、docs/HCS `136 passed`、frontend HTTP `6 passed`、target detector `856 passed`，compile/diff check 通過。canonical profile 由 `1.256s` 降至 `0.484s`，snapshot reads `700 -> 100`、projection calls `200 -> 100`；runtime reload 後 health/readiness、port 與 doctor 通過，live reports/historical/daily 約 `1.14s/0.50s/1.17s`，daily `165/165/2/98.79%`、repair detail 保持具體 evidence warning，沒有 snapshot、artifact、index、review、rerun、repair 或 queue mutation。

## D3620 / short-circuit target scanning for sufficient data confidence

- `#差距分析` / `#偏誤辨識`：profile 顯示歷史 row 與 quality audit 每筆都做 target-price 遞迴與大型 regex 掃描，但這份資料只在 score 低於 `EXPLICIT_TARGET_PRICE_MIN_SCORE=60` 時參與 blocking；高信心報告因此付出不影響結果的成本。
- `#責任` / `#效用`：先計算 data-confidence score，只有低信心分支才呼叫 `detect_explicit_target_price_fields()`；高信心的 passed/non-fresh warning 與低信心的 detected fields、阻斷細節完全保留，沒有把品質投影改成寫入或自動重跑。
- `#可驗證性` / `#證據基礎`：新增 monkeypatch regression 先 RED 再 GREEN；focused data-confidence `5 passed`、content core `34 passed`、target detector `856 passed`、quality/audit/conformance `194 passed`、history/storage `167 passed`、import boundary `503 passed`、docs/HCS `136 passed`、frontend HTTP `6 passed`，compile/diff check 通過。canonical profile 顯示 history 100 rows `2.575s -> 1.292s`、indexed quality audit 165 rows `1.646s -> 0.479s`；runtime reload 後 health/readiness、port 與 doctor 通過，live daily `165/165/2/98.79%`、repair detail 保持具體 evidence warning，沒有 snapshot、artifact、index、review、rerun、repair 或 queue mutation。

## D3619 / preserve concrete warning detail in repair queue

- `#差距分析` / `#偏誤辨識`：live 唯一 `action_required` 是 `2603.TW v4` 的 evidence caution；content credibility 已保存 `warnings[]`，但 repair item `_summary()` 只讀 `blocking_issues`、summary、message，操作員只能看到泛稱「內容可信度需確認」。
- `#語意含義` / `#受眾` / `#責任`：warning gate 在沒有 blocking detail 時取第一個 warning message，讓人工直接看到「證據抽查未完全通過，內容可信度需人工確認。」；blocking detail 仍優先，severity、priority、reason code、rerun/queue 邊界完全不變。
- `#可驗證性` / `#證據基礎`：新增 regression 先 RED 再 GREEN；repair queue `51 passed`、quality/audit/dashboard/review `118 passed`、完整 quality `325 passed in 5.02s`、import boundary `503 passed in 12.86s`、architecture/docs/HCS `138 passed in 3.69s`、frontend HTTP `6 passed in 3.16s`，compile/diff 通過。runtime reload 後 live 2603 detail、health/readiness/doctor 均符合預期，未寫 snapshot、artifact、index、review、rerun、repair 或 queue。

## D3618 / remove report target detection regex hot path

- `#差距分析` / `#偏誤辨識`：D3617 的 pattern ownership split 後，target detector 仍在每個候選欄位呼叫約 145k 字元的 non-price metric substitution；valid direct target 也沒有利用已證明的字串邊界，造成大型組合回歸成本過高。
- `#責任` / `#效用`：新增 `report_target_price_detection_fast_paths`，只負責 read-only cheap prefilters；time-to／queue metric 先用小 regex 排除，字串開頭的 direct currency target 先判定，commodity/input 前置語境、range/multi-target 和其餘語料保留既有 fallback。`price_parser_patterns` 只補足 `target 項 12 個` 等 fast-path permutation，不改價格抽取政策。
- `#可驗證性` / `#證據基礎`：先以 monkeypatch large pattern 取得 RED，再 GREEN；完整 target detector `856 passed in 12.26s`、price parser `851 passed in 211.42s`、quality `324 passed in 4.46s`、import boundary `503 passed in 11.46s`、frontend HTTP `6 passed in 2.79s`、architecture/docs/HCS `138 passed in 3.68s`，compile/diff check 通過。runtime reload 與 live health/readiness/doctor 驗證完成後再封存；本輪沒有 snapshot、artifact、index、review、rerun、repair 或 queue mutation。

## D3617 / restore module responsibility boundaries

- `#差距分析` / `#系統圖像`：import-boundary regression 讓長模組責任重新浮現：parser 把 pattern ownership 與演算法混在一起，evidence matrix 把 shape-safe construction 與 policy 混在一起，quality audit 則同時負責 orchestration 與 snapshot/artifact hydration。
- `#組成` / `#責任`：新增 `price_parser_patterns`、`content_credibility_evidence_matrix_support`、`report_quality_audit_rows` 三個內部 ownership module；保留 facade、audit envelope 與既有 callable injection，讓 monkeypatch、storage path、read-only audit 與 gate責任不漂移。
- `#可驗證性` / `#偏誤降低`：先以 import boundary RED 驗證結構債，再 GREEN；`503 passed`、price parser `851 passed`、content credibility inputs `870 passed`、quality/document `392 passed`、frontend HTTP `6 passed`、architecture/docs/HCS `138 passed`，compile/diff check 通過。大型組合回歸已通過 `1746` 個案例後因既有 regex 成本中止，保留 residual risk，不將部分結果寫成完整通過；runtime `healthz=ok`、`readyz=ready`，daily/historical `165/165/2/98.79%`、`1217/1217/115/90.55%`，100 筆 report rows 中 73 筆 projection。repair action 1 是既有 warning，本輪沒有 snapshot、artifact、index、review、rerun 或 queue mutation。

## D3616 / project current credibility rules without replacing saved evidence

- `#偏誤辨識` / `#證據基礎`：歷史/API row 只對齊 persisted content gate 與 final-audit，未使用 snapshot 內已保存的 `rerun_context.parsed`；新 deterministic 規則因此可能只在新 renderer 生效，歷史報告看不到相同檢查。
- `#責任` / `#語意含義`：新增 `content_credibility_projection` helper；只有 parsed/data/pipeline context 完整時唯讀評估，已記錄 gate 以 issue-level merge 保留舊 findings，缺 gate 維持 metadata missing，`available` 不等於 passed，也不建立任何 repair/rerun/queue side effect。
- `#可驗證性` / `#偏誤降低`：projection、report history、quality audit 與 docs RED→GREEN；跨層 `386 passed`，compile/diff check 通過；live 第一頁 `100` 筆有 `73` 筆 projection，persisted/current issue ids `0` 筆差異，daily `165` audited/`2` metadata missing/`98.79%`、historical `1217`/`115`/`90.55%`，health/readiness/doctor 通過。daily sample 的 1 筆 repair 是既有 2603 v4 evidence warning，本輪未寫 snapshot、artifact、index、review、rerun 或 queue。

## D3615 / surface confidence caps from shared calibration

- `#偏誤辨識` / `#證據基礎`：final-audit 已判定 `data_trust=partial/stale/unknown` 或跨來源衝突會降低信心上限，但 content credibility 只顯示 non-fresh，沒有指出 recommendation 的 raw/effective confidence 已超過 cap。
- `#責任` / `#語意含義`：重用 `build_confidence_calibration()` 與既有 conflict predicate；只有 `needs_downgrade` 產生 `confidence_exceeds_data_trust_cap` warning，保留 cap、分數與 reasons，`calibrated/aligned/unavailable` 維持非警示。
- `#可驗證性` / `#偏誤降低`：先取得 integration RED，再 GREEN focused content/calibration `37 passed`、跨層 quality/document `500 passed`；live `partial + 9/10` 產生 cap `7/10` warning，daily `165/2/98.79%`、current artifact 三 fields、repair action `0`、health/readiness/doctor 通過，保留 read-only mutation boundary。

## D3614 / require evidence for every existing structured conclusion

- `#偏誤辨識` / `#證據基礎`：evidence matrix builder 已建立 `估值結論` 與 `護城河評分`，但 content credibility 只檢查 `最終投資建議`；缺 row 或 failed row 會被錯誤當成沒有問題。
- `#拆解問題` / `#責任`：依 parsed `recommendation`、`price_targets`、`moat_scores` 條件式建立 coverage requirements；每個 row 都要求 usable status 與非空 basis，缺少結論時不創造要求，issue 分別保留 `missing_*_evidence`／`unusable_*_evidence`，仍由 evidence_exit_gate 負責數字抽查。
- `#可驗證性` / `#偏誤降低`：先取得兩個 RED，再 GREEN focused content `32 passed`、跨層 quality/document `496 passed`；live 完整/缺估值/failed moat 三種 smoke 均符合預期，daily `165/2/98.79%`、current artifact 三 fields、repair action `0`、health/readiness/doctor 通過，保留 read-only mutation boundary。

## D3613 / surface recommendation targets outside scenario range

- `#偏誤辨識` / `#證據基礎`：final-audit 已用三情境範圍檢查 12 個月目標價，但歷史/API content credibility trace 沒有這個 warning；只通過主要目標方向與情境排序，仍可能把遠離估值帶的結論顯示成沒有可信度警示。
- `#拆解問題` / `#責任`：重用既有 target-price parser 與 canonical bear/base/bull candidates，只有 12 個月與三情境都可解析才計算 `bear * 0.7` 到 `bull * 1.3`；超出產生 `recommendation_target_outside_scenario_range` warning，缺值略過，不把 read-only projection 變成 final-audit blocker 或 rerun/repair side effect。
- `#可驗證性` / `#偏誤降低`：先取得 integration RED，再 GREEN `28 passed`；跨層 quality/document `494 passed`，live smoke 確認 NT$200 超過 `56.0..182.0` 時產生 warning，daily `162/2/98.77%`、current artifact 三 fields、repair action `0`、health/readiness/doctor 通過。runtime reload 接續一筆既有 watchlist job，使 audit 分母由 160 變 162，保留為環境背景，不歸因於本次 patch。

## D3612 / reject empty or failed recommendation evidence rows

- `#偏誤辨識` / `#證據基礎`：`claim=最終投資建議` 的存在被錯當成 evidence coverage；failed/unknown row 或空 basis 仍能回傳 passed，會讓人工看到錯誤綠燈。
- `#責任` / `#語意含義`：只在 content credibility matrix gate 要求 usable status `success`、`skipped_fresh_cache`、`degraded_enrichment` 與非空 basis；不把 matrix warning 升級成 evidence_exit_gate rejected，維持兩者責任分離。
- `#可驗證性` / `#偏誤降低`：failed evidence 與 empty basis 先 RED，再 GREEN `29 passed`；跨層 quality/document `490 passed`，live smoke 兩種不可用 row 都產生 `unusable_final_recommendation_evidence` warning，daily `159/2/98.74%`、current artifact 三 fields、repair queue `0`、health/readiness/doctor 通過，保留既有 mutation boundary。

## D3611 / preserve content-credibility evidence in artifacts

- `#差距分析` / `#責任`：snapshot/API 已有 `content_credibility`，但 execution summary 沒有獨立 marker；`read_artifact_quality_summary()` 因此把現有報告的內容可信度證據漏掉，人工核對只能看到其他兩個 gate。
- `#組成` / `#可驗證性`：新增 shared `Content credibility` status/summary 到 Markdown/HTML，並以 read-only marker parser 相容既有 `內容一致性` reading-notice 行；不由 artifact text 重建或改寫 persisted gate。
- `#偏誤降低` / `#來源品質`：先取得三個 RED，再 GREEN artifact/renderer `71 passed`、跨層 quality/document `431 passed`；runtime reload 後 daily/current historical 維持 `158/2/98.73%`，兩筆 current artifact summary 都辨識三個 quality fields，repair queue `0`、health/readiness/doctor 通過。缺 metadata 分母未被 artifact marker 假裝清除，保留 snapshot、artifact、review、rerun、queue mutation boundary。

## D3610 / retain horizon-sequence evidence in credibility output

- `#差距分析` / `#責任`：final-audit 已有 3/6/12 個月時序規則，但 content credibility 沒有自己的 trace；raw final-audit 缺失時，歷史/API projection 只剩主要目標價方向，可能漏掉中期目標倒退。
- `#組成` / `#來源品質`：新增 `content_credibility_horizons`，重用 `forward_consistency_checker.check_target_price_sequence()`；只對至少兩個可解析且具方向性的 horizon 產生 `horizon_target_sequence_conflict` warning，不重建缺值、不改 final-audit critical 或 queue 行為。
- `#可驗證性` / `#偏誤降低`：先取得 integration RED，再 GREEN；跨層 quality 回歸 `319 passed`，live smoke 產生 `horizon_target_sequence_conflict` warning；daily 與 current historical 分別以 `all_indexed_reports/latest_per_ticker_pipeline`、`all_historical_indexed_reports/all_indexed_versions` 驗證為 `158/2/98.73%`，repair queue `0`，health/readiness/doctor 通過，維持 read-only mutation boundary。

## D3609 / do not overstate confidence without evidence

- `#偏誤辨識` / `#證據基礎`：`not_recorded` 被當成「不矛盾」而 passed，會讓高信心結論繞過 evidence gate 缺口；`NaN` 只是輸入正規化，不是證據通過。
- `#語意含義` / `#責任`：新增 `high_confidence_unrecorded_evidence` warning，只在 confidence `>=8/10` 時升級；保留 rejected + high confidence 的 blocked，並不把未記錄證據假裝成 rejected。
- `#可驗證性` / `#來源品質`：先取得 evidence-confidence RED，再 GREEN `4 passed`；跨層 quality/conformance `318 passed`，live warning smoke、daily/current historical `157/2/98.73%`、repair queue `0`、decision queue `2`、health/readiness/doctor 均通過，維持既有 mutation boundary。

## D3608 / do not pass unknown recommendation directions

- `#偏誤辨識` / `#合理性`：alignment 只有「買入／偏空／持有」分支；未知 label 有現價與目標價時會直接穿過所有分支，形成「未檢查」卻顯示 passed 的錯誤綠燈。
- `#責任` / `#語意含義`：沿用 `CANONICAL_RECOMMENDATIONS`，content credibility 只記錄 `unrecognized_recommendation_label` warning 並停止方向比較；final-audit 仍獨立負責允許值 structural block，不把兩個 gate 合併。
- `#可驗證性` / `#來源品質`：先取得 alignment RED，再 GREEN focused content `27 passed`、跨層 quality/conformance `317 passed`；live unknown-label smoke、daily/current historical `157/2/98.73%`、queue、health/readiness/doctor 均通過，維持 read-only 與 mutation boundary。

## D3607 / validate long-term scenario target ordering

- `#偏誤辨識` / `#差距分析`：單一主要目標價方向通過，不代表熊／基本／牛情境帶自洽；目前 evaluator 原本完全沒有檢查這個既有 parsed input。
- `#拆解問題` / `#責任`：沿用既有 target-price parser，新增 canonical scenario candidate 與 pairwise order evaluator；倒置 pair 產生 `scenario_target_order_conflict` blocked，不可解析值產生 `unparseable_scenario_target` warning，缺值不自行補推，v4 不受長線情境規則干擾。
- `#可驗證性` / `#來源品質`：三個情境案例先取得 RED，再 GREEN `21 passed`；跨層 quality/conformance lane `315 passed`，live daily/current historical `157/2/98.73%`、v4 skip semantics、health/readiness/doctor 均通過，維持 read-only gate 與既有 mutation boundary。

## D3606 / hydrate only the selected version scope

- `#最佳化` / `#變數分析`：D3605 的版本篩選已正確改變結果範圍，但 code path 仍先讀全量 snapshot/artifact；current-only live cold request 約 `2.2s`，主要成本在讀取而不是版本分類。
- `#拆解問題` / `#責任`：把 latest-per-ticker/pipeline 判定抽成共用 index-row helper，先縮小 rows，再交給既有 cache/storage hydration；完整報告仍保留在 current scope 分母，review/missing-field 才是缺口集合篩選。
- `#可驗證性` / `#來源品質`：loader-scope regression 先取得 RED，再 GREEN；live current `519ms/186ms`、scope 數字、runtime health/ready 與既有跨層測試共同核對，未改 mutation boundary。

## D3605 / focus current-version quality gaps without changing coverage semantics

- `#差距分析` / `#詮釋框架`：live historical `115` 筆缺口中只有 `2` 筆屬目前 ticker/pipeline 最新版本；只有摘要標記仍不足以讓人工核對快速聚焦目前風險。
- `#溝通設計` / `#責任`：新增 `version_status=current|historical|unknown` GET filter、`report_version_status_filter` 回應欄位與 history 按鈕；版本範圍保留完整報告分母，review/missing-field 仍是後續 gap-only intersection，避免 coverage 被意外改寫。
- `#可驗證性` / `#來源品質`：backend、route、history renderer/module 與 static contract 先取得 RED，再 GREEN；後續完成完整 quality/history、HTTP、runtime、browser 與 remote push 核對。

## D3604 / distinguish current and historical quality gaps

- `#差距分析` / `#情境脈絡`：live historical audit 有 `115` 筆缺口，但 daily latest scope 只有 `2` 筆；沒有版本標記時，`90.52%` historical coverage 會被誤讀成目前報告仍同樣缺 gate。
- `#溝通設計` / `#責任`：indexed audit 依 report index 的 latest-per-ticker/pipeline 結果附 `report_version_status=current|historical|unknown`，envelope 增加 `quality_metadata_missing_by_version_status`，history target 顯示版本新舊；只改善讀取脈絡，不新增 review、rerun、queue 或 artifact mutation。
- `#可驗證性` / `#來源品質`：先以 backend、shared evidence、history renderer RED 鎖定版本狀態缺失，再 GREEN；full quality/history suite、live current-vs-historical scope、browser 1440/390 均已核對，remote push 於本批最後完成。

## D3603 / separate context availability from rerun execution strategy

- `#拆解問題` / `#來源品質`：live item 同時具備 `artifact_rerun_context_status=present` 與 freshness `needs_rerun`；但 `report_rerun_service` 對這種 snapshot 明確回 `409` 要求完整重跑，原本把 context availability 寫成「可嘗試只重跑」會讓操作員走到必然失敗的 final-agent 路徑。
- `#決策樹` / `#責任`：保留 `rerun_context_status` 描述上下文是否可查，新增 `rerun_execution_status` 描述實際策略；`full_rerun_required` 優先於 artifact fallback。preview 停用 final-agent button、保留完整重跑；API、gate、review、queue 與 mutation boundary 不變。
- `#溝通設計` / `#可驗證性`：共用 evidence context 把「上下文可查」與「重跑策略」分開顯示，stale notice 補上「請使用完整重跑」。核心 audit `78 passed`、preview `109 passed`、frontend quality/history `145 passed`；本批跨層品質/預覽 `332 passed`、HTTP E2E `41 passed`、文件/HCS `135 passed`、視覺 `2 passed`，live daily item、cache-busted assets、Chromium 1440px/390px 與 console 均完成核對，待 commit/push 後做 remote 一致性驗證。

## D3602 / surface rerun-context availability in shared quality evidence

- `#受眾` / `#語意含義`：live daily audit 已正確區分 `snapshot_rerun_context_status=missing` 與 `artifact_rerun_context_status=present`，但 daily、history、preview 共用 helper 只顯示 artifact 摘要，操作人員無法直接知道可嘗試既有局部重跑 fallback。
- `#溝通設計` / `#責任`：共用 `report_quality_evidence.context()` 對 `present|partial|missing|artifact_fallback_available` 產生白話 rerun-context 文案；`artifact_fallback_available` 明示「可嘗試」而非保證，並保留「artifact 不代表 gate 已通過」與人工核對警示，不改 `recommended_action`、`blocks_auto_rerun` 或 queue/review mutation boundary。
- `#可驗證性` / `#來源品質`：先以 1 個前端 RED 回歸鎖定缺少 `rerunContextText`，再 GREEN；品質跨層 suite `85 passed`、helper `node --check`、`git diff --check`、live asset cache-bust、daily API 與 runtime doctor 均通過。下一步仍需完成 commit/push 後的遠端一致性驗證。

## D3601 / distinguish snapshot context loss from Markdown fallback

- `#偏誤辨識` / `#來源品質`：D3600 的 `rerun_context_status=missing` 只看 snapshot；全量 artifact scan 顯示 `115/115` 缺口都有 Markdown 且前序 Agent sections 完整，若不再分層會把可用 fallback 誤報成必須完整重跑。
- `#詮釋框架` / `#溝通設計`：audit item 新增 `snapshot_rerun_context_status`、`artifact_rerun_context_status`，aggregate `artifact_fallback_available` 明示可嘗試既有 final-agent partial rerun；detail 不再宣稱「一定不能局部重跑」，仍要求核對 artifact/freshness，並維持 manual review/auto-rerun boundary。
- `#最佳化` / `#可驗證性`：quality audit `22 passed`、repair/review `56 passed`、frontend quality `6 passed`、import boundary `5 passed`、文件契約 `138 passed`；同一 Markdown 的兩次讀取合併為單次 cache lookup。正式 runtime reload 後 health/readiness/doctor 通過，live first item 確認 aggregate `artifact_fallback_available`；最後一次 canonical audit 為 `1220` verified versions、coverage `90.57%`、缺口 `115`，沒有新增 mutation。

## D3600 / expose rerun-context availability in quality audit

- `#拆解問題` / `#證據基礎`：對 live `115` 筆三 gate 缺口做 context inventory，`analyses`、`structured_outputs`、`parsed`、`evidence_matrix` 全部為空，且 `needs_rerun=115`、`refreshed_without_analysis_rerun=115`；既有「人工查看」detail 沒有說明局部重跑不可用。
- `#溝通設計` / `#責任`：quality repair item 與 historical audit item 新增 `rerun_context_status`，缺少原始上下文且確實需重跑時追加 `rerun_context_missing`；detail 明示安排完整重跑。`recommended_action=manual_review`、`blocks_auto_rerun=true`、artifact/gate/review/queue boundary 不變。
- `#可驗證性` / `#來源品質`：先取得 audit projection RED，再 GREEN；repair queue `50 passed`、quality audit/review `27 passed`、frontend quality `6 passed`、import boundary `5 passed`、文件契約 `138 passed`。正式 runtime reload 後 health/readiness/doctor 通過，live first item 確認 `rerun_context_status=missing` 與 `rerun_context_missing`；最後一次 canonical audit 為 `1221` verified versions、coverage `90.58%`、缺口 `115`，沒有新增 artifact/index/review/queue mutation。

## D3599 / preserve rerun context through data refresh

- `#拆解問題` / `#責任`：refresh context 原本只帶 data、quality gate 與 `evidence_matrix`，沒有帶回 snapshot 的 nested `rerun_context`；`build_data_snapshot()` 依 top-level 空輸入重建後，既有 Agent analyses、structured outputs、parsed recommendation 與 pipeline metadata 會消失，Markdown fallback 可能掩蓋此缺口。
- `#偏誤降低` / `#來源品質`：refresh 現在只保留原 nested context 並交給既有 sanitizer；`sanitize_rerun_context()` 只有在 caller 沒有 top-level 同名欄位時才 fallback 到 nested context，避免把新分析 context 覆蓋成舊資料。不重新跑模型、不改 quality gate、artifact/index、review 或 queue。
- `#可驗證性` / `#證據基礎`：先新增 refresh preservation assertion 取得 `1 failed`，再 GREEN；refresh/diff `14 passed`、完整 data-trust `182 passed`、局部 rerun `5 passed`、import boundary `16 passed`、文件契約 `138 passed`。正式 runtime reload 後 `healthz=ok`、`readyz=ready`；最後一次 live historical audit 為 `1223` 份 verified versions、coverage `90.6%`、缺口 `115`，沒有新增 artifact/index/review/queue mutation。

## D3598 / preserve evidence matrix through data refresh

- `#拆解問題` / `#證據基礎`：本輪初始 historical audit 觀測 `1228` 份 verified snapshot、`115` 份三 gate 缺口，且 `after_refresh=115`；抽查 1623 v2 的 data snapshot、HTML/Markdown 與 refresh code，確認 artifact 有舊版 conformance/evidence 摘要，但 snapshot 的 `evidence_matrix` 在 refresh 後被重建成 `[]`。
- `#偏誤降低` / `#責任`：不把既有 artifact marker 重建成 gate，也不在 refresh 時重新宣稱分析通過；只讓 `report_refresh_service` 將原 snapshot 的 `evidence_matrix` 帶入 `build_data_snapshot()`，並讓 builder 對 explicit matrix 做 sanitized preservation，維持原有新報告 matrix builder fallback。
- `#可驗證性` / `#來源品質`：先新增保存行為測試取得 `1 failed`，再 GREEN；refresh/diff `14 passed`、content credibility evidence `8 passed`、report data-trust matrix `30 passed`、snapshot/data-trust `39 passed`。正式 runtime reload 後 `healthz=ok`、`readyz=ready`；live historical read-only audit 為 `1225` 份 verified versions、coverage `90.61%`、缺口 `115`，沒有新增 artifact/index/review/queue mutation。

## D3597 / credibility price-parser fast paths

- `#最佳化` / `#變數分析`：D3596 後完整 `870` case matrix 雖能通過，但同一輪 durations 顯示 service-queue 語料最高 `39.21s`，`time-to` 語料也重複進入大型 `NON_PRICE_METRIC_*` regex；瓶頸是輸入形狀與 fallback 分流，不是測試數量本身。
- `#偏誤降低` / `#責任`：新增三個保守 fast path：帶數量單位的 `time-to` 指標直接判為非價格、字串開頭且有明確貨幣／單位或區間的 `target price` 直接讀取、`queue items reached N` 直接判為非價格。商品原料價格、估值倍數、目標價調整／修正版與帶前置上下文的 marker 都排除在 fast path 外，繼續走既有完整 parser；不改 report artifact/index、snapshot、gate 或 queue。
- `#可驗證性` / `#來源品質`：先以三個 monkeypatch RED 鎖住「不得觸碰大型 pattern」，再 GREEN；完整 inputs `870 passed in 220.14s`，相同命令前一版 `578.52s`，約減少 `62%`。品質/preview `218 passed`、refresh/data-trust/evidence `211 passed`、文件/架構契約 `138 passed`，diff check/compile 通過；正式 runtime reload 後 `healthz=ok`、`readyz=ready`，live 2603 報告 `content_credibility.status=passed`。

## D3596 / temporal token contamination in credibility price parsing

- `#證據基礎` / `#偏誤辨識`：掃描 `1216` 份 snapshot、其中 `1073` 份 v4 parsed trade setup 後，發現 target/stop 字串確實含有日期或週期數字；live 例子包括 `2026 年 7 月 31 日價格點 204.0`、`7 月 31 日關鍵支撐位 36.0` 與 `2026 年 4 月關鍵支撐位 85.0`。舊 `first_price()` 會取到 `2026.0` 或 `7.0`，進而把交易計畫誤判成方向矛盾。
- `#責任` / `#語意含義`：在 `content_credibility_inputs.first_price()` 的輸入邊界先移除明確日曆日期與週期 token，再使用既有 `extract_price_numbers()`；只修正數值抽取，不改 target/stop 欄位語意、trade direction policy、snapshot/index、artifact、review、rerun 或 queue。
- `#可驗證性` / `#偏誤降低`：三個核心案例先取得 RED，補充月日格式後新增核心案例 GREEN `4 passed`（focused command 共 `5 passed`，含既有非有限數案例）；內容可信度/品質/repair `92 passed`、preview/reading `126 passed`、refresh/data-trust `196 passed`、alignment/evidence `15 passed`、import boundary `3 passed`。重啟正式 runtime 後 `/healthz`、`/readyz` 通過，live 2603/2324/2375 停損值為 `204.0/36.0/85.0`。大型 inputs 解析矩陣跑到 `837 passed`、約 26 分鐘後中止，未宣稱完整通過，列為 residual risk。

## D3595 / final-audit snapshot persistence

- `#證據基礎` / `#系統圖像`：D3594 的 live evidence 顯示歷史 projection 可從 conformance 對齊，但新 renderer 的 data snapshot 仍沒有 raw `final_audit`，refresh service 也沒有明確帶回欄位，下一次刷新可能失去 audit trace。
- `#責任` / `#限制條件`：snapshot 只新增 sanitized optional `final_audit`，不把它列入 legacy required keys；refresh 只沿用既有 audit，不重跑、不改 provider、不回寫 index/review/queue，也不回填既有舊檔案。
- `#可驗證性` / `#偏誤降低`：renderer/snapshot/refresh RED `3 failed` 後 GREEN `3 passed`；data-trust/refresh `194 passed`、content/quality/repair `88 passed`、snapshot integrity smoke `true`，正式 runtime health/readiness 與 daily/historical scope 均通過。舊 snapshot 仍由 D3594 projection 覆蓋語意落差。

## D3594 / historical final-audit reconciliation

- `#偏誤辨識` / `#來源品質`：D3593 只修正新 renderer；live `1216` 份既有 snapshot 沒有 raw `final_audit`，但 `report_conformance` 已保留 final-audit step，造成 `21` 筆 `passed credibility` 與 warning/blocked final audit 的語意矛盾。
- `#責任` / `#語意含義`：新增共享 projection，只有在已記錄的 `content_credibility` 與同一 snapshot 的 conformance final-audit evidence 矛盾時升級讀取結果；缺少 content metadata 仍維持缺口，不把 artifact 摘要或 conformance step 回寫成新 gate payload。
- `#可驗證性` / `#偏誤降低`：RED `2 failed` 後 GREEN `38 passed`、相鄰 `240 passed`；local `1216` rows 的 passed/non-passed mismatch 為 `0`，API `/api/reports` 可見 `warning/final_audit_warning`，daily/historical scope、runtime health/readiness 通過。raw final-audit persistence 未在本批擴張，列為後續獨立決策。

## D3593 / final-audit credibility alignment

- `#證據基礎` / `#差距分析`：規格把 `final_audit` 列為內容可信度輸入，但現行 evaluator 只讀 parsed target、data trust、evidence gate 與 matrix；live 舊報告也顯示 final audit 可能有重大矛盾，因此不能只依 conformance 另一個 step 代替內容可信度 trace。
- `#責任` / `#語意含義`：新增專用 read-only projection，critical/阻斷狀態會讓 `content_credibility` blocked，warning/其他非通過狀態為 warning，corrections 只代表修正紀錄不升級；不重複寫 final audit、不改 renderer side effect 或 review/queue 邊界。
- `#可驗證性` / `#偏誤降低`：先取得兩個 final-audit RED，再 GREEN `3 passed` 新增行為、`122 passed` 相關品質/conformance lane 與 `583 passed` 本批跨層 suite；runtime smoke、daily `160/2/98.75%`、historical browser `1216/115/90.54%`、1440px/390px overflow 與 console 均收斂。大型 inputs 解析集仍未完成，保留為獨立 residual risk。

## D3592 / refresh attribution semantics

- `#證據基礎` / `#偏誤辨識`：live 缺口的 `refreshed_from_report` 只證明 snapshot 有刷新歸因；refresh service 會保留既有品質 maps，因此「未保留」不能演繹成 refresh 造成遺失。
- `#語意含義` / `#責任`：repair detail 改用「目前未記錄」並明示無法由現有 metadata 判定成因；helper、history、watchlist 將 `after_refresh` 顯示為「有刷新歸因」。不改 internal enum、gate predicate、artifact 重建或 review/queue side effect。
- `#可驗證性` / `#偏誤降低`：backend/frontend RED `2 failed` 後，focused quality suite `255 passed`、跨層 suite `461 passed`；live health/readiness、三個 asset、daily/history scope 均收斂。browser 以 390px/1440px 驗證 history/watchlist target 無水平溢出，兩入口可見「有刷新歸因」、舊文案不存在且 console 無錯誤；detail 保留「無法由 metadata 判定缺口是否由刷新造成」的限制。三個品質 asset 使用 `20260820-refresh-attribution` cache-buster。

## D3591 / preview badge evidence-detail source

- `#來源品質` / `#差距分析`：preview badge 的 policy detail 與 history/watchlist 共用 evidence context 目前是兩個取值入口；policy wording 一旦先更新，preview 的 title/aria/data context 可能偏離同一報告的人工核對脈絡。
- `#責任` / `#語意含義`：preview 保留 compact inline badge 與既有 filename/pipeline 導覽，僅將 `report_quality_evidence.context(report).detail` 設為優先來源；不把 target `<small>` renderer 套用至 badge，也不把 artifact marker 轉成 gate verdict。
- `#可驗證性` / `#偏誤降低`：新增 policy-detail drift RED→GREEN regression，`1 failed` → focused `4 passed`；跨層 suite `399 passed`，Node syntax、文件契約與 diff check 通過。live health/readiness、preview asset、daily `160/2/98.75%` 與 browser scoped navigation、390px/1440px overflow、console 均收斂；更新 preview asset cache-buster。

## D3590 / shared target-context renderer

- `#拆解問題` / `#組成`：preview 的 detail 與 history/watchlist 的 target HTML 都需要同一份 evidence 語意，但不應把 badge 與 target 的不同容器硬合併；抽出 `renderTargetContext()` 只統一三段文字順序與小字 projection，保留 consumer 的容器與既有 class map。
- `#溝通設計` / `#語意含義`：renderer 的 `text` 用於 title/aria 等完整脈絡，`html` 依序輸出 review status、evidence context、artifact warning；watchlist 保留既有 class，history 使用共用 class，避免以 artifact marker 生成 gate verdict。
- `#責任` / `#限制條件`：只讀取既有 item 的 `quality_review` 與 `report_quality_evidence` context，不寫 review ledger、不改 API、artifact/index、rerun 或 daily queue；fallback 保留在 consumer 內，單獨載入 renderer 的測試與 legacy 呼叫仍可工作。
- `#可驗證性` / `#偏誤降低`：先取得 `2 failed, 1 passed` RED，再 GREEN 核心前端 `35 passed`、跨入口 `398 passed`、Node syntax、size guard、文件契約與 diff check；live `/healthz`/`/readyz`、asset `200`、daily `160/2/98.75%`、scoped history `1/1/0%`，並以兩入口的 DOM 順序、aria/title/data context、390px/1440px overflow 與 console 完成驗證。

## D3589 / daily target evidence hierarchy

- `#受眾` / `#差距分析`：live daily target 的 status、evidence context 與 artifact limitation 原本共用一個小字區塊，觸控操作員必須靠分號拆解，無法快速辨識目前審核狀態與不可推導的 evidence。
- `#溝通設計` / `#語意含義`：target 依序呈現「審核狀態」→「結構化缺口／來源／artifact」→「artifact 摘要僅供人工核對，不代表 gate 已通過」，三段各有 class 與視覺層級；完整 detail 仍留在 title/aria/data context。
- `#責任` / `#倫理判斷`：只改 watchlist renderer 與 CSS presentation，沒有把 artifact marker 轉成 gate verdict，也沒有改 filename/pipeline navigation、review mutation、ledger、artifact/index、rerun 或 queue。
- `#可驗證性` / `#限制條件`：先取得 `2 failed, 25 passed` RED，再 GREEN `27 passed` targeted 與 `398 passed` 跨層 suite；以行數、Node syntax、cache-buster、live target dimensions、desktop/mobile overflow、aria、asset 與 console 驗證，保留三入口共用 renderer 作下一個觀察點。

## D3588 / daily quality summary parity

- `#受眾` / `#差距分析`：live 今日工作台的 quality audit summary 在手機上是一段長文字，雖然沒有水平溢出，操作員仍需自行拆解 scope、缺口、審核與 artifact evidence；history 已有的 scan order 應延伸到 daily。
- `#溝通設計` / `#語意含義`：daily board 先顯示「全量報告品質」scope，再以獨立項呈現缺口總數、缺 gate、模式、審核狀態、人工進度、來源、artifact 與 coverage；target 仍保留可見 warning 與 aria detail。
- `#責任` / `#倫理判斷`：只改前端 projection 與 responsive layout，`auditText` 仍保留作 unavailable/legacy fallback；不改 audit API、coverage 分母、review ledger、artifact/index、rerun 或 daily decision queue。
- `#可驗證性` / `#限制條件`：先取得 `2 failed, 25 passed` RED，再 GREEN `27 passed` targeted suite；以行數、Node syntax、cache-buster、live dashboard、desktop/mobile overflow、warning/aria 與 console 驗證，保留 target 內文密度作下一個觀察點。

## D3587 / filter-scope-first audit summary

- `#受眾` / `#偏誤辨識`：combined filter 的數字若先出現、active scope 後出現，操作員可能把 subset coverage 或缺口數讀成全庫結論；scope 必須靠近摘要起點。
- `#溝通設計` / `#語意含義`：history renderer 將「審核範圍／缺口範圍」各自以醒目摘要項呈現，欄位、模式、審核狀態、進度與來源拆成獨立項；mobile `<=600px` 使用單欄 grid，desktop 保持可利用橫向空間。
- `#責任` / `#倫理判斷`：這是 read-only UI projection，只重排既有 audit envelope，不重算 coverage、不改分母、不寫 review ledger，也不把 artifact marker 變成 gate verdict。
- `#可驗證性` / `#限制條件`：先取得 `2 failed, 152 passed` RED，再 GREEN targeted `154 passed`；以行數、Node syntax、cache-buster、live combined scope、desktop/mobile overflow 與 console 驗證，保留 daily/history parity 作下一個觀察點。

## D3586 / visible artifact limitation and accessible target context

- `#受眾` / `#差距分析`：D3585 的 artifact limitation 雖存在於 detail、title 或 data attribute，觸控操作員與螢幕閱讀器使用者未必會看到；品質缺口需要在 target 本身可掃讀，不能只依賴 hover。
- `#溝通設計` / `#語意含義`：共用 evidence helper 分出短版 `targetWarning`，history 與 watchlist target 以可見小字呈現「artifact 摘要僅供人工核對，不代表 gate 已通過」，並把同一句納入 aria-label；preview badge aria-label 同步保留完整 detail。
- `#責任` / `#倫理判斷`：warning 是 evidence presentation，不是 gate verdict；不從 artifact marker 推導通過、不改 quality predicate、不寫 review ledger、不修 artifact/index、不 enqueue rerun 或 daily queue。
- `#可驗證性` / `#限制條件`：先以 aria 與 visible warning assertions 取得 RED，再 GREEN `184 passed` targeted frontend/cache-buster suite 與 `398 passed` 跨層 suite；Node syntax、文件契約、diff check、live asset、desktop/mobile browser 與 runtime health/readiness 均收斂，並保留 filter scope 文字密度作為下一個觀察點。

## D3585 / shared clickable evidence guidance

- `#拆解問題` / `#系統圖像`：preview、history、watchlist 都展示同一份品質缺口，但原本各自組字串，容易讓操作員在不同入口看到不同 provenance 或 artifact 限制。
- `#組成` / `#語意含義`：新增 `report_quality_evidence_helpers.js` 作為共同語意層；preview badge、history target 與 watchlist target 共用相同的 structured metadata、刷新來源、artifact marker 與人工核對限制。
- `#形塑行為` / `#溝通設計`：verified snapshot 的「結構化品質缺口」badge 變成可點擊導引，沿用既有 filename/pipeline scoped history audit；操作員能從正在查看的報告回到同一證據範圍，而不是自行重搜全庫。
- `#責任` / `#可驗證性`：click handler 只呼叫既有唯讀 `StockAgentOpenHistoricalQualityAudit`，不新增 review mutation；以 RED→GREEN、helper load order、browser target contract、live scope 與 console 驗證，D3586 再補上重新整理後的可見 warning/accessibility 邊界。

## D3584 / preview evidence boundary

- `#證據基礎` / `#系統圖像`：同一 verified snapshot 的 structured gate map 可缺失，而 artifact 仍有 marker；report list/preview 若只顯示 generic badge，操作員無法知道兩層 evidence 的差異。
- `#責任` / `#限制條件`：以 `report_quality_evidence` 共用 read-only lookup 給 audit 與 report row；preview policy 只標示缺口與 artifact 可查，不從 marker 重建 gate，也不改 artifact/index、review ledger、rerun 或 queue。
- `#偏誤辨識` / `#溝通設計`：badge/detail 明確寫「結構化品質缺口」與「artifact 摘要僅供人工核對，不代表 gate 已通過」，和 history/daily target 使用同一語意。
- `#可驗證性` / `#來源品質`：以 RED→GREEN、既有 audit storage seam 回歸、preview/static suites、live `/api/reports`、browser tooltip/console、coverage 與 ledger count 驗證；未執行 review mutation。

## D3583 / structured metadata versus artifact evidence

- `#證據基礎` / `#語意含義`：live `143` 筆缺口的 `missing_quality_fields` 是結構化 snapshot metadata 未記錄；同一筆可另有 artifact 摘要，後者只是人工核對 evidence，不代表 gate 已通過。
- `#偏誤辨識` / `#溝通設計`：daily/history target 原本只並列「缺少」與「artifact 可查」，操作員可能把兩個層次合併解讀；改以「結構化缺口」與「artifact 摘要可查」明確分層。
- `#責任` / `#倫理判斷`：renderer 只呈現 API envelope 已有的兩種 evidence，不在前端重建 gate 或自動核准；review mutation、artifact/index、rerun 與 daily queue 邊界維持不變。
- `#可驗證性` / `#來源品質`：以 daily/history target RED→GREEN、cache-buster、Node syntax、size guard、跨層 tests、live payload 與 review ledger count 驗證；不執行 review mutation。

## D3582 / transient history state guard

- `#系統圖像` / `#差距分析`：session 恢復的是查詢 scope，不是報告內容；頁碼、preview 與追蹤 snapshot 若沒有明確生命週期，篩選切換後可能把上一個 ticker 留在新列表旁。
- `#限制條件` / `#偏誤降低`：把頁碼、preview、snapshot 視為 transient state；scope fingerprint 改變時清除它們，並以 snapshot request version 擋住晚到的舊 response，不擴大 session storage。
- `#責任` / `#制定策略`：`history_workspace` 統一負責 scope 變更的 UI reset；snapshot module 仍只負責載入與 render，backend/API、artifact/index、review ledger、rerun 與 daily queue 不變。
- `#可驗證性` / `#來源品質`：以 scope change RED→GREEN、in-flight snapshot response regression、cache-buster、Node syntax、跨層測試與後續 live read-only checks 驗證；不執行 review mutation。

## D3581 / whole history scope persistence

- `#系統圖像` / `#差距分析`：quality filter 已能恢復，但主搜尋與 pipeline 仍回到預設；history list、audit summary 與 API request 可能不是同一個 scope。
- `#組成` / `#溝通設計`：由 `history_filters` 集中保存搜尋、pipeline、建議、資料狀態與 include-versions，quality filter 維持自己的模組責任；refresh 後兩層一起恢復可見 scope。
- `#責任` / `#制定策略`：daily scoped navigation 透過既有 `setValues()` 覆蓋主 scope，quality module 的 reset 清除 quality scope；不在 app、watchlist 或 backend 重複保存狀態。
- `#可驗證性` / `#來源品質`：以整體 scope restore/override RED→GREEN、enum normalization、cache-buster、Node syntax、跨層測試、live asset/API/health/readiness 驗證；本批不執行 review mutation。

## D3580 / quality filter persistence boundary

- `#差距分析` / `#問對問題`：quality filter 是否要持久化不能只問「能不能留住」；browser refresh 需要恢復同一稽核範圍，daily scoped navigation 則必須清掉舊條件。
- `#限制條件` / `#偏誤降低`：只保存兩個白名單 enum 到 tab-scoped `sessionStorage`，不保存報告內容、搜尋字串或 revision；storage 失敗時維持既有 in-memory 行為。
- `#責任` / `#系統圖像`：`history_quality_audit` 擁有 filter state 與 reset boundary，workspace scoped navigation 只呼叫 reset，不自行複製 storage 邏輯；backend 仍是唯一 query 範圍來源。
- `#可驗證性` / `#來源品質`：以 reload restore/reset RED→GREEN、enum normalization、cache-buster、Node syntax、跨層測試、live asset/API/health/readiness 與 ledger count 驗證；本批不執行 review mutation。

## D3579 / combined audit scope semantics

- `#偏誤辨識` / `#語意含義`：live response 同時帶有 review status 與 missing field，但原 renderer 只顯示前者；這會把交集數字誤讀成單一篩選結果。
- `#組成` / `#溝通設計` / `#受眾`：新增雙重 scope summary，保留兩個 quick-filter 群組與雙重空集合語意，讓操作員能直接知道目前看的交集。
- `#責任` / `#倫理判斷`：backend 既有 AND filter 保持唯一資料範圍來源，前端只呈現 envelope 的兩個 normalized filter，不自行推算或寫入 review 狀態。
- `#可驗證性` / `#限制條件`：以 combined renderer RED→GREEN、backend AND contract、cache-buster、Node syntax、跨層測試、live read-only query 與 ledger count 驗證；本批不執行 review mutation。

## D3578 / missing quality field scope

- `#拆解問題` / `#差距分析`：live audit 已有三個 gate 的缺口 aggregate，但人工核對入口仍以所有缺口為集合；缺少「只看某一欄位缺口」的可驗證範圍。
- `#受眾` / `#語意含義` / `#溝通設計`：新增欄位快捷入口與「缺口範圍」文案，將 field-scoped coverage 與全庫 coverage 分開；目前欄位即使為零也保留回復入口，避免空集合卡死。
- `#責任` / `#倫理判斷` / `#偏誤降低`：backend 只在 current review attach 後投影 verified repair item 的缺口集合，與 review status 共同 GET 篩選；不把欄位缺口篩選誤做成修復、核准、rerun 或 daily queue action。
- `#可驗證性` / `#來源品質` / `#限制條件`：以 backend/route/frontend RED→GREEN、cache-buster、Node syntax、行數護欄、live exact query、health/readiness 與 review ledger count 驗證；本批不執行 review mutation。

## D3577 / scoped daily-to-history review navigation

- `#差距分析` / `#受眾`：daily 最新品質 target 已知道 filename、ticker、pipeline 與 pending 狀態，但原入口只開 preview 或泛用 history audit；操作員必須重新搜尋歷史缺口，且可能誤留在其他 review status filter。
- `#最佳化` / `#溝通設計`：新增「前往人工核對」，以 filename/pipeline 直接縮小 GET audit/list 範圍；workspace 同時重設 recommendation/data-trust/review-status、頁碼與 preview，讓入口語意就是「核對這一筆」。
- `#責任` / `#倫理判斷`：watchlist 只負責傳導 scope，history filter/workspace 負責套用查詢與狀態；不把導覽升格為 review mutation，不建立 queue、rerun 或 artifact/index 副作用。
- `#可驗證性` / `#限制條件`：先以三層 RED 鎖定 target markup、panel delegation、scope query 與 stale status reset，再驗證 cache-buster、live exact filename query、health/readiness 與 ledger；本批不執行 review mutation。

## D3576 / current revision visibility

- `#證據基礎` / `#來源品質`：live historical item 帶有 current `report_quality_revision`，但原 review control 沒有把它呈現給操作員；只看 ticker/模式/日期不足以核對 stale revision 風險。
- `#受眾` / `#溝通設計`：新增短版版本識別碼供掃讀，完整 revision 放在 title 與 aria context；不把長 hash 堆進主要操作文字，也不讓技術值遮住決策按鈕。
- `#責任` / `#倫理判斷`：版本提示只改善人工辨識，不成為 client authorization；server 仍負責 fingerprint、mutation token、current revision 與 append-only ledger。
- `#可驗證性` / `#限制條件`：先以長 revision fixture 鎖定短版與完整 accessible value，再驗證前端、cache-buster、live asset/readonly scope/ledger；本批不執行 review mutation。

## D3575 / explicit review write confirmation

- `#倫理判斷` / `#責任`：人工 review 是 append-only 寫入；填完理由不等於操作員已確認要留下決策。新增最後確認，取消時不進入 mutation call，也不把取消誤報成失敗或已儲存。
- `#受眾` / `#溝通設計`：確認訊息同時顯示決策、目前版本與 note，讓操作員在不可逆的 ledger append 前再次核對意圖；成功、失敗與取消三者保持不同語意。
- `#限制條件` / `#偏誤降低`：前端確認只是 UX safety gate，不取代 server mutation token、current revision、decision/note validation；不改 artifact/index、queue、rerun 或品質 gate。
- `#可驗證性` / `#來源品質`：先以 `confirm=false` 取得 `savedCount=1` RED，再 GREEN `16 passed`；live 只做 historical/daily GET、health/readiness、asset 與 review ledger count 核對，本批不執行 review mutation。

## D3565 / revision-scoped quality review progress

- `#證據基礎` / `#差距分析`：live historical audit 的 `143` 個缺 metadata row 全部沒有 current review event；若只顯示缺口數，無法區分待核對與已留下人工決策的報告。新增 `quality_review_by_status`，以 canonical review ledger 的 current revision state 作為唯讀 aggregate。
- `#語意含義` / `#受眾`：只對 missing-metadata rows 計數，`pending` 代表沒有當前 revision event，不代表品質 gate 通過或失敗；daily 與 historical 都顯示四種白話狀態，pipeline summary 保留同一分組，避免把完整報告或分頁 slice 混入審核分母。
- `#責任` / `#倫理判斷`：backend 負責 safe status normalization，frontend 只呈現 aggregate；不將 `approved_with_gap` 轉成完整、不寫回 artifact/index、不建立 rerun/repair/queue action，也不改既有 review POST 邊界。
- `#可驗證性` / `#限制條件`：TDD 先鎖定 missing-only、pipeline map 與兩個 UI 入口，再以品質跨層 suite、文件契約、Node syntax、Python compile、live historical/daily response、health/readiness 與 asset `200` 驗證；本批保持 read-only。

## D3566 / quality gap versus review actionability

- `#語意含義` / `#偏誤辨識`：`quality_metadata_missing_reports` 是 evidence gap 總數，不等於仍待人工核對；D3565 新增的 status map 已能辨識決策進度，UI 若繼續寫「待人工核對」會把 `approved_with_gap`、`rejected`、`deferred` 混成 pending。
- `#受眾` / `#溝通設計`：daily 與 historical summary 改成「品質 metadata 缺口」總數，並保留「審核狀態：待人工核對／已核准保留缺口／退回處理／已暫緩」的獨立摘要；操作員可同時看到資料缺口與目前處理狀態。
- `#責任` / `#倫理判斷`：只修改前端呈現與 cache-buster，不由 UI 猜測或改寫 review state，不把已核准缺口誤呈現為完成品質 gate，也不新增任何 artifact/index、rerun、queue 或 mutation 副作用。
- `#可驗證性` / `#來源品質`：以不一致 fixture 先得到 `4 failed`，修正後跨層 `951 passed`；同步驗證 cache-buster、Node syntax、Python compile、diff check 與 live audit map，確認數據沒有被文字修正影響。

## D3567 / daily target review context

- `#差距分析` / `#受眾`：daily payload 的兩個 missing-quality target 都有 `quality_review.status` 與 revision，但工作台按鈕只顯示 artifact marker；操作員知道有 evidence，卻不知道這一筆是否已核准保留缺口或仍待核對。
- `#溝通設計` / `#語意含義`：target 的可見小字、title、aria label 同步顯示「審核狀態：待人工核對／已核准保留缺口／退回處理／已暫緩」，並保留 artifact evidence；不把 status context 寫成 gate 結論。
- `#責任` / `#倫理判斷`：daily helper 只讀取並呈現 item state，歷史 workspace 仍是 review action 的唯一 owner；本批不新增 daily mutation、不改 revision、note、token 或 ledger。
- `#可驗證性` / `#來源品質`：approved-with-gap fixture 先得到 `1 failed, 12 passed`，修正後跨層 `951 passed`，並驗證專屬 cache-buster、資產 `200`、live pending item 與 review ledger count `0`。

## D3568 / historical review-status filter

- `#最佳化` / `#差距分析`：歷史版本有 `143` 個 pending 缺口，之後若逐筆留下 review event，單靠 pipeline/page 仍要翻過其他狀態；新增 `review_status` read-only filter，讓人工核對可以直接聚焦 pending 或某種已決策狀態。
- `#分析層次` / `#語意含義`：filter 在 attach current revision review 後套用，`review_status_filter` 明確回傳，filtered `audited_reports`、coverage denominator、missing counts 與 items 都只描述選定狀態，不把篩選結果誤讀成全庫總數。
- `#責任` / `#倫理判斷`：API/client/history module 只傳 GET query；review ledger、revision、artifact/index、rerun、queue 與 mutation token 邊界不變，status quick filter 不另造寫入入口。
- `#可驗證性` / `#來源品質`：backend/route/renderer/module RED 後 targeted `5 passed`、跨層 `953 passed`；同步鎖定 status button、cache-buster、pipeline/page regression，待重啟後以 live pending/approved filter 做範圍核對。

## D3569 / filtered quality coverage scope wording

- `#語意含義` / `#偏誤降低`：live pending filter 的 `0%` 是因為篩選集合本身全是缺口，不是整個歷史庫的品質結論；UI 改用「審核範圍」標籤，避免把 subset coverage 誤讀成 global coverage。
- `#受眾` / `#溝通設計`：pending、approved_with_gap、rejected、deferred 各自使用白話狀態名稱；只有 `review_status=all` 顯示「品質 metadata 完整度」，讓操作員先辨識數字的分母與閱讀範圍。
- `#責任` / `#限制條件`：這是 history renderer 的呈現修正，backend filtered envelope、review ledger、artifact/index、queue、rerun 與 mutation 邊界均不變；更新 renderer 專屬 cache-buster，避免舊 bundle 留在瀏覽器。
- `#可驗證性` / `#來源品質`：先以前端 fixture 取得 RED，再 GREEN targeted `9 passed`、跨層 `954 passed`；維持 renderer 99 行責任護欄，並以 Node syntax、diff check 與 live pending/all scope/asset response 作最終驗證。

## D3570 / review submission feedback and duplicate guard

- `#證據基礎` / `#差距分析`：live canonical review ledger 仍有 `143` 個 pending 缺口；既有 history control 只有 mutation call，沒有 in-flight 狀態或成功回饋，操作員無法從畫面分辨請求是否已落 ledger。
- `#偏誤降低` / `#系統動力學`：page-level lock 在第一次提交後立即阻擋同筆連點，button 同步設為 disabled/`aria-busy`，避免一次人工決策形成多筆 append-only event；server revision/token 邊界仍是最終防線。
- `#受眾` / `#溝通設計`：成功顯示「人工審核已儲存」，失敗顯示錯誤並恢復按鈕；不把人工決策寫成品質 gate pass，也不將 reload/loading 誤報成完成。
- `#責任` / `#限制條件`：修改只在 `history_quality_audit.js` 的 client interaction owner，API、review store、artifact/index、queue、rerun 與 mutation contract 不變；更新專屬 cache-buster 讓舊 bundle 不殘留。
- `#可驗證性` / `#來源品質`：先取得 duplicate-submit RED，再 GREEN `15 passed`；失敗路徑也確認 error toast 與 unlock，並以跨層 suite、Node syntax、diff check、live asset/health/readiness 與 ledger count 做收斂驗證。

## D3571 / recoverable zero-count review filter

- `#差距分析` / `#系統動力學`：review status filter 的 count 隨 ledger 變化；當目前狀態降為 `0` 時，原本的「只顯示非零狀態」規則會把目前按鈕與 all 入口一起移除，造成空集合不可恢復。
- `#語意含義` / `#偏誤降低`：目前狀態顯示 `（0）` 明確表示「此篩選目前無結果」，不把空集合誤報成狀態不存在；其他非目前零值狀態仍可隱藏，保持摘要簡潔。
- `#受眾` / `#溝通設計`：filtered view 永遠保留「全部審核狀態」，操作員完成最後一筆後可立即返回全量，不需要重新整理或猜測 URL。
- `#責任` / `#限制條件`：修正只在 status-filter helper，更新專屬 cache-buster；backend aggregate、review mutation、artifact/index、queue 與 rerun 不變。
- `#可驗證性` / `#來源品質`：先以 count=0 fixture 取得 RED，再 GREEN `10 passed`；維持 helper 97 行，並以跨層 suite、Node syntax、diff check 與 live asset/health/readiness 作最終驗證。

## D3572 / filtered empty summary semantics

- `#語意含義` / `#偏誤降低`：filtered response 的 `audited_reports=0` 代表目前審核狀態沒有匹配缺口，不代表有 `0` 份 complete snapshot；renderer 分離 status-specific empty copy 與 unfiltered complete copy。
- `#證據基礎` / `#來源品質`：API 的 `review_status_filter`、`items_total` 與 quality status map 是範圍證據；不從空集合推導全庫 quality coverage，也不重算 backend denominator。
- `#受眾` / `#溝通設計`：操作員看到「目前沒有符合〈狀態〉的品質 metadata 缺口」，可搭配仍保留的 `（0）`/all 導航理解目前篩選結果。
- `#責任` / `#限制條件`：修改限於 history renderer 與 cache-buster，backend audit、review ledger、artifact/index、queue、rerun 不變。
- `#可驗證性`：先以 filtered-empty fixture 取得 RED，再 GREEN `11 passed`；維持 renderer 99 行，並以跨層 suite、Node syntax、diff check 與 live asset/health/readiness 作最終驗證。

## D3573 / scoped review progress summary

- `#證據基礎` / `#差距分析`：live historical audit 有 `143` 個 pending 缺口；狀態數能說明分布，卻不能直接回答人工核對已完成多少，逐批處理容易失去進度感。
- `#語意含義` / `#偏誤降低`：進度分子只取 `approved_with_gap`、`rejected`、`deferred`，分母是四種 review status 的總和；complete report 不在 review map 中，避免把品質完整誤當成人工審核完成。
- `#受眾` / `#溝通設計`：摘要顯示「人工審核進度：已決策／總缺口」，切換 pipeline/status 後明確跟著目前範圍變化，不冒充全庫永久 KPI。
- `#責任` / `#限制條件`：修改只在 history renderer 與 cache-buster，backend aggregate、review ledger、artifact/index、queue、rerun 與 mutation 不變。
- `#可驗證性` / `#來源品質`：先以 progress fixture 取得 RED，再 GREEN `11 passed`；維持 renderer 99 行，並以跨層 suite、Node syntax、diff check 與 live asset/health/readiness 作最終驗證。

## D3574 / daily and historical review progress parity

- `#差距分析` / `#受眾`：daily board live 有 `2` 個 latest-scope pending 缺口，但原本只有「審核狀態」分布；history 已有 progress，兩入口對人工工作量的表達不一致。
- `#語意含義` / `#偏誤降低`：daily 與 history 都以 approved/rejected/deferred 為已決策、四狀態總和為缺口分母；daily 明確仍是 latest-per-ticker/pipeline scope，不冒充 historical 全量。
- `#溝通設計` / `#責任`：daily 只顯示進度提示並保留「查看歷史版本稽核」入口，不新增 queue action、review mutation 或第二套決策流程。
- `#限制條件` / `#來源品質`：修改只在 watchlist helper 與 cache-buster，保留 95 行責任護欄與既有 read-only boundary。
- `#可驗證性`：先以 daily fixture 取得 RED，再 GREEN `15 passed`；並以跨層 suite、Node syntax、diff check 與 live daily asset/summary/ledger 檢查收斂。

## D3564 / model-level quota observability boundary

- `#證據基礎` / `#來源品質`：live dashboard 只提供 aggregate Gemini quota error，無法把 `2909` 次 observed calls 與 `2569` 次 errors 對齊到模型；先以同一 `api_usage_events` reset window 分組 `observed_model_calls`、`quota_error` 與 `rate_limited`，不把 provider 回應外推成官方剩餘額度。
- `#偏誤降低` / `#語意含義`：新增 `observed_model_quota_errors`，對有呼叫但零錯誤的模型保留 `0`，UI 顯示「模型呼叫數、額度錯誤數、本機錯誤率」；避免只見 aggregate error 就誤停用所有模型，也避免零值缺席被誤讀成沒有該模型。
- `#責任` / `#受眾`：backend 只做 ledger read-only aggregation，quota service 只做 safe integer-map normalization，frontend 只做呈現；不改 routing、Redis circuit、key/model disable、queue、report rerun 或 mutation boundary。操作員可用模型集中度決定下一步查 provider response 與 retry evidence。
- `#可驗證性`：RED 先鎖定 quota event 的模型分組、成功模型的零錯誤值與前端錯誤率；GREEN 再以 live 匿名化 model map、asset cache-buster、health/readiness 和 scoped regression 驗證。全量 pytest 可收集，人工停止於 `953 passed, 4 skipped, 75 subtests passed` 的歷史長批次，未將未完成的全量結果宣稱為通過。

更新時間：2026-08-16

## D3563 / shared maintenance preview-confirmation boundary

- `#拆解問題` / `#差距分析`：D3562 只把 stale queue 做成 preview-confirmation；同一維護面板的報告索引、任務紀錄與來源健康紀錄仍可點擊即寫入，形成不一致的副作用邊界。
- `#倫理判斷` / `#責任`：新增 `maintenance_action_helpers.js` 作為共同 owner，四個 action 都先呼叫既有 endpoint 的 `write=false`，候選數為零、確認器不存在或操作員取消時回傳不寫入；核准後才委派原本的 `write=true` API/後端規則。
- `#受眾` / `#溝通設計`：各 action 用白話呈現實際候選數與清理類型，沿用既有 danger dialog；不把預覽結果誤報成已刪除，也不讓 UI 自己重建 backend cleanup 判定。
- `#可驗證性` / `#限制條件`：Node 行為測試覆蓋四個按鈕的取消與核准路徑，既有 `api_client.js <90`、`maintenance_panel.js <105` 責任護欄維持；live 驗證確認四個 preview request 均為 `write=false`，本批不執行 destructive cleanup。

本批暫定決策：先統一所有維護入口的人工確認邊界，不改 API payload、後端刪除條件、CLI 行為或現場資料。

驗證收斂：scoped maintenance/frontend/docs suite `897 passed`；live report-index、analysis-history、provider-sla、failed-queue preview 均 `success=true,dry_run=true`，deleted count 為 `0`，stale queue 為 `10` 筆；新版三個資產與 `healthz/readyz` 均 `200`。

## D3562 / stale failed queue confirmation gate

- `#偏誤降低` / `#責任`：原維護按鈕直接進入 `write=true`，操作員可能未先核對候選數；UI 改成先呼叫 `previewFailedQueue()`，只把 API 回傳的 `stale_failed_jobs` 作為確認內容，取消、零候選或沒有共用確認器時都不寫入。
- `#受眾` / `#溝通設計`：確認訊息白話呈現「清理前先確認」與將刪除筆數，沿用既有 danger dialog，不另造一套互動或把 dry-run 結果誤寫成已刪除。
- `#倫理判斷` / `#限制條件`：本批不執行 live destructive cleanup；仍保留 mutation token、dry-run 預設與 age evidence guard，UI 核准只是進入既有寫入邊界，不改後端刪除規則。
- `#可驗證性`：Node 行為測試實際跑取消與核准兩條路徑，確認 preview 次數、write 次數與訊息；完整 scoped suite `829 passed`，live dry-run 為 `10/10/0/0`（scanned/stale/deleted/errors），health/readiness 與新版資產均 `200`。

本批暫定決策：把 queue housekeeping 的人工核准放在寫入 API 前，並維持所有現場 queue evidence 不被本次驗證移除。

## D3561 / explicit stale failed queue maintenance

- `#拆解問題` / `#差距分析` / `#責任`：live RQ `stock-analysis` 有 10 筆 2026-06-28 failed jobs；observability 能分類 stale，但原維護面板沒有可執行入口，且 stale-only chip 的 tone 仍是 `is-ok`。
- `#倫理判斷` / `#限制條件`：不讓 worker 自動刪除、不自動重試、不把未知時間當 stale；新增 service 只在 `write=true` 且 mutation token 邊界內刪除可由 `ended_at`/`created_at` 證明超過門檻的 RQ job，dry-run 與近期/無法分類的 job 都保留。
- `#可驗證性` / `#受眾`：unit、API route、frontend wiring 與 OpenAPI 契約共同鎖定 dry-run、delete flag、button/action、stale warning tone；live 執行只做唯讀 dry-run，避免直接清掉現場 queue evidence。
- 驗證收斂：CLI 與 API `write=false` 皆回報 `failed_jobs_scanned=10`、`stale_failed_jobs=10`、`deleted_jobs=0`、`errors=0`；重啟後 health/readiness 為 `200`，OpenAPI 帶 `MutationToken`，三個新資產為 `200`，review ledger 仍為 `0`。

本批暫定決策：提供可追溯的人工清理入口，但不把歷史 failed registry 的 housekeeping 變成自動副作用；待操作人員明確執行 maintenance action 後，再以 live count 驗證刪除結果。

## D3560 / module responsibility boundary convergence

- `#拆解問題` / `#責任`：import boundary 的失敗由 report-quality audit、review route 與 observability payload 混合責任造成；先依實際 import/monkeypatch 依賴拆出 `report_quality_audit_payload`、`api_routes/report_quality_review`、`api_observability_payload_helpers` 與 `provider_sla_dashboard_payload`，保留 public import 與 route callable injection。
- `#最佳化` / `#系統動力學`：拆分後 `report_quality_audit=272`、`watchlist=313`、`api_observability_service=279`、`provider_sla_observability=127`，bounded cache、review history、provider impact、queue warning 的行為維持原 owner contract。
- `#可驗證性` / `#來源品質`：import boundary `503 passed`、observability `148 passed`、品質稽核／review／前端／文件跨層 `157 passed`；Python compile、Node syntax 與 diff check 通過，沒有新增 artifact/index/queue/rerun side effect。

本批暫定決策：先完成現有 boundary 的責任收斂，不為降低行數做行為重寫；下一步仍以 live runtime 與品質 evidence 的真實差距選擇優化點。

## D3559 / revision-scoped review timeline

- `#證據基礎` / `#責任`：D3558 ledger 已保存每次決策，但 audit payload 只帶最新 state 與 event count；若只看最新事件，無法驗證誰在何時留下哪個理由。新增 `list_review_history()`，以 filename、pipeline、revision 精確分組，最多回傳 20 筆且按 event id 倒序。
- `#偏誤降低` / `#來源品質`：history query 以當前 report-quality revision 為必要鍵，舊 artifact fingerprint 的事件不會混入新報告；仍不把人工決策轉成 gate pass，也不從 Markdown 重建 structured metadata。
- `#受眾` / `#可驗證性`：audit item 新增 `quality_review_history`，歷史頁用可展開區塊顯示事件編號、時間、操作人、決策與 note；更新 `review-history` cache-buster，TDD 先以 store/audit/frontend RED，再 GREEN。

本批暫定決策：先把目前 revision 的決策時間線做成唯讀 evidence，保留事件上限與 revision 邊界；若要跨 revision 比對，另立報告版本比較規格，不在本批混合顯示。

## D3558 / revision-scoped manual quality review

- `#差距分析` / `#證據基礎`：artifact marker 能指出可查文字，但不能回答人工核對是否已完成；若只用 filename，報告刷新後舊結論可能誤套到新 artifact。
- `#偏誤降低` / `#責任`：新增 `report_quality_revision`，以 indexed row 的 output_dir、filename、pipeline、mtime 與 stored hashes 綁定事件；`approved_with_gap` 明確表示保留品質缺口，不能轉成 gate pass 或 coverage complete。
- `#倫理判斷` / `#來源品質`：review ledger 只追加決策、note、reviewer label 與 artifact summary snapshot，位於 `operational.sqlite3`；不覆蓋歷史 artifact、不從 Markdown 重建 structured gate。
- `#可驗證性` / `#受眾`：API 以 mutation token 保護，stale revision 回 `409`，UI 顯示待核對/已核准保留缺口/退回/暫緩並要求理由；回應固定列出三個副作用皆為 false。

本批暫定決策：先建立可回溯的人工決策閉環，不自動把人工決策寫回報告品質欄位；後續若要做 metadata repair，必須另立 evidence patch 規格與二次核准。

## D3557 / report quality audit read cost

- `#差距分析` / `#最佳化`：live historical audit 首次約 `7.13s`、warm 約 `1.87–2.03s`，daily 約 `2.34s`；相同 read-only request 反覆讀取未變更的 report snapshot 與 Markdown。
- `#限制條件` / `#系統動力學`：新增最多 8 筆、15 秒 TTL 的 process row cache；key 同時含 scope、output_dir、filter 與 indexed row fingerprint，避免不同 storage root 或 report version 誤用同一結果。
- `#責任` / `#來源品質`：cache 只重用已由 canonical report index fingerprint 證明未變更的 derived rows；`updated_at`、`file_mtime`、stored hash 變化會重新讀取，不跨重啟、不寫入任何 operational state。
- `#可驗證性`：先以重複呼叫取得 RED，再 GREEN；回歸測試特別鎖定不同 temporary storage root 不可碰撞。重啟正式 runtime 後，historical summary 首次 `2.284s`、同一 process 暖讀 `0.122s/0.122s`，daily dashboard `1.810s/1.765s`；所有請求 `200`，historical `audited_reports=1330`、`quality_metadata_missing_reports=143` 維持一致。

本批暫定決策：優先降低重複 read cost，但不以永久 cache 或無 fingerprint TTL 掩蓋新的品質 evidence。

## D3556 / artifact evidence field coverage

- `#差距分析` / `#來源品質`：live historical `143` 筆缺口全部是 `status=present`，但 field marker 只有 `report_conformance=143`、`evidence_exit_gate=143`，`content_credibility=0`；status-only 摘要會隱藏部分 evidence。
- `#語意含義` / `#偏誤降低`：新增 `artifact_quality_summary_by_field`，以 pagination 前的全量 missing row 為分母，保留三個品質欄位的 marker count，UI 明確顯示零值；`present` 仍不是 structured gate pass。
- `#受眾` / `#責任`：daily 與 historical 共用欄位摘要，操作員可以直接判斷哪些 artifact evidence 可查，卻不會被引導成自動修復、採用或 rerun。
- `#可驗證性`：先以 field-count、pagination、daily/historical renderer fixture 取得 RED，再完成 backend/UI GREEN；更新 static field aggregate cache-buster。

本批暫定決策：把 artifact marker 的可用性拆成狀態與欄位兩層；欄位為零是明確 evidence gap，不由 UI 推導 gate 結論或產生 action。

## D3555 / artifact evidence availability aggregate

- `#差距分析` / `#受眾`：daily/historical audit 逐筆 target 已有 `artifact_quality_summary`，但 envelope 只回傳分頁 items；若只看前 5 筆，操作員無法知道全部 missing-metadata rows 的 artifact evidence 可用性。
- `#來源品質` / `#語意含義`：新增 `artifact_quality_summary_by_status`，只在已判定的 missing row 上累計 `present`、`not_found`、`unavailable`，並明確標示 `present` 是 Markdown/HTML marker 可查，不是 structured gate pass。
- `#偏誤降低` / `#責任`：daily 與 historical UI 共用同一 aggregate，避免把 pagination slice 誤當全量；不改 verified snapshot coverage 分母、不重建 gate、不寫 artifact/index、不 enqueue rerun。
- `#可驗證性`：先用 audit、historical renderer、watchlist board fixture 取得 RED，再完成 backend/UI GREEN；cache-buster 更新，保留 renderer/helper 行數責任護欄。

本批暫定決策：把 artifact evidence availability 作為完整度提示，不把 marker 存在升格為品質通過，也不由 aggregate 自動產生 remediation action。

## D3554 / daily 與 historical artifact evidence context 一致

- `#受眾` / `#溝通設計`：live daily dashboard 的 2 筆品質缺口已帶 `artifact_quality_summary`，但「今日工作台」target 原本只顯示 missing gate/provenance；同一筆報告在不同入口看到的 evidence context 不一致。
- `#系統動力學` / `#責任`：watchlist helper 沿用既有 `artifact_quality_summary.status=present` 與白名單 fields，加入可見次要文字、`title`、`aria-label` 及 `data-quality-artifact-fields`；不複製 backend 判定、不新增 API/queue/rerun/mutation。
- `#可驗證性`：先補 watchlist fixture 取得 RED，再完成 target markup、CSS 與兩個 cache-buster；watchlist frontend focused suite GREEN，helper 83 行仍低於 95 行責任護欄。

本批暫定決策：讓 daily/historical 人工核對入口共享同一 evidence context，不把 artifact 摘要視為 structured gate 通過，也不改 daily queue 排序。

## D3553 / artifact 摘要與 structured gate 邊界

- `#來源品質` / `#證據基礎`：live historical audit 的 143 筆缺 metadata row，其 Markdown 都保留 `Evidence gate`、`Report conformance` 與品質 gate 狀態文字；這是可查的 artifact evidence，不等同 snapshot 已有 structured gate。
- `#偏誤降低` / `#責任`：indexed audit 只對已判定缺口的 row 讀取 Markdown/HTML marker，輸出 `artifact_quality_summary.status/source/fields`；前端顯示「artifact 摘要可查」，不從文字重建 gate payload、不改 coverage、不回寫 artifact、不 enqueue rerun。
- `#可驗證性`：先新增 backend 與 renderer fixture 取得 RED，再完成 marker detection、欄位白名單與 accessible target context；TDD focused tests GREEN，renderer 94 行仍低於 100 行責任護欄。

本批暫定決策：補足人工核對的 evidence availability，不把 artifact 文字摘要升格為品質通過結論，也不自動修復 143 筆歷史 snapshot。

## D3552 / 歷史品質 target 的可見缺口 context

- `#受眾` / `#溝通設計`：live historical audit 的 143 筆 target 已能分批讀取，但每個按鈕原本只寫 ticker/mode；missing gate 與刷新 provenance 只在 tooltip，鍵盤或手機人工核對仍不夠可辨識。
- `#偏誤降低` / `#責任`：renderer 將 `missing_quality_fields` 映射成「報告一致性／證據關卡／內容可信度」，並將 `quality_metadata_provenance` 顯示為「刷新後」或「未標記刷新來源」；完整 context 同步進入 `title` 與 `aria-label`，不改 audit 統計、分頁、報告開啟 callback 或 read-only 邊界。
- `#可驗證性`：先新增 target fixture 取得 RED，再完成 renderer/CSS 與 cache-buster；前端 target summary test GREEN，renderer 90 行仍低於 100 行責任護欄。

本批暫定決策：降低逐筆人工核對的辨識成本，不把可見 context 解讀成 gate 已通過，不自動修復或擴大 historical audit scope。

## D3551 / 歷史品質缺口批次核對

- `#差距分析` / `#受眾`：live historical audit 有 `143` 筆缺口，但回應與畫面原本只列前 `5` 筆；即使選定 pipeline，人工仍無法沿既有頁面走完其餘 target。
- `#責任` / `#最佳化`：backend 只切 `items[]` slice，保留完整 coverage 統計；API client 傳 `item_offset`，module 由 generation 保護批次 response，renderer 提供「上一批／下一批」，不複製 report preview 或 repair 邏輯。
- `#可驗證性`：RED 暴露缺少 offset contract、舊 callback 相容性與 cache-buster；GREEN `192 passed`，live offset `0` 與 `5` 各回傳 5 筆不同檔案、`items_total=143`，health/ready 通過。

本批暫定決策：只改善人工核對明細的可達性，不擴張 audit scope、不改 verified snapshot 分母、不自動修復、不把歷史缺口加入每日 action。

## D3550 / 歷史稽核模式缺口快速聚焦

- `#受眾` / `#差距分析`：live historical audit 的 `143` 個缺口已按 `v1/v2/v3/v4` 聚合，但摘要只提供文字；操作員若要逐模式核對，仍需手動改 pipeline 下拉選單，且容易忘記先關閉舊 preview。
- `#溝通設計` / `#最佳化`：renderer 對每個有缺口的模式提供 `只看 vN 缺口`，使用 `data-quality-audit-pipeline`；module 只委派既有 filter，不複製 API 查詢或 audit 判定。
- `#責任` / `#可驗證性`：workspace 重新載入前重設頁碼並關閉 preview，保留 history list/audit generation、report target `openReport()`、daily queue 與 `verified_snapshot_reports` 分母；前端 RED→GREEN 測試確認模式按鈕與 delegation，`history_workspace.js` 維持 177 行。

本批暫定決策：改善模式級人工核對的尋路成本，不擴張 historical item limit、不自動修復、不把歷史缺口轉成每日 action。

## D3549 / 歷史列表與稽核的共同回應序號

- `#差距分析` / `#系統動力學`：D3548 只保護 historical audit summary；`loadHistory()` 的 report list 仍可能在 filter race 中讓舊 `/api/reports` response 覆蓋新列表，造成摘要與列表不一致。
- `#偏誤降低` / `#責任`：workspace 在 load 開始固定 filter snapshot，使用單一 generation 丟棄 stale list response，並提前把同一 snapshot 傳給 quality audit；pagination/render/preview 行為不被改寫。
- `#可驗證性`：新增 controlled deferred response harness；RED 觀察 final `old`，GREEN `10 passed` 觀察 final `new`，另以 fresh live audit navigation 確認 `1330/143` 與既有 GET-only boundary。

本批暫定決策：以 workspace generation 統一列表與稽核的顯示一致性，不引入 AbortController 或更改後端 endpoint。

## D3548 / 今日範圍到歷史範圍的唯讀導引

- `#受眾` / `#組成`：追蹤工作台目前只顯示 latest-per-ticker/pipeline 的 `2` 個缺口；歷史頁則有 `143` 個版本缺口，兩者分母不同但缺少入口連接。
- `#溝通設計` / `#責任`：新增「查看歷史版本稽核」按鈕，僅呼叫 app navigation 與既有 `openHistoricalQualityAudit()`；history workspace 自己負責 checkbox、篩選狀態與捲動，追蹤面板不複製 audit 邏輯。
- `#可驗證性`：RED→GREEN navigation/delegation `3 passed`；fresh browser 從追蹤頁點擊後確認分析頁、舊版 checkbox、`1330/143` 摘要，performance resource 只見既有 GET，沒有 mutation。

本批暫定決策：只補 scope discovery 與唯讀導引，不合併 daily/history 數字、不把歷史缺口加入今日 queue，也不改任何 audit 計算。

## D3547 / 品質完整度分母與 snapshot 驗證邊界

- `#語意含義` / `#來源品質`：API 的 coverage 是以 `verified_snapshot_reports` 為分母，不能把 `audited_reports` 或被排除的 invalid/unverified rows 說成完整證據。
- `#偏誤降低` / `#受眾`：歷史稽核摘要明示完整度百分比與「分母：已驗證快照」，另列 `snapshot 無法驗證` 的 invalid/未驗證數；無缺口時也只宣稱 verified snapshot 沒有 metadata 缺口。
- `#可驗證性`：新增完整度與驗證邊界 fixture；RED 確認舊 UI 不呈現 basis，GREEN `6 passed` 確認 `89.25%` 與 `1 invalid/2 未驗證` 都可見，並鎖住 renderer/helper cache-buster 與 size boundary。

本批暫定決策：只補充現有 API evidence 的正確呈現，不改 coverage 計算、audit scope、artifact 或 daily queue 行為。

## D3546 / 歷史品質稽核篩選回應一致性

- `#差距分析` / `#系統動力學`：歷史稽核是背景請求；搜尋或 pipeline 連續變更會形成多個 in-flight request，完成順序不一定等於操作順序，舊 coverage 可能覆蓋新範圍。
- `#偏誤降低` / `#責任`：`history_quality_audit` 以 `loadVersion` 保存單一模組責任，只有最後一次 load 能 render；includeVersions 關閉、API 不存在與 exception 路徑也不讓過期 response 改寫畫面。
- `#可驗證性`：新增延遲 response Node harness，先完成新範圍 `1` 份，再完成舊範圍 `9` 份；RED 確認舊值覆蓋，GREEN 確認畫面仍保留 `範圍：1 份`。專屬前端 suite `4 passed`。

本批暫定決策：只修正前端 response ordering，不在 API 增加取消機制或改變 audit selection；既有 read-only、背景載入與 openReport 行為維持不變。

## D3545 / 歷史品質稽核進入操作閉環

- `#受眾` / `#差距分析`：API 已有 1330 份 historical coverage 與 143 個缺口，但歷史頁沒有入口；操作員若不使用 curl，無法在既有報告流程中定位缺口。
- `#溝通設計` / `#語意含義`：勾選「顯示舊版報告」後，頁面顯示與當前搜尋/模式篩選一致的「歷史版本品質稽核」，白話呈現缺 gate、來源與模式分布，最多列五個人工核對 target。
- `#最佳化` / `#責任`：新增 `history_quality_audit.js` 專責載入/降級/CTA delegation；背景載入不阻塞歷史列表，CTA 沿用 `openReport()`，不新增第二套報告路徑。
- `#責任` / `#倫理判斷`：維持 historical audit read-only，不加入 daily queue、不自動修復、不從 HTML/Markdown 重建 gate、不寫 artifact/index、不 enqueue rerun。
- `#可驗證性`：helper/module wiring、asset cache-buster、CSS/JS size boundary 與 static regression 必須一起通過，之後以重啟 runtime 與實際歷史頁互動確認 endpoint/filter/CTA。

本批暫定決策：先讓歷史品質 evidence 在既有報告頁可被查證，再保留批次修復為另一個需明確核准與 audit trail 的工作流。

## D3544 / 品質缺口 provenance 聚合

- `#來源品質` / `#證據基礎`：live historical audit 的 143 筆缺口全部是 `quality_metadata_after_refresh`，且現行 refresh service 已有 gate preservation；因此不能把歷史 evidence gap 誤寫成目前 refresh regression。
- `#語意含義` / `#偏誤降低`：新增 `after_refresh` 與 `no_refresh_provenance` 聚合；後者只表示沒有 `refreshed_from_report` attribution，不等同於「從未刷新」。
- `#受眾` / `#溝通設計`：watchlist board 在有新欄位時顯示「來源：刷新後缺口／未標記刷新來源」，item 保留刷新檔名與時間，操作員可回到 artifact/freshness 查證。
- `#責任` / `#倫理判斷`：維持 read-only audit、priority `820`、人工核對與 `blocks_auto_rerun`；不從 HTML/Markdown 重建 gate、不回寫歷史 snapshot、不自動 enqueue rerun。
- `#可驗證性`：先以 audit regression 取得 RED，再完成後端/前端 GREEN；本批後續重啟 runtime 後需確認 live full historical、daily dashboard、filtered endpoint 與 served cache-buster。

本批暫定決策：先補 provenance evidence 與可讀摘要，再決定是否需要獨立的人工歷史修復 workflow；不把分類欄位誤升格為修復結論。

## D3529 / full audit 保留 provenance detail

- `#可驗證性` / `#責任`：live probe 證明 repair helper 有 `quality_metadata_after_refresh`，但 `_audit_item()` serializer 丟掉 detail/reason codes；只看 title 無法追查判定依據。
- `#溝通設計` / `#受眾`：full audit `items[]` 現在保留 detail 與 reason codes，操作員/API consumer 可知道是「刷新後缺口」，而不是只看到泛稱標題。
- `#偏誤降低`：只增加輸出證據，不改 priority `820`、人工審核、阻擋自動重跑與 98.75% coverage 結論。
- `#可驗證性`：audit/repair regression RED→GREEN `52 passed`，並需用重啟後 live endpoint 確認 reason code 真正穿透 API。

本批暫定決策：full audit item 的 detail/reason codes 是觀測證據，不等同於歷史 gate 已恢復；仍禁止從摘要推測完整 structured payload。

## D3528 / 刷新 provenance 的品質缺口語意

- `#來源品質` / `#證據基礎`：job event 與 checkpoint 沒有可安全重建的三個 structured gate；snapshot 的 `refreshed_from_report` 與 artifact 內摘要只能證明曾刷新與曾渲染摘要，不能推測完整 gate payload。
- `#語意含義` / `#受眾`：將 repair title 從泛稱「品質證據未記錄」細分為「刷新後品質證據缺口」，並加上 `quality_metadata_after_refresh`，讓操作員先查 artifact/freshness，不把缺口錯判成生成器未執行品質檢查。
- `#責任` / `#偏誤降低`：維持 priority `820`、人工審核、阻擋自動重跑；不以 HTML 摘要反推 content credibility 或 evidence 詳情，也不自動回寫歷史 snapshot。
- `#可驗證性`：repair helper 與 indexed audit integration RED→GREEN，品質 audit/repair `52 passed`。

本批暫定決策：先改善 evidence provenance 的辨識與溝通；歷史 gate 若要恢復，必須另建具明確輸入/輸出與 audit trail 的人工核准 workflow。

## D3527 / 資料刷新不得抹除報告品質證據

- `#拆解問題` / `#差距分析`：live HTML 已有 Evidence gate 與 Report conformance 顯示，刷新後 data snapshot 卻只剩 report lint；缺口位於 refresh persistence boundary，不是 renderer 沒有計算 gate。
- `#來源品質` / `#責任`：HTML、Markdown 與 data snapshot 的寫入時間線確認是 15:32/15:47 產生報告，15:48 refresh 重建 snapshot；修正放在 canonical `build_data_snapshot()` 與 `refresh_report_data_snapshot()`，不在 audit 層補假資料。
- `#偏誤降低` / `#語意含義`：refresh 只更新資料可信度與 freshness/rerun，不應把原報告品質 gate 變成空物件；若需要重新分析，仍由 `decision_freshness` / repair queue 呈現，不把舊 gate 當成新分析。
- `#可驗證性`：先新增 refresh metadata regression 取得 RED，再補 `evidence_exit_gate` schema 欄位與三 gate context preservation；GREEN 為 refresh `1`、data-trust `182`、renderer/quality `45`、preview/API `164`、artifact/storage/import `551` passed，並重啟 live runtime。

本批暫定決策：修復未來 refresh 的 metadata preservation，不自動重跑或回寫目前兩份已遺失原始 gate 的歷史 snapshot；歷史修復仍需人工核准。

## D3526 / 品質 coverage 分母明確化

- `#語意含義` / `#偏誤降低`：live audit 的 `quality_metadata_coverage_basis=verified_snapshot_reports` 不應在 UI 被簡化成無分母的「覆蓋 98.75%」；改顯示「已驗證快照覆蓋 98.75%」，避免 snapshot 被排除時誤判全索引品質。
- `#受眾` / `#責任`：操作員能直接知道這個百分比的證據範圍，並把缺少品質 metadata 與無法驗證 snapshot 分開處理；沒有 basis 的相容 payload 仍維持一般「覆蓋」文案。
- `#可驗證性`：先新增 Node 行為測試確認品質 CTA click 傳遞 `filename/ticker/pipeline`，再以 coverage 文案 RED→GREEN；前端 audit suite `5 passed`。

本批暫定決策：UI 只映射已知 basis label，不直接把未知後端字串暴露給操作員；後續新增 basis 必須同步定義白話中文語意與測試。

## D3525 / 品質缺口的可追溯人工入口

- `#受眾` / `#差距分析`：backend audit 已有兩份 missing item 的報告定位資料，但 watchlist board 只顯示數字；操作員仍需自行切換 history，增加人工核對成本。
- `#語意含義` / `#溝通設計`：新增「查看 1623.TW v1/v2」類型的明確 read-only CTA，語意是開啟報告查看，不是重跑、修復或採用報告。
- `#偏誤降低` / `#責任`：按鈕只走既有 `openReport(filename, ticker, pipeline)`，不進 decision queue、不 POST rerun、不寫 artifact/index；invalid/unverified snapshot 仍只顯示警示。
- `#最佳化` / `#限制條件`：沿用既有 watchlist board、事件 delegation 與 report preview，不新增第二套報告路徑；更新 style/script cache-buster，讓瀏覽器不留在舊 bundle。
- `#可驗證性`：RED→GREEN static/history `136 passed`、HTTP/quality/dashboard `49 passed`，JS syntax 與 file-size budget 通過。

本批暫定決策：人工核對入口可直接定位報告，但不自動產生 remediation action；後續若要批次修復，仍需另外核准 workflow 與 audit trail。

## D3524 / snapshot 排除數與逐筆 audit 隔離

- `#拆解問題` / `#差距分析`：audit coverage 只看 verified snapshot，若沒有 invalid/unverified 計數，操作者難以區分「沒有缺口」與「資料根本未納入分母」。
- `#偏誤降低` / `#語意含義`：新增 `snapshot_invalid_reports`、`snapshot_unverified_reports` 與 `quality_metadata_coverage_basis`；coverage 明確以 verified snapshot 為分母，排除 row 不再靜默消失。
- `#可驗證性` / `#責任`：`load_storage_item()`、JSON parse 與 integrity check 都在 row 邊界隔離例外；單筆 failure 只成為 unverified，不會把其他報告或每日工作台整體變成 unavailable。
- `#受眾` / `#溝通設計`：前端在有排除 row 時顯示「snapshot 無法驗證」，不把它解讀成品質 gate 通過，也不新增 daily action。
- `#最佳化`：coverage 計算維持原 denominator 與 160-row 輸出，只增加可追蹤欄位與失敗隔離，避免擴大 audit 成為 artifact repair。
- `#可驗證性`：RED→GREEN audit/前端 `8 passed`，quality repair/dashboard/queue/provider `231 passed`；runtime 重啟後 `/healthz=ok`、`/readyz=ready`，live 160/160 verified、invalid 0、unverified 0、158 complete、2 missing、coverage `98.75%`，dashboard 約 `1.94–1.98` 秒。

本批暫定決策：完整度 audit 必須同時報告分母與排除數；先保留排除 row 為 unverified，修復 artifact 另列人工 scope。

## D3523 / 品質 metadata repair module 責任拆分

- `#拆解問題` / `#差距分析`：完整 import boundary 的唯一紅燈是 `report_quality_repair_items.py` 超過既有 `<190` 行責任護欄；根因是 D3521 把新的品質 metadata 判定直接加進共用 repair helper。
- `#限制條件` / `#最佳化`：不壓縮語句、不放寬 boundary、不改既有呼叫者；新增 `report_quality_metadata_repair.py` 承擔 verified snapshot 與三 gate metadata 缺口判定，原 module 只做相容匯出與其他 repair builders。
- `#語意含義` / `#責任`：`quality_metadata_repair_item.__module__` 明確指向專責 module，但 queue/audit 仍從既有 `report_quality_repair_items` import，維持既有 API 邊界與 priority 820、manual review、blocks_auto_rerun 行為。
- `#可驗證性`：先以 ownership contract 及既有行數 test RED，再 GREEN；專責/既有 metadata/import `3 passed`，quality repair/audit/dashboard/frontend `84 passed`，完整 import boundary `503 passed`，新 module compile 通過。

本批暫定決策：將新增品質規則放入 domain-specific module，保留 façade 相容入口；後續新增 repair rule 必須先確認責任模組與 import-boundary 預算。

## D3522 / 全量品質覆蓋與每日 action scope 分離

- `#拆解問題` / `#差距分析`：近期 20 份報告是可執行的每日工作範圍，不等於 report index 的全部最新 row；live 全量為 160 份，若只看 sample 會漏掉歷史品質 metadata 缺口。
- `#變數分析` / `#偏誤降低`：action sample 保持原本 rerun/repair predicate；full audit 是只讀 coverage，逐一從 raw index row 透過 storage helper 載入 snapshot，不把歷史缺口誤升級成今日 action，也不把無法讀取誤報成零缺口。
- `#來源品質` / `#可驗證性`：audit 以 `report_index.query_report_metadata(..., row_mapper=...)`、`load_storage_item()` 與 `verify_data_snapshot_integrity()` 為證據來源；不讀 preview rendering、不回寫 artifact/index。live 結果為 160/160 verified、158/160 complete、2 份 `1623.TW` v1/v2 missing、coverage `98.75%`。
- `#受眾` / `#溝通設計`：工作台只增加「全量報告品質：2 份待人工核對（覆蓋 98.75%）」提示；audit unavailable 時顯示「暫時無法讀取」，保留原每日工作台與通知邏輯。
- `#最佳化` / `#責任`：由 full `list_reports` audit 約 4 秒改成 raw-index/lightweight path；本次 live 重啟測得 `1.86–2.05` 秒。route 只讀且失敗隔離，歷史兩份修復仍由人工決定，不自動重跑。
- `#可驗證性`：RED→GREEN audit/dashboard `39 passed`、static/HTTP `152 passed`、report-history/index boundary `3 passed`；live `/healthz=ok`、`/readyz=ready`。

本批暫定決策：將「完整度觀測」與「今日可執行工作」拆成不同 scope；先揭露 coverage 與人工核對項目，暫不擴張成全量自動修復。

## D3521 / 品質 metadata 缺失可見性

- `#拆解問題` / `#差距分析`：全量 history audit 顯示 `1623.TW` v1/v2 的報告產物與 verified snapshot 都存在，但三個 persisted quality gate 是空物件；原 queue 沒有對應的 repair action。
- `#語意含義` / `#受眾`：空物件不是「通過」，也不能直接說成報告失敗；前端改為「品質證據未記錄／先人工查看」，讓歷史卡片與 preview 的讀取邊界一致。
- `#偏誤降低` / `#可驗證性`：backend 只在 `snapshot_integrity.status=verified` 且 `report_conformance`、`evidence_exit_gate`、`content_credibility` 缺有效 status/verdict 時建立 priority 820 的 blocked `manual_review`；未驗證 snapshot 仍由原 integrity repair item 處理，避免 synthetic row 行為漂移。
- `#責任` / `#制定策略`：不自動重跑、不回寫 HTML/Markdown/snapshot/index；每日工作台仍是近期 20 份 v4 抽樣，歷史缺口透過 history/preview 與 production queue helper 呈現，不擴張抽樣範圍冒充全量結論。
- `#可驗證性`：RED→GREEN 完成空 gate queue、前端 action/boundary、static/history/preview/queue `190 passed`，dashboard/queue/provider/API `190 passed`，並通過 JS syntax、Python compile、diff check。

本批暫定決策：先讓「沒有品質證據」成為明確、不可自動採用的人工審核訊號；是否要另做全量歷史修復工作，保留為下一批需人工核准的 scope。

## D3520 / 歷史 v4 品質 gate 相容性

- `#拆解問題` / `#差距分析`：live 最近 20 份 v4 history row 都是部署前 snapshot，仍帶 `recommendation_target_alignment` 舊 check；但 preview 已能讀出交易方向、目標與停損，造成新舊報告的品質證據不一致。
- `#語意含義` / `#受眾`：歷史卡片、preview 與每日 repair queue 都應使用同一套 v4 短線交易計畫語意；不能因 API 通用 recommendation 是 `N/A` 就把短線交易計畫說成沒有可檢查內容。
- `#偏誤降低`：row mapping 只在 v4、舊 gate、且 snapshot/Markdown 可解析交易計畫時 lazy 重算 `trade_setup_alignment`；v1–v3、缺少交易計畫、已具新 check 的報告原樣保留，且不寫回任何 artifact/index。
- `#可驗證性`：先以歷史 row RED 測試鎖住舊 check，再以 `148 passed` 通過 preview、content credibility、frontend history 與 temporal-memory 回歸；runtime 重啟後 live 最近 20/20 v4 為新 check，`legacy_skip_count=0`，preview 方向未變。
- `#責任` / `#制定策略`：RQ failed registry 的 10 筆紀錄已核對為 2026-06-28 的 `test_rq_sys_config.run_job` 歷史測試工作；它們沒有對應 canonical `analysis_jobs` 可執行任務，也沒有進 daily decision queue，因此保留 raw registry 觀測，不把歷史測試失敗變成操作員待辦。

本批暫定決策：相容性修正放在讀取邊界，讓歷史品質判斷立即一致；不回寫報告檔、不改長短線欄位語意，也不把 raw RQ registry 計數冒充報告工作失敗。

## D3519 / Mode D 交易計畫可信度

- `#拆解問題` / `#差距分析`：live `2465.TW` 的 v4 `preview` 已有交易方向、進場區間、1–2 週目標與停損，但通用 recommendation metadata 是 `N/A`；品質 gate 因此只說略過方向一致性檢查。
- `#語意含義` / `#受眾`：v4 是短線交易計畫，不是長線 3/6/12 個月投資建議；不把 `Neutral` 強行改成長線「持有」，也不把 1–2 週目標寫進長期目標欄位。
- `#偏誤降低`：新增 `trade_setup_alignment`，Long/Short 分別核對目標與停損相對現價的方向；Neutral 保留中性，只要求價格輸入可解析。缺少價格時 warning，方向矛盾時 blocking。
- `#組織結構`：上一批 route payload 讓 observability service 超過既有 import-boundary 行數護欄；將 helper 抽到 `backend/model_route_observability.py`，保留 API service 的相容匯出與既有測試 monkeypatch 入口。
- `#可驗證性`：新增完整交易計畫、Long 方向矛盾與不可解析價格 RED→GREEN 測試；一般 v1–v3 recommendation alignment 保持原路徑。報告品質相關 `200 passed`、storage/artifact/lint/reading `80 passed`、runtime observability `136 passed`、HCS/docs/import `638 passed`。

本批暫定決策：只補 Mode D 的品質證據與方向護欄，不改 report index 共用欄位、不污染 3/6/12 個月目標、不改 v4 preview 顯示邏輯。

## D3518 / 模型路由維運可見性

- `#差距分析`：live dashboard 已產生 3 條 `slow_route`，但 `model_route_warning` 的操作入口指向只渲染 quota service 的 panel；操作人員無法從 deep link 看到 route、p95 或 warning id。
- `#可驗證性`：目前三條 live slow route 都是 0 failures、0 retries；`slow_route` 也由既有 policy 排除於 daily decision queue，因此問題是可見性，不是需要立即改 routing 或重跑策略。
- `#語意含義` / `#受眾`：面板把 `slow_route`、`retry_storm`、`quality_gate_failures` 分別標成延遲、重試與品質檢查警示；每筆都保留 route/message，並提醒單份報告重跑要回看 `data_trust`、`decision_freshness` 與 `今日工作台`。
- `#反饋迴路` / `#組織結構`：新增窄責任 `/api/observability/model-routes`，loader 以 `Promise.allSettled` 隔離 route observer 與 quota observer；route 失敗不會遮住 quota，daily queue suppression policy 維持不變。
- `#可執行性`：先以 endpoint、panel render、workspace loader contract 取得 RED，再完成 GREEN；後續以 OpenAPI、static、observability、live endpoint 與 served UI 驗證。

本批暫定決策：不改 model route、retry threshold 或 daily queue `slow_route` suppression；只補 route warning 的維運顯示與證據邊界。

## D3517 / API quota 本機觀測語意

- `#偏誤辨識`：live quota payload 的錯誤數是本機 `api_usage_events` 週期統計，不是 provider 全域健康或剩餘額度；舊 UI 仍以「LLM/API 健康」命名，會放大證據範圍。
- `#偏誤降低`：成功、warning、空資料與讀取失敗四種路徑統一使用 `LLM/API 本機觀測`，保留 warning tone、錯誤數、設定服務數與 refresh 行為。
- `#語意含義` / `#受眾`：warning 改為「本機觀測需留意」，讓操作人員知道要查 reset time、provider response 與報告 `data_trust`，而不是把 warning 當作 provider 全域結論。
- `#可驗證性`：static contract RED→GREEN `3 passed`；`node --check` 通過；相關 static 檔案沒有殘留 `LLM 健康` 或 `LLM/API 健康` 顯示詞。

本批暫定決策：只修正證據範圍與文案，不清除既有 `api_usage_events`、不降低 quota warning、不改 model circuit 或 provider retry policy。

## D3516 / 系統告警與報告可用性分層

- `#拆解問題`：將 provider SLA 的 system-window aggregation、單份報告 `data_trust`/`decision_freshness` 與 daily decision queue 分成三個判斷層，不再把 dashboard `critical` 直接等同於報告必須重跑。
- `#差距分析`：live provider dashboard 是 `critical + core`，但 live daily dashboard 的 20 份抽樣報告為 `monitor`、無 rerun/repair；缺口位於前端語意，不是 provider aggregation 或 report repair predicate。
- `#偏誤降低`：核心 SLA 文案改為「期間性的系統來源提醒」，明確要求以報告資料可信度與 `今日工作台` 決定單份報告動作；保留 critical 等級，避免因文案修正而掩蓋真實供應商事故。
- `#受眾` / `#語意含義` / `#組織結構`：先說明告警時間範圍，再指出報告級判斷入口，最後保留既有核心/補充來源分流，讓非工程操作人員能按證據層級行動。
- `#可驗證性`：`test_provider_sla_helpers_group_rows_and_copy_without_panel` 鎖住核心告警新文案與舊誤導語句不再出現；provider SLA/static adjacent regression `10 passed`，`node --check` 通過。

本批暫定決策：不降級 FMP stable quote 的 system-level `critical`，不自動把 report readiness 從另一個 API 偷接進 provider panel；先修正語意邊界，保留既有 report repair queue 作為單份報告的真實動作來源。

本文件是 `docs/hcs-plus-optimization-state.md` 的嚴格單項輪巡附件。先前已完成四大類批次式優化；本次開始把每個 HCS 單項思考習慣獨立落地、獨立驗證，避免「類別完成」掩蓋單項盲點。

## 專案狀態

- 專案目標：讓本機股票研究系統的報告、前端工作台、資料可信度與維運流程更可掃讀、可驗證、可追溯。
- 已完成範圍：第 1 輪 / 批判思考 / `#拆解問題` 到 `#可驗證性`，第 1 輪 / 創意思考 / `#學習科學` 到 `#研究複製`，第 1 輪 / 溝通思考 / `#受眾` 到 `#多媒體`，第 1 輪 / 互動思考 / `#倫理考量` 到 `#制定策略`，第 2 輪 / 批判思考 / `#拆解問題` 到 `#可驗證性`，第 2 輪 / 創意思考 / `#學習科學` 到 `#研究複製`，第 2 輪 / 溝通思考 / `#受眾` 到 `#多媒體`，第 2 輪 / 互動思考 / `#倫理考量` 到 `#制定策略`，第 3 輪 / 批判思考 / `#拆解問題` 到 `#可驗證性`，第 3 輪 / 創意思考 / `#學習科學` 到 `#研究複製`，第 3 輪 / 溝通思考 / `#受眾` 到 `#多媒體`，第 3 輪 / 互動思考 / `#倫理考量` 到 `#制定策略`。
- 暫定策略：把批判思考發現轉成小型可學、可接續、可驗證的文件與前端契約改善。
- 驗證基準：每批至少有一個自動化測試或文件契約能防止狀態回退。
- 目前限制：尚未重跑完整測試矩陣；本批次先驗證 HCS 文件契約。

## 完整單項輪巡清單

| 分類 | 思考習慣 |
|---|---|
| 批判思考 | #拆解問題、#問對問題、#差距分析、#變數分析、#偏誤辨識、#偏誤降低、#決策樹、#目的、#效用、#信賴區間、#相關性、#描述統計、#機率、#迴歸、#顯著性、#證據基礎、#演繹、#歸納、#謬誤、#來源品質、#情境脈絡、#批判、#估算、#詮釋框架、#合理性、#可驗證性 |
| 創意思考 | #學習科學、#限制條件、#類比、#演算法、#設計思考、#捷思法、#最佳化、#假說發展、#資料視覺化、#建模、#抽樣、#個案研究、#比較組、#介入研究、#訪談調查、#觀察研究、#研究複製 |
| 溝通思考 | #受眾、#組成、#語意含義、#組織結構、#專業性、#論點、#溝通設計、#表達、#媒介、#多媒體 |
| 互動思考 | #倫理考量、#倫理勇氣、#倫理判斷、#複雜因果、#湧現特性、#分析層次、#網絡、#系統動力學、#系統圖像、#談判、#說服、#形塑行為、#從眾、#差異、#情緒智商、#領導原則、#權力動態、#責任、#自我覺察、#制定策略 |

## 嚴格輪巡進度

| 輪次 | 分類 | 思考習慣 | 狀態 | 落地修改 |
|---|---|---|---|---|
| 1 | 批判思考 | #拆解問題 | 完成 | 建立本嚴格輪巡附件與批次邊界 |
| 1 | 批判思考 | #問對問題 | 完成 | 將高影響決策寫成暫定決策與可回答問題 |
| 1 | 批判思考 | #差距分析 | 完成 | 建立現況到目標的缺口矩陣 |
| 1 | 批判思考 | #變數分析 | 完成 | 建立會影響報告可信度與維運體驗的變數清單 |
| 1 | 批判思考 | #偏誤辨識 | 完成 | 建立偏誤風險與對應護欄，並新增文件契約測試 |
| 1 | 批判思考 | #偏誤降低 | 完成 | 將 alias 漂移風險轉成 canonical pipeline 文件護欄 |
| 1 | 批判思考 | #決策樹 | 完成 | 決定本批先修文件範例與契約，而非 runtime 行為 |
| 1 | 批判思考 | #目的 | 完成 | 明確化 pipeline 文件範例的使用者目的 |
| 1 | 批判思考 | #效用 | 完成 | 用低風險文件修改降低新整合者選錯 ID 的成本 |
| 1 | 批判思考 | #信賴區間 | 完成 | Active jobs 顯示共用模式語意，降低操作者對任務類型的不確定性 |
| 1 | 批判思考 | #相關性 | 完成 | 避免任務狀態與 raw pipeline id 產生錯誤關聯 |
| 1 | 批判思考 | #描述統計 | 完成 | 將任務列表摘要維持在可掃讀的 ticker、模式、狀態、進度 |
| 1 | 批判思考 | #機率 | 完成 | Performance panel 顯示樣本信心提示，避免把少量 hit rate 當成穩定機率 |
| 1 | 批判思考 | #迴歸 | 完成 | 將回測績效維持為觀察指標，不把短期 ROI 當成可外推趨勢 |
| 1 | 批判思考 | #顯著性 | 完成 | 10 筆以下標示「樣本不足，僅供觀察」 |
| 1 | 批判思考 | #證據基礎 | 完成 | Preview 頂部顯示 evidence exit gate / report conformance 品質徽章 |
| 1 | 批判思考 | #演繹 | 完成 | 避免從「可預覽」錯推成「證據與格式皆可採用」 |
| 1 | 批判思考 | #歸納 | 完成 | 將 history 的品質警示延續到 preview，維持跨視圖一致性 |
| 1 | 批判思考 | #謬誤 | 完成 | Operator summary 移除 `fresh / sampled` 內部語氣，避免把資料新鮮度誤讀為整體可信 |
| 1 | 批判思考 | #來源品質 | 完成 | 將來源提醒脈絡寫成「無需刷新/重跑 · 資料新鮮 / 抽樣」 |
| 1 | 批判思考 | #情境脈絡 | 完成 | 把摘要樣本範圍明確標成「抽樣」，避免被看成全庫統計 |
| 1 | 批判思考 | #批判 | 完成 | 將 LLM 健康正常改為本機觀測正常，避免過度肯定 |
| 1 | 批判思考 | #估算 | 完成 | API quota summary 明確說明是本機觀測與服務設定數 |
| 1 | 批判思考 | #詮釋框架 | 完成 | 將 LLM/API 面板框架從 provider 健康改成本機觀測 |
| 1 | 批判思考 | #合理性 | 完成 | 補上批判思考第 1 輪 26/26 收尾摘要 |
| 1 | 批判思考 | #可驗證性 | 完成 | 用 HCS 狀態測試鎖住收尾摘要與下一分類入口 |
| 1 | 創意思考 | #學習科學 | 完成 | 在模式契約新增決策問題式速記 |
| 1 | 創意思考 | #限制條件 | 完成 | 不改 UI 與 runtime，只補文件契約測試 |
| 1 | 創意思考 | #類比 | 完成 | 用「分診台」類比說明模式選擇流程 |
| 1 | 創意思考 | #演算法 | 完成 | 新增模式選擇決策樹 |
| 1 | 創意思考 | #設計思考 | 完成 | 以使用者決策情境排列 mode 選擇順序 |
| 1 | 創意思考 | #捷思法 | 完成 | 定義不確定時先用 `v1` 建立基本面基準 |
| 1 | 創意思考 | #最佳化 | 完成 | Report compare summary 使用共用 mode label，降低辨識成本 |
| 1 | 創意思考 | #假說發展 | 完成 | 驗證「比較報告時先看決策模式」的 UI 假說 |
| 1 | 創意思考 | #資料視覺化 | 完成 | 比較選取摘要不再顯示 raw `pipeline_id` |
| 1 | 創意思考 | #建模 | 完成 | Report compare result 顯示左右比較基準 |
| 1 | 創意思考 | #抽樣 | 完成 | Report compare result 顯示左右樣本日期與時間順序 |
| 1 | 創意思考 | #個案研究 | 完成 | 將兩份報告比較框成可審查個案 |
| 1 | 創意思考 | #比較組 | 完成 | 跨模式比較 warning 改用可讀 mode label |
| 1 | 創意思考 | #介入研究 | 完成 | 以前端轉譯介入 raw pipeline warning |
| 1 | 創意思考 | #訪談調查 | 完成 | 將使用者可能誤解的 warning 文案轉成測試契約 |
| 1 | 創意思考 | #觀察研究 | 完成 | 掃描前端 raw mode 使用，區分顯示與資料傳遞 |
| 1 | 創意思考 | #研究複製 | 完成 | 將共用 mode label 模式複製到 compare summary/result/warning |
| 1 | 溝通思考 | #受眾 | 完成 | Compare warning 改用非工程操作者可讀語氣 |
| 1 | 溝通思考 | #組成 | 完成 | Warning 由左右模式與比較性質組成 |
| 1 | 溝通思考 | #語意含義 | 完成 | 將 `vs` 改成「與」，並明示跨視角比較 |
| 1 | 溝通思考 | #組織結構 | 完成 | Report compare result 第一列顯示比較結論 |
| 1 | 溝通思考 | #專業性 | 完成 | 以同股票同模式/跨視角等專業語氣標示比較性質 |
| 1 | 溝通思考 | #論點 | 完成 | 讓比較結論先於檔名與數字出現 |
| 1 | 溝通思考 | #溝通設計 | 完成 | 收斂 compare panel，不再新增複雜視覺元件 |
| 1 | 溝通思考 | #表達 | 完成 | 用收尾摘要固定本輪比較文案原則 |
| 1 | 溝通思考 | #媒介 | 完成 | 確認目前以文字 grid/chip 作為合適媒介 |
| 1 | 溝通思考 | #多媒體 | 完成 | 記錄暫不引入圖表/截圖式比較，避免過度設計 |
| 1 | 互動思考 | #倫理考量 | 完成 | Compare result 增加非即時交易指令提醒 |
| 1 | 互動思考 | #倫理勇氣 | 完成 | 將「建議」改成「報告建議變化」，避免過度順從報告 |
| 1 | 互動思考 | #倫理判斷 | 完成 | 測試鎖住使用提醒與建議語意邊界 |
| 1 | 互動思考 | #複雜因果 | 完成 | Compare result 增加報告差異不等於市場因果提醒 |
| 1 | 互動思考 | #湧現特性 | 完成 | 提醒使用者搭配資料可信度與追蹤報酬判讀 |
| 1 | 互動思考 | #分析層次 | 完成 | 將報告差異、資料可信度、追蹤報酬分層呈現 |
| 1 | 互動思考 | #網絡 | 完成 | Decision-needs-rerun warning 連回重跑流程 |
| 1 | 互動思考 | #系統動力學 | 完成 | 將資料更新後的正確順序寫成先重跑再比較 |
| 1 | 互動思考 | #系統圖像 | 完成 | Compare warning 呈現比較、資料、重跑的系統關係 |
| 1 | 互動思考 | #談判 | 完成 | Rerun warning 改成條件式「若要比較」語氣 |
| 1 | 互動思考 | #說服 | 完成 | 避免 warning 以命令式語氣強推使用者重跑 |
| 1 | 互動思考 | #形塑行為 | 完成 | 用條件式順序引導審慎比較流程 |
| 1 | 互動思考 | #從眾 | 完成 | Preview legacy 預設改為「報告建議」，避免 UI 強化跟隨式採用 |
| 1 | 互動思考 | #差異 | 完成 | 摘要補上「報告建議仍需自行判斷」，區分報告輸出與使用者判斷 |
| 1 | 互動思考 | #情緒智商 | 完成 | 移除預設裸「投資建議/建議」語氣，降低情緒化操作暗示 |
| 1 | 互動思考 | #領導原則 | 完成 | Preview 靜態骨架與 rerun CTA 改用「報告」語氣，帶領使用者看研究產物 |
| 1 | 互動思考 | #權力動態 | 完成 | 將「最終建議」改成「報告結論」，降低系統權威感 |
| 1 | 互動思考 | #責任 | 完成 | 靜態 preview 標題、label、aria 與按鈕一致標示報告層級 |
| 1 | 互動思考 | #自我覺察 | 完成 | History filter 承認自己是在篩選報告欄位，不是發布投資指令 |
| 1 | 互動思考 | #制定策略 | 完成 | 收尾互動思考 20/20，下一輪回到批判思考重新拆解問題 |
| 2 | 批判思考 | #拆解問題 | 完成 | 建立第 2 輪問題雷達，拆出報告正文、prompt 契約與前端顯示層 |
| 2 | 批判思考 | #問對問題 | 完成 | 將下一輪決策轉成「要不要分離契約/顯示層」的關鍵問題 |
| 2 | 批判思考 | #差距分析 | 完成 | 記錄第 1 輪已降權威語氣與剩餘正文契約風險的差距 |
| 2 | 批判思考 | #變數分析 | 完成 | 建立可改名顯示層與需保留契約層的變數表 |
| 2 | 批判思考 | #偏誤辨識 | 完成 | 明確標記字串潔癖偏誤與過度保守契約偏誤 |
| 2 | 批判思考 | #偏誤降低 | 完成 | 用解析契約回歸與前端契約測試作為改名護欄 |
| 2 | 批判思考 | #決策樹 | 完成 | 建立契約詞處理決策樹，分流顯示層、解析契約與完整報告正文 |
| 2 | 批判思考 | #目的 | 完成 | 明確目標是降低使用者入口權威感，同時保住報告解析契約 |
| 2 | 批判思考 | #效用 | 完成 | 選定最高效用路徑：先補 coverage map，再決定是否拆正文顯示詞 |
| 2 | 批判思考 | #信賴區間 | 完成 | 契約詞 coverage map 標示只涵蓋可維護來源檔，排除生成報告輸出 |
| 2 | 批判思考 | #相關性 | 完成 | 記錄「出現契約詞」不等於可替換或不可替換 |
| 2 | 批判思考 | #描述統計 | 完成 | 統計 tests 23 檔、backend 25 檔含契約詞 |
| 2 | 批判思考 | #機率 | 完成 | 將契約詞改動風險分成高/中/低機率回歸 |
| 2 | 批判思考 | #迴歸 | 完成 | 建立契約詞回歸測試組 |
| 2 | 批判思考 | #顯著性 | 完成 | 定義會觸發更廣測試矩陣的顯著性門檻 |
| 2 | 批判思考 | #證據基礎 | 完成 | 將 coverage map 與風險排序轉成契約測試矩陣 |
| 2 | 批判思考 | #演繹 | 完成 | 建立高/中/低顯著性改動到必跑測試的規則 |
| 2 | 批判思考 | #歸納 | 完成 | 記錄測試矩陣只能外推到目前可觀測來源與代表性流程 |
| 2 | 批判思考 | #謬誤 | 完成 | 將契約矩陣可能導致的錯誤推論寫成反謬誤護欄 |
| 2 | 批判思考 | #來源品質 | 完成 | 將測試、source、文件、生成輸出分成可用與不可作為完成證據的來源 |
| 2 | 批判思考 | #情境脈絡 | 完成 | 區分機器契約變更與使用者顯示層改動的適用情境 |
| 2 | 批判思考 | #批判 | 完成 | 評估契約矩陣過重風險，決定暫不新增自動選測腳本 |
| 2 | 批判思考 | #估算 | 完成 | 將高/中/低情境估算成 4/3/2 個測試檔的最小命令分組 |
| 2 | 批判思考 | #詮釋框架 | 完成 | 定義綠燈、紅燈與不得解讀為的結果框架 |
| 2 | 批判思考 | #合理性 | 完成 | 以契約矩陣、反謬誤護欄與最小命令分組作為合理收尾 |
| 2 | 批判思考 | #可驗證性 | 完成 | 建立第 2 輪批判思考 26/26 收尾 checkpoint |
| 2 | 創意思考 | #學習科學 | 完成 | 契約矩陣速學卡用三題降低學習成本 |
| 2 | 創意思考 | #限制條件 | 完成 | 保留不新增自動選測腳本的限制 |
| 2 | 創意思考 | #類比 | 完成 | 用三道安檢通道類比契約風險分流 |
| 2 | 創意思考 | #演算法 | 完成 | 將契約矩陣速學卡轉成四步操作流程 |
| 2 | 創意思考 | #設計思考 | 完成 | 補上 parser/prompt、報告模板、前端文案三個操作者情境 |
| 2 | 創意思考 | #捷思法 | 完成 | 補上三條快速判斷規則 |
| 2 | 創意思考 | #最佳化 | 完成 | 契約矩陣採用觀測板定義最佳化目標 |
| 2 | 創意思考 | #假說發展 | 完成 | 建立三個可觀察假說 |
| 2 | 創意思考 | #資料視覺化 | 完成 | 用綠/黃/紅採用訊號矩陣呈現人工 review 訊號 |
| 2 | 創意思考 | #建模 | 完成 | 建立三類契約矩陣案例模型 |
| 2 | 創意思考 | #抽樣 | 完成 | 定義代表性抽樣規則 |
| 2 | 創意思考 | #個案研究 | 完成 | 建立案例卡格式 |
| 2 | 創意思考 | #比較組 | 完成 | 建立基準組與介入組比較 |
| 2 | 創意思考 | #介入研究 | 完成 | 定義案例卡介入方案 |
| 2 | 創意思考 | #訪談調查 | 完成 | 建立三題操作者回饋 |
| 2 | 創意思考 | #觀察研究 | 完成 | 定義契約矩陣觀察記錄欄位 |
| 2 | 創意思考 | #研究複製 | 完成 | 定義複製檢查清單與完成條件 |
| 2 | 溝通思考 | #受眾 | 完成 | 契約矩陣讀者路徑分出三種維護者受眾 |
| 2 | 溝通思考 | #組成 | 完成 | 建立先讀速學卡、再用操作流程、最後填案例卡的閱讀順序 |
| 2 | 溝通思考 | #語意含義 | 完成 | 明確標出文件契約、觀察紀錄與低顯著性的語意邊界 |
| 2 | 溝通思考 | #組織結構 | 完成 | 契約矩陣維護導覽建立章節順序 |
| 2 | 溝通思考 | #專業性 | 完成 | 維護語氣限制測試綠燈的可宣稱範圍 |
| 2 | 溝通思考 | #論點 | 完成 | 核心論點收斂為人工判斷加最小測試驗證 |
| 2 | 溝通思考 | #溝通設計 | 完成 | 契約矩陣一頁摘要建立三步短版判斷 |
| 2 | 溝通思考 | #表達 | 完成 | 新增通道、命令與限制的建議表達句型 |
| 2 | 溝通思考 | #媒介 | 完成 | 決定文字與表格優先 |
| 2 | 溝通思考 | #多媒體 | 完成 | 暫不新增圖像或多媒體，保留文字限制 |
| 2 | 互動思考 | #倫理考量 | 完成 | 契約矩陣倫理邊界新增不得誇大測試綠燈的底線 |
| 2 | 互動思考 | #倫理勇氣 | 完成 | 明確必要時要說不的阻擋條件 |
| 2 | 互動思考 | #倫理判斷 | 完成 | 建立允許/禁止敘述與升級條件 |
| 2 | 互動思考 | #複雜因果 | 完成 | 建立局部證據到錯誤推論的複雜因果圖譜 |
| 2 | 互動思考 | #湧現特性 | 完成 | 記錄低顯著性累積、跨模式模糊與觀察替代驗證風險 |
| 2 | 互動思考 | #分析層次 | 完成 | 區分文件層、測試層、runtime 層與使用者行為層 |
| 2 | 互動思考 | #網絡 | 完成 | 建立契約矩陣維護網絡 |
| 2 | 互動思考 | #系統動力學 | 完成 | 記錄語氣、觀察與升級條件的動態回路 |
| 2 | 互動思考 | #系統圖像 | 完成 | 建立改動定位、證據對齊與倫理宣稱流程 |
| 2 | 互動思考 | #談判 | 完成 | 契約矩陣 review 對話建立補證據協商 |
| 2 | 互動思考 | #說服 | 完成 | 把補跑、升級與拆分說成降低錯放與 review 成本 |
| 2 | 互動思考 | #形塑行為 | 完成 | 建立一頁摘要、案例卡與採用訊號的預設行為 |
| 2 | 互動思考 | #從眾 | 完成 | review 防從眾檢查禁止用多數同意、前例綠燈或測試全綠取代證據 |
| 2 | 互動思考 | #差異 | 完成 | 差異保留要求通道、模式與證據層分開回報 |
| 2 | 互動思考 | #情緒智商 | 完成 | 高壓 review 先命名壓力，再回到最小補證據路徑與限制句 |
| 2 | 互動思考 | #領導原則 | 完成 | review 責任分工要求主責宣告改動層級並由 review 主導者要求升級 |
| 2 | 互動思考 | #權力動態 | 完成 | 權力護欄禁止用職位、資深度或合併權限取代證據 |
| 2 | 互動思考 | #責任 | 完成 | 改動者、reviewer、合併者分別負責層級、通道命令與限制句 |
| 2 | 互動思考 | #自我覺察 | 完成 | review 自我稽核承認契約矩陣不是自動化審核器，避免過度官僚 |
| 2 | 互動思考 | #制定策略 | 完成 | 收尾策略要求最小足夠路徑，並將下一批推進到第 3 輪批判思考 |
| 3 | 批判思考 | #拆解問題 | 完成 | 契約矩陣第 3 輪問題雷達拆出矩陣過重、2 分鐘選通道、低顯著性被拖慢與限制句落地問題 |
| 3 | 批判思考 | #問對問題 | 完成 | 將下一批焦點改成一頁摘要可取代什麼、完整矩陣何時必須保留、哪個證據層缺 runtime 驗證 |
| 3 | 批判思考 | #差距分析 | 完成 | 對照已完成矩陣能力與仍缺的日常入口、限制句驗證、輕量通道誤用防線 |
| 3 | 批判思考 | #變數分析 | 完成 | 契約矩陣第 3 輪護欄拆出改動層級、證據層、可逆性與時程壓力 |
| 3 | 批判思考 | #偏誤辨識 | 完成 | 標出過度升級、過度降級、工具化幻覺與綠燈擴張偏誤 |
| 3 | 批判思考 | #偏誤降低 | 完成 | 建立一頁摘要優先、跨層改動升級、證據分層回報、限制句必填與案例卡觸發 |
| 3 | 批判思考 | #決策樹 | 完成 | 契約矩陣第 3 輪分流決策把低顯著性、高顯著性、混合層、跨層與文件層排成五步 |
| 3 | 批判思考 | #目的 | 完成 | 目的校準聚焦降低 2 分鐘選通道摩擦、保住高顯著性契約、防止綠燈擴張與保留低顯著性效率 |
| 3 | 批判思考 | #效用 | 完成 | 效用校準列出規則、預期效用、成本與升級或停用條件 |
| 3 | 批判思考 | #信賴區間 | 完成 | 證據校準標出目前樣本、不可外推範圍與觀察窗口 |
| 3 | 批判思考 | #相關性 | 完成 | 觀測訊號只支持關聯，不代表因果或 runtime 已驗證 |
| 3 | 批判思考 | #描述統計 | 完成 | 定義樣本數、中位選通道時間、錯選率、跨層改動比例、案例卡觸發率與限制句出現率 |
| 3 | 批判思考 | #機率 | 完成 | 將錯選率、限制句缺漏率與案例卡漏觸發率轉成風險機率判讀 |
| 3 | 批判思考 | #迴歸 | 完成 | 用連續兩個觀察窗口與紅色高風險例外定義回歸監測 |
| 3 | 批判思考 | #顯著性 | 完成 | 設定至少 5 個案例、升級門檻與不得宣稱改善限制 |
| 3 | 批判思考 | #證據基礎 | 完成 | 將文件契約測試、觀察窗口紀錄與案例卡分成可接受證據，並列出不可作為證據的訊號 |
| 3 | 批判思考 | #演繹 | 完成 | 建立立即升級、小樣本限制與連續窗口回歸的推論規則 |
| 3 | 批判思考 | #歸納 | 完成 | 明確文件測試、觀察窗口與案例卡不得外推到 runtime、使用者理解或生成報告母體 |
| 3 | 批判思考 | #謬誤 | 完成 | 將測試綠燈謬誤、樣本數謬誤與案例代表性謬誤寫成護欄 |
| 3 | 批判思考 | #來源品質 | 完成 | 將高品質來源、次級來源與不得作為完成證據分級 |
| 3 | 批判思考 | #情境脈絡 | 完成 | 限定護欄只適用於契約相關變更，並標出人工 review 與 runtime/使用者研究邊界 |
| 3 | 批判思考 | #批判 | 完成 | 批判矩陣過重風險，區分必留護欄、可短句替代與可延後工具化 |
| 3 | 批判思考 | #估算 | 完成 | 估算低風險 UI、混合層報告呈現與高風險契約的完成回報成本 |
| 3 | 批判思考 | #詮釋框架 | 完成 | 建立文件契約通過、觀察窗口、runtime 驗證與使用者研究的完成回報詮釋框架 |
| 3 | 批判思考 | #合理性 | 完成 | 以第 3 輪契約矩陣能力、人工判斷邊界與不新增自動選測腳本作為合理收尾 |
| 3 | 批判思考 | #可驗證性 | 完成 | 建立第 3 輪批判思考 26/26 收尾 checkpoint 與下一分類入口 |
| 3 | 創意思考 | #學習科學 | 完成 | 契約矩陣創意學習入口用三層學習路徑降低第一次使用負擔 |
| 3 | 創意思考 | #限制條件 | 完成 | 明確不改 runtime、不新增自動選測腳本、不新增遙測、不替代人工 review |
| 3 | 創意思考 | #類比 | 完成 | 用登機前安檢類比快速通道、人工複檢與證據托盤 |
| 3 | 創意思考 | #演算法 | 完成 | 將學習入口轉成判斷、選通道、裝證據托盤、完成回報四步操作 |
| 3 | 創意思考 | #設計思考 | 完成 | 分出低風險 UI、報告模板或正文呈現、高風險契約三個操作者情境 |
| 3 | 創意思考 | #捷思法 | 完成 | 建立核心契約詞先人工複檢、只在前端顯示才快速通道、缺限制句不得完成三條規則 |
| 3 | 創意思考 | #最佳化 | 完成 | 將錯選通道、漏跑命令、限制句缺漏與案例卡漏補定義為採用摩擦 |
| 3 | 創意思考 | #假說發展 | 完成 | 建立四步操作、證據托盤、三條快速規則的三個可觀察假說 |
| 3 | 創意思考 | #資料視覺化 | 完成 | 用綠色、黃色、紅色採用訊號板呈現人工觀察結果 |
| 3 | 創意思考 | #建模 | 完成 | 建立四類代表性案例模型 |
| 3 | 創意思考 | #抽樣 | 完成 | 定義每個觀察窗口的代表性抽樣與黃色/紅色必抽規則 |
| 3 | 創意思考 | #個案研究 | 完成 | 建立案例卡格式與不可外推欄位 |
| 3 | 創意思考 | #比較組 | 完成 | 建立基準組與介入組比較設計 |
| 3 | 創意思考 | #介入研究 | 完成 | 定義改檔前案例模型選擇、三欄回報與補救回放 |
| 3 | 創意思考 | #訪談調查 | 完成 | 建立三題操作者回饋題 |
| 3 | 創意思考 | #觀察研究 | 完成 | 建立第 3 輪觀察記錄欄位 |
| 3 | 創意思考 | #研究複製 | 完成 | 建立複製檢查清單與可複製完成條件 |
| 3 | 溝通思考 | #受眾 | 完成 | 分出四種讀者角色 |
| 3 | 溝通思考 | #組成 | 完成 | 建立四步讀者入口組成 |
| 3 | 溝通思考 | #語意含義 | 完成 | 定義讀者角色、入口、觀察欄位與複製成功的語意邊界 |
| 3 | 溝通思考 | #組織結構 | 完成 | 契約矩陣第 3 輪維護導覽建立章節導覽 |
| 3 | 溝通思考 | #專業性 | 完成 | 維護語氣限制觀察窗口、未跑命令、紅色訊號與測試綠燈的可宣稱範圍 |
| 3 | 溝通思考 | #論點 | 完成 | 核心主張收斂為低風險更快收尾、高風險更早升級、觀察可複製但不誤讀 |
| 3 | 溝通思考 | #溝通設計 | 完成 | 契約矩陣第 3 輪短版回報建立一頁摘要 |
| 3 | 溝通思考 | #表達 | 完成 | 建議句型固定通道、命令與不得解讀為 |
| 3 | 溝通思考 | #媒介 | 完成 | 決定文字與表格優先，不新增圖像流程 |
| 3 | 溝通思考 | #多媒體 | 完成 | 暫不新增圖像或多媒體，保留可搜尋文字、pytest 與人工 review |
| 3 | 互動思考 | #倫理考量 | 完成 | 契約矩陣第 3 輪倫理阻擋建立短版回報倫理底線 |
| 3 | 互動思考 | #倫理勇氣 | 完成 | 必要時說不：缺證據停止合併、交易指令補責任邊界、高風險降級回人工複檢 |
| 3 | 互動思考 | #倫理判斷 | 完成 | 建立允許回報、禁止回報與升級判斷 |
| 3 | 互動思考 | #複雜因果 | 完成 | 建立局部綠燈因果圖，限制文件、前端測試與倫理阻擋的跨層誤推 |
| 3 | 互動思考 | #湧現特性 | 完成 | 記錄快速通道累積、案例卡增加但驗證減少、阻擋規則不敢啟用三種湧現風險 |
| 3 | 互動思考 | #分析層次 | 完成 | 區分文件層、測試層、runtime 層與使用者行為層 |
| 3 | 互動思考 | #網絡 | 完成 | 建立第 3 輪維護網絡，連接文件、測試、runtime、使用者行為與 reviewer 阻擋節點 |
| 3 | 互動思考 | #系統動力學 | 完成 | 記錄快速通道、案例卡、阻擋勇氣與跨層宣稱四個動態回路 |
| 3 | 互動思考 | #系統圖像 | 完成 | 建立先定位證據層、再連節點、接著判斷回路、最後同層宣稱或升級驗證的操作圖像 |
| 3 | 互動思考 | #談判 | 完成 | 建立補證據協商句型，保留同層宣稱但不降低跨層證據標準 |
| 3 | 互動思考 | #說服 | 完成 | 建立先承認證據、再指出缺口、接著提出最小補證據、最後寫限制句的說服路徑 |
| 3 | 互動思考 | #形塑行為 | 完成 | 建立完成回報預設三欄與黃色、紅色、跨層宣稱的預設升級行為 |
| 3 | 互動思考 | #從眾 | 完成 | 建立第 3 輪防從眾檢查，禁止多數同意、前例綠燈、測試全綠與合併壓力取代證據 |
| 3 | 互動思考 | #差異 | 完成 | 建立差異訊號清單，保留改動層級、證據層、pipeline 模式與風險顏色差異 |
| 3 | 互動思考 | #情緒智商 | 完成 | 建立高壓語氣處理，先命名壓力來源，再回到預設三欄與最小補證據路徑 |
| 3 | 互動思考 | #領導原則 | 完成 | 建立證據領導，要求主責、review 主導者與合併者分別維持宣稱層級、升級權與紅黃訊號處理 |
| 3 | 互動思考 | #權力動態 | 完成 | 建立權力護欄，禁止合併權限、資深度或權威催促取代證據層與預設三欄 |
| 3 | 互動思考 | #責任 | 完成 | 建立角色責任，讓改動者、reviewer、合併者分別負責證據、限制句、未跑命令與剩餘風險 |
| 3 | 互動思考 | #自我覺察 | 完成 | 建立輕量使用邊界，避免角色責任變成形式簽核或自動審核假象 |
| 3 | 互動思考 | #制定策略 | 完成 | 以 20/20 收尾第 3 輪互動思考，下一步進入三習慣綜合優化 |
| 綜合 | 三習慣綜合優化 | #可驗證性 | 完成 | 建立驗證閘門，要求完成宣稱對應命令、證據層或限制句 |
| 綜合 | 三習慣綜合優化 | #溝通設計 | 完成 | 建立完成回報格式，固定本次宣稱層級、已補證據、仍不得解讀為與下一個可執行行動 |
| 綜合 | 三習慣綜合優化 | #系統圖像 | 完成 | 建立前端顯示層、報告呈現層、機器契約層與維運決策層的系統圖像收斂 |
| 綜合 | 三習慣綜合優化 2 | #證據基礎 | 完成 | 建立證據來源分級，區分直接證據、間接證據、缺口證據與未跑命令 |
| 綜合 | 三習慣綜合優化 2 | #受眾 | 完成 | 建立讀者角色分流，讓不同維護者先讀對應入口 |
| 綜合 | 三習慣綜合優化 2 | #責任 | 完成 | 建立責任承接，讓改動者、reviewer、合併者分別承擔證據、誤讀與剩餘風險 |
| 綜合 | 三習慣綜合優化 3 | #偏誤降低 | 完成 | 建立偏誤防線，防止表格打勾、證據漂白、升級逃避與流程膨脹 |
| 綜合 | 三習慣綜合優化 3 | #學習科學 | 完成 | 建立速學入口，用 10 秒定位、90 秒分流、5 分鐘復盤降低採用成本 |
| 綜合 | 三習慣綜合優化 3 | #制定策略 | 完成 | 建立策略收斂，保留輕量通道、升級高顯著性、刪減膨脹規則 |
| 綜合 | 三習慣綜合優化 4 | #目的 | 完成 | 建立目標校準，要求矩陣服務股票研究系統核心目標 |
| 綜合 | 三習慣綜合優化 4 | #效用 | 完成 | 建立效用門檻，要求規則降低錯選模式、漏跑命令、跨層外推或維護成本 |
| 綜合 | 三習慣綜合優化 4 | #合理性 | 完成 | 建立合理性審核，固定必要性、比例性、可驗證性與可逆性 |
| 綜合 | 三習慣綜合優化 5 | #限制條件 | 完成 | 建立限制邊界，分出硬限制、軟限制、升級限制與停用限制 |
| 綜合 | 三習慣綜合優化 5 | #決策樹 | 完成 | 建立四步分流決策，依改動層級、顯著性、證據缺口選處理方式 |
| 綜合 | 三習慣綜合優化 5 | #最佳化 | 完成 | 建立成本最佳化，保留輕量通道、合併重複規則、刪除低效用規則 |
| 綜合 | 三習慣綜合優化 6 | #來源品質 | 完成 | 建立來源分級，區分高可信來源、可用但有限來源、不得作為完成證據與缺口來源 |
| 綜合 | 三習慣綜合優化 6 | #情境脈絡 | 完成 | 建立適用情境，分開低風險文件、報告語意、機器契約與維運決策 |
| 綜合 | 三習慣綜合優化 6 | #批判 | 完成 | 建立批判反證，要求規則回答失效情境、證據層級與刪減可能 |
| 綜合 | 三習慣綜合優化 7 | #估算 | 完成 | 建立把握估算，區分高把握、中把握、低把握與不得宣稱 |
| 綜合 | 三習慣綜合優化 7 | #信賴區間 | 完成 | 建立信心邊界，要求標示適用層級、證據覆蓋與剩餘不確定 |
| 綜合 | 三習慣綜合優化 7 | #詮釋框架 | 完成 | 建立解讀框架，分成已驗證、有限支持、暫定假設與未證明 |
| 綜合 | 三習慣綜合優化 8 | #相關性 | 完成 | 建立關聯檢核，分出強支撐、弱支撐、衝突支撐與無關 |
| 綜合 | 三習慣綜合優化 8 | #描述統計 | 完成 | 建立分布摘要，描述完成分布、缺口分布、驗證分布與風險分布 |
| 綜合 | 三習慣綜合優化 8 | #顯著性 | 完成 | 建立顯著性門檻，分出升級、保留、降級與刪減訊號 |
| 綜合 | 三習慣綜合優化 9 | #機率 | 完成 | 建立概率語言，分出高可能、中可能、低可能與未知或不得推定 |
| 綜合 | 三習慣綜合優化 9 | #迴歸 | 完成 | 建立迴歸風險，檢查回到過度宣稱、跨層外推、流程膨脹與弱證據升級 |
| 綜合 | 三習慣綜合優化 9 | #謬誤 | 完成 | 建立謬誤防線，阻止相關當因果、測試當 runtime 安全、文件完整當使用者理解、歷史紀錄當新證據 |
| 綜合 | 三習慣綜合優化 10 | #合理性 | 完成 | 建立合理性收尾，確認十次綜合優化仍服務核心目標與契約安全邊界 |
| 綜合 | 三習慣綜合優化 10 | #可驗證性 | 完成 | 建立驗證門檻，要求聚焦測試、回歸集合、diff check、strict log、狀態表與契約章節 |
| 綜合 | 三習慣綜合優化 10 | #制定策略 | 完成 | 建立完成後維護策略，採文件與測試契約優先、例外升級與定期複檢 |

## 第 1 輪批判思考第一批

### 第 1 輪 / 批判思考 / #拆解問題

狀態：完成

本次使用：把「自主優化」拆成可保存、可驗證、可繼續的工作單位，避免一次性大改造成不可審查的變更。

核心判斷

1. 既有狀態表已完成四大類批次收斂，但未能證明每個 HCS 單項習慣都有獨立落地。
2. 專案規模很大，直接重構程式碼會提高風險；先建立嚴格輪巡紀錄，讓後續修改有清楚檢查點。
3. 最小可逆切入點是文件與文件契約測試，不改動 runtime 行為。

落地修改

1. 新增 `docs/hcs-plus-strict-habit-log.md`，把完整 HCS 單項清單與本批次狀態拆出。
2. 在主狀態表新增嚴格單項輪巡入口，避免後續只看舊的四大類摘要。

優化說明

1. 解決「已完成類別但未完成單項」的追蹤落差。
2. 犧牲的是短期看不到產品功能改變；換來後續每批修改可審查、可接續。
3. 風險是流程文件本身也可能變成形式主義，因此下一步需用測試鎖住最低內容。

驗證方式

- `tests/test_hcs_plus_state.py` 檢查主狀態表有引用嚴格輪巡附件，且附件列出全部 HCS 單項習慣。

### 第 1 輪 / 批判思考 / #問對問題

狀態：完成

本次使用：把接下來的優化從「想改什麼」轉成「哪個決策最影響專案可靠性」。

核心判斷

1. 目前最高影響問題不是新增功能，而是如何降低報告、前端模式、資料可信度與維運文件之間的漂移。
2. 下一批若直接改 UI，可能繞過資料與報告契約；若只改文件，可能沒有使用者可感的進步。
3. 最佳暫定路線是「文件契約 + 小型測試 + 一個實際體驗修正」輪流推進。

落地修改

1. 新增本輪暫定決策：嚴格輪巡每批最多處理 3 到 5 個單項習慣，並至少補一個自動化檢查。
2. 將下一個待決問題寫入本文件：下一批要優先降低偏誤、建立決策樹，還是先收斂目的/效用。

需要你決定

1. 下一批優先方向
A. 先補齊批判思考剩餘習慣的文件與測試護欄
B. 先找一個前端或報告的小型使用者體驗問題落地修正
C. 先做資料可信度或 provider contract 的程式碼改善
建議：B，因為本批次已建立流程護欄，下一批應讓使用者可感的系統品質也跟上。

驗證方式

- 本文件保留決策題與建議選項；若使用者未回答，下一批採用建議 B 並在主狀態表記為暫定決策。

### 第 1 輪 / 批判思考 / #差距分析

狀態：完成

本次使用：比較現況與目標，找出最值得先補的缺口。

核心判斷

1. 現況：`docs/frontend-design-checkpoints.md` 與 `docs/pipeline-mode-contract.md` 已降低 UI/報告模式漂移。
2. 目標：每次自主優化都能說清楚修改位置、驗證方式、下一個檢查點。
3. 缺口：HCS 狀態沒有自動化檢查，且後續嚴格單項輪巡若只靠人工記憶，很容易漏項。

落地修改

1. 新增缺口矩陣作為後續排序依據。
2. 新增 `tests/test_hcs_plus_state.py`，用自動化測試檢查嚴格輪巡清單與第一批完成項。

缺口矩陣

| 目標 | 現況 | 缺口 | 本批處理 |
|---|---|---|---|
| HCS 單項不漏項 | 只有四大類摘要 | 單項清單未被測試鎖住 | 新增嚴格輪巡附件與測試 |
| 修改可追蹤 | 舊摘要列出檔案 | 單項習慣沒有獨立紀錄 | 第一批 5 個習慣逐項記錄 |
| 驗證可重跑 | 多數產品契約已有測試 | HCS 流程文件無測試 | 新增文件契約測試 |

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_strict_habit_log_lists_every_habit`
- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`

### 第 1 輪 / 批判思考 / #變數分析

狀態：完成

本次使用：列出最可能改變優化判斷的變數，避免把單一 UI 或文件問題誤當成全域問題。

核心判斷

1. 系統可靠性由多個變數共同決定：資料來源、pipeline 模式、報告模板、任務佇列、前端呈現、維運文件與測試覆蓋。
2. 同一個修改若影響 pipeline、報告與前端三層，需優先補契約測試。
3. 若變數屬於使用者行為，例如操作者如何選模式，則應優先改善文案、狀態提示與下一步引導。

落地修改

1. 新增 HCS 變數清單，後續每批優化都先標記影響哪幾個變數。
2. 將本批次影響變數標為 `流程可追蹤性`、`測試覆蓋`、`文件一致性`。

變數清單

| 變數 | 影響 | 後續檢查 |
|---|---|---|
| 資料來源可用性 | 影響 data confidence、target price guardrail 與 provider SLA | `tests/test_provider_capabilities.py`、`tests/test_free_mode_contract.py` |
| Pipeline 模式語意 | 影響 UI 選擇、報告模板與 watchlist rerun | `tests/test_report_mode_templates.py`、`tests/test_static_history_filters.py` |
| 報告證據鏈 | 影響數字主張、投資建議與人工信任 | `tests/test_evidence_exit_gate.py`、`tests/test_report_conformance.py` |
| 前端掃讀性 | 影響操作者是否選對模式與是否注意 stale report | `tests/test_static_history_filters.py`、optional visual regression |
| 流程可追蹤性 | 影響 HCS 優化能否接續 | `tests/test_hcs_plus_state.py` |

驗證方式

- 本文件把本批次影響變數與現有測試檔對應，下一批不得只寫抽象建議。

### 第 1 輪 / 批判思考 / #偏誤辨識

狀態：完成

本次使用：找出自主優化最容易出現的判斷偏誤，並建立最低護欄。

核心判斷

1. 最大偏誤是「文件完成感」：寫了漂亮狀態表卻沒有防止漏項或回退。
2. 第二個偏誤是「最近性偏誤」：只因前一輪做前端，就假設下一輪也該繼續前端。
3. 第三個偏誤是「測試可得性偏誤」：只挑容易測的內容，而忽略使用者實際工作流痛點。

落地修改

1. 新增偏誤風險清單，明確要求下一批至少選一個使用者可感的品質改動。
2. 新增文件契約測試，防止 HCS 單項清單與第一批落地紀錄消失。

偏誤護欄

| 偏誤 | 失敗徵兆 | 護欄 |
|---|---|---|
| 文件完成感 | 只有紀錄，沒有測試或產品改動 | 每批至少一個可重跑驗證 |
| 最近性偏誤 | 永遠沿著上一輪主題微調 | 每批先重看 README、架構與近期測試缺口 |
| 測試可得性偏誤 | 只補容易 assert 的字串 | 至少列出一個使用者可感檢查點 |
| 自動化過度自信 | 測試通過就宣稱整體優化完成 | 未完成 3 輪單項巡迴前不得宣稱 HCS Plus 完成 |

驗證方式

- `tests/test_hcs_plus_state.py` 確認第一批完成項都有 `核心判斷`、`落地修改`、`驗證方式` 與 `狀態：完成`。

## 第 1 輪批判思考第二批

### 第 1 輪 / 批判思考 / #偏誤降低

狀態：完成

本次使用：把上一批辨識出的「文件完成感」與「最近性偏誤」轉成具體防護，避免新文件範例和模式契約各說各話。

核心判斷

1. `README.md` 與 `docs/api.md` 的 `POST /api/analysis-jobs` 範例仍使用 `pipeline_id:"mode_a"` alias，和目前 `v1` 到 `v4` 的模式契約不一致。
2. 後端保留 alias 是相容性，不代表新文件應繼續推廣 alias。
3. 最小偏誤降低方式是把文件範例改成 canonical id，並用 docs contract 測試鎖住。

落地修改

1. 將 `README.md` 與 `docs/api.md` 的分析任務範例改為 `pipeline_id:"v1"`。
2. 在 `docs/pipeline-mode-contract.md` 增加規則：新整合與文件範例使用 `v1` / `v2` / `v3` / `v4`，alias 只作相容輸入。
3. 新增 `tests/test_docs_contract.py::test_analysis_job_docs_use_canonical_pipeline_ids`。

優化說明

1. 降低新整合者照文件使用 alias 後，誤以為 `mode_a` 是主要公開契約的風險。
2. 犧牲的是少了一點「舊名稱較直覺」的便利；但 UI 與契約文件已用中文模式名稱補足語意。
3. 保留後端 alias 相容，不破壞現有腳本。

驗證方式

- `tests/test_docs_contract.py::test_analysis_job_docs_use_canonical_pipeline_ids`

### 第 1 輪 / 批判思考 / #決策樹

狀態：完成

本次使用：在三個候選路徑中選擇本批修改：前端體驗、資料可信度或文件契約。

核心判斷

1. 前端體驗修改需要瀏覽器或截圖驗證，適合下一批搭配 visual/DOM 檢查。
2. 資料可信度修改會碰 provider 或 report runtime，風險較高，不適合作為嚴格輪巡剛啟動後的第二步。
3. 文件契約修改最小、可逆、可測，且直接對齊已建立的 `docs/pipeline-mode-contract.md`。

落地修改

1. 採用「文件契約先行」路徑，修改 README/API/模式契約三處。
2. 把決策樹寫入本紀錄，作為下次遇到類似漂移時的選擇依據。

決策樹

| 條件 | 選擇 |
|---|---|
| 發現的是公開文件與既有契約不一致 | 先修文件範例，補 docs contract 測試 |
| 發現的是 UI 文案與資料狀態不一致 | 先修前端，補 DOM/視覺檢查 |
| 發現的是資料可信度或 report guardrail 不一致 | 先補 failing backend test，再改 runtime |

驗證方式

- `tests/test_docs_contract.py` 確保 canonical pipeline id 規則存在於 README、API 參考與模式契約。

### 第 1 輪 / 批判思考 / #目的

狀態：完成

本次使用：把本批修改目的從「整理文件」收斂成使用者結果。

核心判斷

1. 使用者要的是能照文件建立正確分析任務，而不是理解所有 alias 歷史。
2. 文件範例應教 canonical path；相容 alias 只該出現在後端測試或遷移說明。
3. 對本地操作者而言，`v1` 對應模式 A 的關係已由 pipeline mode contract 承擔。

落地修改

1. README 與 API 參考的新任務範例改用 canonical `v1`。
2. 模式契約新增「文件與新整合範例一律使用 canonical pipeline ids」的目的說明。

驗證方式

- docs contract 測試檢查文件含有 `"pipeline_id":"v1"`，且不再含有 `"pipeline_id":"mode_a"`。

### 第 1 輪 / 批判思考 / #效用

狀態：完成

本次使用：衡量本批修改的效用、代價與剩餘風險。

核心判斷

1. 效用：降低 API 使用者照抄文件後產生 ID 語意混亂的機率。
2. 代價：沒有新增產品功能；這是一次低風險一致性修正。
3. 剩餘風險：測試目前只鎖住 `mode_a` 範例，其他 alias 若未來出現在文件，需再擴充測試。

落地修改

1. 將本批效用與剩餘風險寫入 HCS 嚴格紀錄，避免把測試通過誤認為整體流程完成。
2. 主狀態表更新第二批已完成與下一批待辦。

驗證方式

- `tests/test_hcs_plus_state.py` 檢查第二批四個習慣也有獨立的核心判斷、落地修改與驗證方式。

## 第 1 輪批判思考第三批

### 第 1 輪 / 批判思考 / #信賴區間

狀態：完成

本次使用：檢查操作者看到任務狀態時，是否能對「這是哪一種分析」形成足夠信心。

核心判斷

1. Active jobs panel 原本顯示 raw `pipeline_id`，例如 `v1`、`v4`；這對熟悉契約的人可讀，但對日常操作者信心不足。
2. 既有 `StockAgentUi.pipelineModeLabel` 已能輸出「模式 A · 學術深度派」等語意，不應只用在 history/watchlist。
3. 將 active jobs 接上共用 label 可以縮小操作者對任務類型的理解區間。

落地修改

1. `backend/static/active_jobs_panel.js` 新增 `pipelineModeLabel` option 與 `StockAgentUi.pipelineModeLabel` fallback。
2. `backend/static/ops_workspace.js` 呼叫 active jobs render 時傳入 `ui.pipelineModeLabel`。
3. `tests/test_static_history_filters.py` 新增合約檢查，防止 active jobs 回退成 raw pipeline id 顯示。

優化說明

1. 解決 active jobs 與其他模式顯示元件語意不一致的問題。
2. 代價很低：只改前端顯示，不改 API payload 或 job store。
3. 剩餘風險是 operator summary 的簡短卡片仍只顯示 ticker；若後續需要，可再加入目前任務模式摘要。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 批判思考 / #相關性

狀態：完成

本次使用：避免操作者把 raw pipeline id 與任務狀態直接關聯，誤以為 `v1` / `v4` 是狀態或優先級，而不是分析模式。

核心判斷

1. Active job chip 同時顯示 ticker、pipeline、status、stage；raw `v1` 容易被看成內部狀態碼。
2. 共用模式 label 把 `pipeline_id` 和分析目的連起來，降低錯誤關聯。
3. 相關性護欄應落在 UI helper 共用，而不是在 active jobs panel 再寫一份 label map。

落地修改

1. Active jobs panel 不新增獨立模式表，改用 `pipelineModeLabel` 注入。
2. 前端契約測試要求 active jobs panel 與 ops workspace 有共用 label 接線。

驗證方式

- 測試檢查 `active_jobs_panel.js` 包含 `pipelineModeLabel`，且 `ops_workspace.js` 傳入 `pipelineModeLabel: ui.pipelineModeLabel`。

### 第 1 輪 / 批判思考 / #描述統計

狀態：完成

本次使用：檢查任務列表摘要是否保留最小有效統計資訊，而不是加入太多欄位造成掃讀負擔。

核心判斷

1. Active jobs 的摘要重點是任務數、ticker、模式、狀態、階段進度與 LLM retry/error 訊號。
2. 既有 panel 已刻意不顯示 token estimate，避免把估算數字當成精準成本。
3. 本批只替換 pipeline 顯示文字，不增加額外統計欄位，保留原本密度。

落地修改

1. 保留 `llmSummary()`、`progressLabel()` 與 summary count 的既有行為。
2. 只把 job chip 的第二段從 raw id 改成共用模式 label。

驗證方式

- 前端合約測試仍要求 `token_estimate` 與 `估算 token` 不出現在 active jobs panel，並新增模式 label 接線要求。

## 第 1 輪批判思考第四批

### 第 1 輪 / 批判思考 / #機率

狀態：完成

本次使用：檢查決策回測的命中率呈現，避免把少量樣本的百分比讀成穩定機率。

核心判斷

1. Performance panel 原本顯示 `命中率 / 平均 ROI / N 筆`，少量樣本也會以同樣語氣呈現。
2. 對本機研究工作台而言，早期回測多半樣本少；命中率應被視為觀察訊號，不是穩定勝率。
3. 最小修正是在 summary 與 horizon chip 加上樣本信心標籤。

落地修改

1. `backend/static/performance_panel.js` 新增 `sampleConfidenceLabel(total)`。
2. Summary 顯示加入 `樣本不足，僅供觀察`、`樣本基礎可追蹤` 或 `尚無樣本`。
3. Horizon chip 的命中率旁同步顯示樣本信心。

優化說明

1. 解決百分比在小樣本下過度精準的閱讀風險。
2. 犧牲的是 summary 變長；但保留同一行密度，沒有新增額外卡片。
3. 目前 10 筆門檻是產品護欄，不是統計顯著性證明。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 批判思考 / #迴歸

狀態：完成

本次使用：檢查回測結果是否被 UI 暗示成可外推趨勢。

核心判斷

1. `average_strategy_roi_pct` 是歷史已到期決策的平均結果，不等於下一次報告的預測報酬。
2. 小樣本下高 ROI 容易受單一極端案例影響，不能當成模式品質已穩定的迴歸趨勢。
3. UI 只需要提醒「樣本基礎」即可，不應在前端臨時計算複雜統計模型。

落地修改

1. Performance panel 保留原本平均 ROI，但在同一 summary 補上樣本信心。
2. Horizon chip 以 `total >= 10` 才使用 `is-ok` 語氣，少量樣本維持 warning。

驗證方式

- 前端契約測試檢查 `performance_panel.js` 有 `sampleConfidenceLabel` 與 `total >= 10` 門檻。

### 第 1 輪 / 批判思考 / #顯著性

狀態：完成

本次使用：把「是否足以採信」轉成明確的 UI 文案，而不是讓使用者自行從樣本數推斷。

核心判斷

1. UI 不應宣稱統計顯著；目前資料也沒有 confidence interval 或 p-value。
2. 10 筆以下使用「樣本不足，僅供觀察」比「低信心」更準確，因為不是資料錯誤，而是樣本量不足。
3. 10 筆以上也只標示「樣本基礎可追蹤」，避免過度承諾。

落地修改

1. `tests/test_static_history_filters.py` 新增靜態契約，要求樣本不足文案與門檻保留。
2. HCS 狀態測試擴充到 `#機率`、`#迴歸`、`#顯著性`。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪批判思考第五批

### 第 1 輪 / 批判思考 / #證據基礎

狀態：完成

本次使用：檢查使用者打開報告 preview 時，是否仍能看到證據抽查與報告符合性的品質訊號。

核心判斷

1. History 清單已有 `evidence_exit_gate` 與 `report_conformance` 的警示 badge。
2. Preview 頂部原本只顯示模式、資料信任與日期；使用者一打開 preview，品質警示會從視覺焦點消失。
3. 證據基礎應在 preview 入口保留，而不是只存在 history list 或完整報告內文。

落地修改

1. `backend/static/report_preview_panel.js` 新增 `reportQualityBadge(report, escapeHtml)`。
2. Preview mode row 會在資料信任 badge 後顯示「報告符合性未通過」、「報告符合性需確認」、「證據抽查未通過」或「數字證據需人工核對」。
3. 重用既有 `.history-action-badge` 樣式，不新增 CSS。

優化說明

1. 解決證據/符合性警示在 preview 中斷的問題。
2. 犧牲是 preview 頂部 chip 可能多一個；但只在有警示時出現。
3. 剩餘風險是完整 preview 尚未顯示 failed claim 明細；目前先提供採用前警示。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 批判思考 / #演繹

狀態：完成

本次使用：避免使用者從「報告可預覽」演繹出「報告已可直接採用」。

核心判斷

1. Preview 是閱讀入口，不是品質核准。
2. 如果 conformance blocked 或 evidence rejected，preview 仍可用來檢查問題，但不能讓 UI 語氣像一般報告。
3. 將品質徽章放在 preview 頂部，可以把「可讀」與「可採用」拆開。

落地修改

1. `reportQualityBadge()` 優先顯示 report conformance，再顯示 evidence exit gate，對齊 history/operator summary 的行動優先序。
2. Preview 內 `elements.mode.innerHTML` 納入品質徽章。

驗證方式

- 前端契約測試檢查 `report_preview_panel.js` 包含 `reportQualityBadge`、`證據抽查未通過`、`報告符合性未通過`。

### 第 1 輪 / 批判思考 / #歸納

狀態：完成

本次使用：從多個工作台視圖歸納品質訊號的一致呈現規則。

核心判斷

1. History、operator summary 與 preview 都是操作者判斷報告能不能採用的入口。
2. 若只有 history 顯示品質警示，使用者可能在 preview 內忽略同一份報告的風險。
3. 品質警示應跨視圖一致，但不需要每個視圖都顯示完整明細。

落地修改

1. Preview 與 history 共享同樣的警示文字與 tone 類型。
2. `tests/test_static_history_filters.py` 把 preview 納入 evidence/conformance 靜態契約。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪批判思考第六批

### 第 1 輪 / 批判思考 / #謬誤

狀態：完成

本次使用：檢查工作台摘要是否可能讓使用者犯「單一可信度」謬誤，把資料新鮮度、來源健康、報告符合性與證據抽查混成同一種判斷。

核心判斷

1. Operator summary 原本用 `fresh / sampled` 呈現資料狀態，語氣偏內部監控，不像操作者決策語言。
2. `fresh` 容易被誤讀成整份報告都可信；但實際上它只代表資料信任狀態的一部分。
3. 使用中文脈絡能降低把來源健康與結論可信度混淆的風險。

落地修改

1. `backend/static/operator_summary_panel.js` 將 `fresh ${fresh} / sampled ${reports.length}` 改為 `資料新鮮 ${fresh} / 抽樣 ${reports.length}`。
2. `tests/test_static_history_filters.py` 新增不允許舊 `fresh / sampled` 文案的契約。

優化說明

1. 解決 operator summary 中內部英文監控語氣外露的問題。
2. 不改動計算邏輯，只改顯示語意。
3. 剩餘風險是其他 dashboard 仍可能使用英文/內部欄位名稱，需後續逐步掃描。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 批判思考 / #來源品質

狀態：完成

本次使用：讓來源提醒與需要重跑/刷新資料的狀態分開。

核心判斷

1. `provider_sla_critical` 型 partial 可能只是來源健康提醒，不一定代表該報告需要刷新或重跑。
2. Operator summary 已有「無需刷新/重跑」語意，但後面接 `fresh / sampled` 會削弱脈絡。
3. 來源品質提示應同時告訴使用者「這是來源層提醒」與「目前不需採取刷新/重跑動作」。

落地修改

1. 來源提醒 detail 改為 `無需刷新/重跑 · 資料新鮮 ${fresh} / 抽樣 ${reports.length}`。
2. 前端契約測試鎖定中文資料新鮮/抽樣文案。

驗證方式

- `tests/test_static_history_filters.py` 檢查 operator summary 包含 `資料新鮮 ${fresh} / 抽樣 ${reports.length}` 並排除舊字串。

### 第 1 輪 / 批判思考 / #情境脈絡

狀態：完成

本次使用：補足 operator summary 的樣本範圍脈絡，避免使用者以為摘要是全庫完整統計。

核心判斷

1. Operator summary 只讀近期報告樣本，不是所有歷史報告。
2. 用「抽樣」比 `sampled` 更貼近操作者語境，也提醒這是摘要視窗。
3. 這與 performance panel 的樣本信心一致：數字要帶著樣本脈絡出現。

落地修改

1. 將 operator summary 的 detail 統一為中文「資料新鮮 / 抽樣」格式。
2. HCS 狀態測試擴充到 `#謬誤`、`#來源品質`、`#情境脈絡`。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪批判思考第七批

### 第 1 輪 / 批判思考 / #批判

狀態：完成

本次使用：質疑 UI 中「健康正常」是否暗示系統掌握外部 provider 真實健康，而不是只有本機觀測。

核心判斷

1. API quota panel 與 operator summary 原本用「LLM/API 健康」或「LLM 健康正常」描述無錯誤狀態。
2. 這容易讓使用者以為供應商本身狀態已被完整驗證；實際上只是本機觀測到的設定與錯誤次數。
3. 更準確的框架是「本機觀測」，有錯誤時才用健康警示。

落地修改

1. `backend/static/api_quota_panel.js` 將無錯誤 summary 改為 `LLM/API 本機觀測：...`。
2. `backend/static/operator_summary_panel.js` 將 `LLM 健康正常` 改為 `LLM 本機觀測正常`。

優化說明

1. 降低把本機統計誤認為供應商 SLA 事實的風險。
2. 保留 `LLM/API 健康警示`，因為錯誤狀態對操作者仍需快速辨識。
3. 剩餘風險是頁籤標題仍使用「LLM 健康」，這是導覽名；目前先修 summary 與 operator card 的判斷語氣。

驗證方式

- `tests/test_static_history_filters.py::test_operator_signals_avoid_misleading_health_and_tracking_copy`

### 第 1 輪 / 批判思考 / #估算

狀態：完成

本次使用：檢查 API quota 數字是否被當成精準供應商狀態，而不是本機觀測估算。

核心判斷

1. API quota 只統計本機觀測到的 requests、errors、reset 與 key count。
2. 無錯誤不代表 provider 全域健康；只代表目前本機觀測沒有錯誤訊號。
3. 「本機觀測」比「健康」更能承載估算/觀測的限制。

落地修改

1. 前端靜態契約要求 `api_quota_panel.js` 包含 `LLM/API 本機觀測：`。
2. 測試同時排除 `LLM/API 健康：` 的無錯誤 summary 字串。

驗證方式

- `tests/test_static_history_filters.py::test_operator_signals_avoid_misleading_health_and_tracking_copy`

### 第 1 輪 / 批判思考 / #詮釋框架

狀態：完成

本次使用：調整使用者詮釋 API quota 面板的框架，從「健康證明」改成「本機觀測視窗」。

核心判斷

1. 使用者在維運頁看到的是本機工作台視角，不是 provider 控制台。
2. `LLM 本機觀測正常` 保留可掃讀性，同時提醒這不是全面 SLA。
3. 這和 provider SLA 面板的「觀測窗口 / 檢查樣本」語氣一致。

落地修改

1. `operator_summary_panel.js` 的 LLM 卡片使用「本機觀測正常」框架。
2. `tests/test_static_history_filters.py` 把這個框架納入 operator signals 測試。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_operator_signals_avoid_misleading_health_and_tracking_copy`

## 第 1 輪批判思考第八批

### 第 1 輪 / 批判思考 / #合理性

狀態：完成

本次使用：檢查批判思考第 1 輪是否能合理收束，而不是把多個局部修補誤認為完整 HCS Plus。

核心判斷

1. 批判思考共有 26 個單項習慣；目前已逐項留下落地修改與驗證欄位。
2. 合理的收尾不能宣稱完整 HCS Plus 完成，因為創意、溝通、互動思考仍未完成三輪單項巡迴。
3. 下一步應明確切到創意思考第一批，避免流程在批判思考尾端停住。

落地修改

1. 本文件新增「第 1 輪批判思考收尾」，標示 `已完成：26/26`。
2. 主狀態表將 `#合理性/#可驗證性` 標成完成，並新增創意思考下一批入口。
3. `tests/test_hcs_plus_state.py` 將 `#合理性` 納入完成習慣檢查。

優化說明

1. 解決流程紀錄沒有收尾檢查點的問題。
2. 犧牲的是本批沒有新增前端 runtime 行為；換來的是下一階段可接續的流程邊界。
3. 剩餘風險是完整 HCS Plus 尚很長，後續仍需每批實際改檔與驗證。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少 `#合理性` section 與收尾摘要會失敗。
- GREEN：`tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`

### 第 1 輪 / 批判思考 / #可驗證性

狀態：完成

本次使用：把「批判思考第 1 輪完成」轉成可重跑檢查，而不是只靠人工閱讀。

核心判斷

1. 已完成習慣需同時具備 `核心判斷`、`落地修改`、`驗證方式` 與 `狀態：完成`。
2. 收尾摘要需明確寫出 26/26 與下一個 HCS 入口，否則後續接續容易跳項。
3. 主狀態表與 strict log 必須一致，避免一份顯示完成、另一份仍顯示下一批。

落地修改

1. `tests/test_hcs_plus_state.py` 新增批判思考收尾檢查，要求 `已完成：26/26` 與 `下一步：第 1 輪 / 創意思考 / #學習科學`。
2. 本文件新增 `#可驗證性` 獨立紀錄與收尾摘要。
3. 主狀態表新增創意思考第一批 `#學習科學/#限制條件/#類比` 的下一批列。

優化說明

1. 讓流程完成條件能被 CI 或本機測試重跑。
2. 保留下一批只處理 3 個相近習慣的節奏，避免創意思考一開始就擴大範圍。
3. 剩餘風險是文件契約無法替代使用者實際操作驗證；後續若改 UI 仍需跑前端相關檢查。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_critical_thinking_round_has_closing_checkpoint`

## 第 1 輪批判思考收尾

已完成：26/26

已落地修改：

- 建立嚴格單項輪巡附件與 HCS 狀態測試。
- 將 pipeline id 範例收斂到 canonical `v1` 到 `v4`。
- Active jobs、performance panel、report preview、operator summary、API quota panel 已補強可讀性與證據/樣本/觀測脈絡。
- 主狀態表與 strict log 已對齊到批判思考第 1 輪完成。

驗證基準：

- `tests/test_hcs_plus_state.py`
- `tests/test_docs_contract.py`
- `tests/test_static_history_filters.py`

剩餘風險：

- 尚未完成創意思考、溝通思考、互動思考的嚴格單項輪巡。
- 尚未跑完整專案測試矩陣；目前以貼近修改面的測試作為批次驗證。

下一步：第 1 輪 / 創意思考 / #學習科學

## 第 1 輪創意思考第一批

### 第 1 輪 / 創意思考 / #學習科學

狀態：完成

本次使用：把模式選擇從「讀完整規格表」改成「先回答我要做哪種決策」的學習提示。

核心判斷

1. `docs/pipeline-mode-contract.md` 已有完整對照表，但新人需要先形成可記憶的 mode 選擇入口。
2. 以決策問題作為 retrieval cue，能讓使用者先選出候選 mode，再回到詳細表格驗證。
3. 這比新增更長說明更符合學習科學：短提示、可回想、可反覆查驗。

落地修改

1. `docs/pipeline-mode-contract.md` 新增「模式選擇速記」。
2. 每個 mode 以一句決策 cue 呈現：長線納入、交易動作、過熱/避險、事件窗口、三視角交叉檢查。
3. `tests/test_docs_contract.py` 新增契約測試，防止速記層被移除。

優化說明

1. 降低新整合者和操作者第一次閱讀模式契約的認知成本。
2. 不改前端 UI，避免在工作台增加額外文字密度。
3. 剩餘風險是速記只存在文件；若後續使用者仍常選錯 mode，再評估是否進 UI。

驗證方式

- RED：`tests/test_docs_contract.py::test_pipeline_mode_contract_has_decision_cues_for_mode_selection` 先確認缺少「模式選擇速記」會失敗。
- GREEN：`tests/test_docs_contract.py::test_pipeline_mode_contract_has_decision_cues_for_mode_selection`

### 第 1 輪 / 創意思考 / #限制條件

狀態：完成

本次使用：在不增加 UI 密度、不改 backend metadata、不影響 runtime 的限制下，選擇最小可逆落點。

核心判斷

1. 目前前端已經有 mode intent 和 label，繼續塞更多文字可能傷害工作台掃讀。
2. 後端 pipeline metadata 仍有雙來源問題，但創意思考第一批不適合大改資料來源。
3. 文件契約是最小改動面：能改善學習入口，也能用現有 docs contract 測試驗證。

落地修改

1. 速記只加在 `docs/pipeline-mode-contract.md`，不改 `backend/static/ui_helpers.js`。
2. 測試只檢查文件契約必要字串，不引入新的 runtime fixture。

優化說明

1. 在限制下保留高可逆性，避免把學習提示直接塞進產品介面。
2. 犧牲的是短期產品畫面不變；收益是新文件與新整合者能更快選對 mode。
3. 後續若要進一步落地，可把這些 cue 轉成 backend/front-end shared metadata。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_decision_cues_for_mode_selection`

### 第 1 輪 / 創意思考 / #類比

狀態：完成

本次使用：用「分診台」類比說明模式選擇，讓使用者先分流決策情境，再查細節。

核心判斷

1. 四個 pipeline mode 容易被看成技術版本號；類比能把它們重新框成不同決策入口。
2. 「分診台」比「菜單」更準確，因為它強調先判斷問題性質，再選流程。
3. 類比必須落在文件契約，不應取代下方精確欄位與驗收標準。

落地修改

1. 「模式選擇速記」段落新增：`這個速記像分診台`。
2. 文件說明先用決策分流，再回到表格檢查報告模板、摘要標題與證據要求。

優化說明

1. 降低 `v1/v2/v3/v4` 被誤解成版本新舊或優先級的風險。
2. 保留 canonical id 和 alias normalization 的技術邊界。
3. 剩餘風險是類比可能被過度延伸；因此下方仍保留正式模式對照表。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_decision_cues_for_mode_selection`

## 第 1 輪創意思考第二批

### 第 1 輪 / 創意思考 / #演算法

狀態：完成

本次使用：把 mode 選擇從口訣推進成可照順序執行的決策樹。

核心判斷

1. 速記能幫助記憶，但仍需要一個穩定順序處理 `both`、短線事件、過熱風險、交易行動與長線研究。
2. 決策樹應先處理多報告與短效期限，因為選錯會造成最高重跑成本。
3. 文件層的演算法比 runtime 自動選 mode 更安全，因為目前仍需要操作者判斷問題脈絡。

落地修改

1. `docs/pipeline-mode-contract.md` 新增「模式選擇決策樹」。
2. `tests/test_docs_contract.py` 新增 `test_pipeline_mode_contract_has_selection_decision_tree`。

優化說明

1. 將 mode selection 從靜態表格轉成可執行步驟。
2. 不新增自動化選 mode 行為，避免在資訊不足時替使用者做投資流程判斷。
3. 剩餘風險是決策樹仍是文件規範；後續可視使用情況轉成前端輔助。

驗證方式

- RED：`tests/test_docs_contract.py::test_pipeline_mode_contract_has_selection_decision_tree` 先確認缺少決策樹會失敗。
- GREEN：`tests/test_docs_contract.py::test_pipeline_mode_contract_has_selection_decision_tree`

### 第 1 輪 / 創意思考 / #設計思考

狀態：完成

本次使用：從使用者任務出發排列 mode 選擇，而不是從系統代碼或內部 agent 數出發。

核心判斷

1. 使用者真正的問題是「我要做哪種決策」，不是「我要跑哪個版本」。
2. 決策樹把 `both`、`v4`、`v3`、`v2`、`v1` 排成情境順序，對應不同任務壓力。
3. 這能讓文件契約服務操作者與整合者，而不只是服務開發者。

落地修改

1. 決策樹每一步都以「如果核心問題是...」開頭。
2. 每一步附上該 mode 的檢查重點，讓使用者知道選完後要看什麼證據。

優化說明

1. 把文件從 reference 擴展成 how-to 入口，但仍保留契約表格的精確性。
2. 犧牲的是文件略長；收益是選 mode 的第一步更明確。
3. 後續若發現文件過長，可把速記與決策樹拆成獨立 how-to。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_selection_decision_tree`

### 第 1 輪 / 創意思考 / #捷思法

狀態：完成

本次使用：加入一個可接受的預設捷思，處理使用者仍不確定該選哪個 mode 的情境。

核心判斷

1. 不確定時直接選交易或短線 mode 容易讓報告偏向行動建議，但缺少基本面基準。
2. 先用 `v1` 建立基本面基準是較保守的暫定捷思，之後再視結論補跑 `v2`、`v3` 或 `v4`。
3. 捷思必須明確標成 fallback，而不是取代正式判斷。

落地修改

1. 決策樹新增：`若仍不確定，先選 v1 建立基本面基準`。
2. 測試鎖住 fallback 文字，避免後續文件回到模糊狀態。

優化說明

1. 降低新使用者卡在 mode selection 的風險。
2. 保守預設犧牲的是速度；收益是先建立較完整資料脈絡。
3. 後續若有使用者偏好，也可把 fallback 寫成可設定策略。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_selection_decision_tree`

## 第 1 輪創意思考第三批

### 第 1 輪 / 創意思考 / #最佳化

狀態：完成

本次使用：降低使用者在報告比較摘要中解讀 `v1/v2/v3/v4` 的成本。

核心判斷

1. Report compare summary 原本用 raw `pipeline_id` 顯示兩份報告，使用者需要自己把 `v1` 轉成「學術深度派」。
2. 既有共用 helper `pipelineModeLabel` 已解決其他視圖的同類問題，compare panel 應重用它。
3. 這是小範圍最佳化：不改 compare API、不改資料模型，只改選取摘要的顯示語意。

落地修改

1. `backend/static/report_compare_panel.js` 新增 `pipelineModeLabel` fallback。
2. 比較選取摘要從 `${report.pipeline_id || 'v1'}` 改為共用模式語意 label。
3. `backend/static/history_workspace.js` 將 `ui.pipelineModeLabel` 傳入 report compare panel。

優化說明

1. 減少使用者比較報告時的 mode 解碼負擔。
2. 保持顯示層改動，不影響 compare diff 計算。
3. 剩餘風險是 compare result grid 仍以 filename 呈現左右報告；後續可再評估是否加入 mode badge。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認 compare panel 缺 `pipelineModeLabel` 會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 創意思考 / #假說發展

狀態：完成

本次使用：將「比較報告前，使用者需要先辨識兩份報告的決策模式」轉成可驗證假說。

核心判斷

1. 若 compare summary 顯示可讀 mode label，使用者更容易判斷兩份報告是否同模式、跨模式或時間序列比較。
2. 該假說可以用靜態契約先驗證接線：compare panel 必須使用 `pipelineModeLabel`，且 history workspace 必須傳入 helper。
3. 若後續要驗證真實效果，可在 UI QA 中檢查 compare summary 的掃讀速度與誤解率。

落地修改

1. `tests/test_static_history_filters.py` 新增 compare panel mode label 接線契約。
2. 測試排除 raw `pipeline_id` summary template，防止回退。

優化說明

1. 先用低成本測試固定假說的最小可觀測行為。
2. 不引入 analytics 或事件追蹤，避免擴大改動面。
3. 剩餘風險是靜態測試不能保證實際 DOM 呈現；完整 UI 驗證可後續用瀏覽器測試補上。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 創意思考 / #資料視覺化

狀態：完成

本次使用：讓比較摘要顯示對使用者有意義的 mode 視覺語意，而不是內部代碼。

核心判斷

1. `ticker · v1 · date` 的視覺資訊密度低，且 `v1` 容易被誤讀為版本或優先級。
2. `ticker · 模式 A · 學術深度派 · date` 更接近使用者做比較時需要的視覺分組。
3. 使用既有 label helper 能維持與 history、watchlist、active jobs 的一致視覺語言。

落地修改

1. `report_compare_panel.js` 的 summary 顯示改用 `pipelineModeLabel(report.pipeline_id || 'v1')`。
2. 靜態測試要求 compare panel 包含 `window.StockAgentUi?.pipelineModeLabel` fallback。

優化說明

1. 改善比較視圖的資料可視化語意，而不新增新元件或版面。
2. 犧牲的是 summary 字串略長；但比較區域只有最多兩份報告，仍可掃讀。
3. 剩餘風險是 mobile 寬度下長 label 可能換行；現有 summary 已是文字段落，風險可接受。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪創意思考第四批

### 第 1 輪 / 創意思考 / #建模

狀態：完成

本次使用：讓 report compare result 明確顯示左右報告使用的決策模型。

核心判斷

1. 比較報告時，`v1` 與 `v2` 代表不同決策模型；如果只看 filename，使用者不容易先判斷比較基準。
2. 既有 compare payload 已有 `left.pipeline_id` 與 `right.pipeline_id`，前端可直接用共用 mode label 建模。
3. 顯示「比較基準」能讓同模式時間比較與跨模式視角比較先被區分。

落地修改

1. `backend/static/report_compare_panel.js` 在 result grid 新增「比較基準」。
2. 左右基準使用 `pipelineModeLabel(left.pipeline_id || 'v1')` 與 `pipelineModeLabel(right.pipeline_id || 'v1')`。

優化說明

1. 補足比較結果的模型脈絡，避免使用者只看到數字 delta。
2. 不改後端 compare API，因為既有 payload 已足夠。
3. 剩餘風險是跨模式比較的警示仍使用 raw pipeline id；後續可再把 compatibility warning 語意化。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認缺少「比較基準」會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 創意思考 / #抽樣

狀態：完成

本次使用：讓比較結果標示兩份報告的樣本日期與時間順序。

核心判斷

1. 兩份報告比較本質上是小樣本比較，至少要看左右報告日期與時間順序。
2. compare compatibility 已有 `date_order`，但目前只出現在可比較 chip；result grid 缺少可掃讀樣本欄。
3. 「比較樣本」能提醒使用者 delta 來自哪兩個日期，而不是整體模型表現。

落地修改

1. `report_compare_panel.js` 新增「比較樣本」欄位。
2. 欄位顯示 `left.date → right.date · dateOrderLabel(compatibility.date_order)`。

優化說明

1. 強化樣本脈絡，降低把兩份報告差異過度外推的風險。
2. 不新增資料欄位，只重用現有 `date` 與 compatibility。
3. 若日期缺失會顯示 `N/A`，後續可再補後端 metadata 完整性檢查。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 創意思考 / #個案研究

狀態：完成

本次使用：把兩份報告比較框成一個可審查個案，而不是泛化統計。

核心判斷

1. Report compare 是針對兩份具體報告的個案比較，不應被看成整體策略績效。
2. 「比較基準」與「比較樣本」一起讓個案邊界更清楚：模式、日期、左右順序都被明示。
3. 這與 performance panel 的樣本信心提示互補，前者處理個案，後者處理聚合樣本。

落地修改

1. compare result grid 新增兩個脈絡欄位，讓個案比較先顯示基準與樣本。
2. HCS 狀態測試納入 `#建模`、`#抽樣`、`#個案研究` 的獨立紀錄。

優化說明

1. 降低使用者把單一比較結果過度推廣的風險。
2. 保持 UI 改動小而可掃讀；沒有新增 nested card 或複雜表格。
3. 剩餘風險是跨模式比較需要更友善的 warning 文案，留給後續 `#比較組`。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪創意思考第五批

### 第 1 輪 / 創意思考 / #比較組

狀態：完成

本次使用：讓跨模式比較的 warning 清楚指出左右報告屬於不同決策模式。

核心判斷

1. 後端 compare compatibility 已能判斷 `different_pipeline`，但 message 以 raw pipeline id 呈現。
2. 跨模式比較不是不能比，而是比較組不同；使用者需要看到可讀模式名稱再判斷比較目的。
3. 前端已有 mode label helper，適合在 warning 顯示層把比較組語意補上。

落地修改

1. `backend/static/report_compare_panel.js` 新增 `compareWarningMessage`。
2. `different_pipeline` warning 改顯示 `兩份報告模式不同：模式 A ... vs 模式 B ...`。

優化說明

1. 降低跨模式比較時把 `v1/v2` 誤讀成版本號或優先級的風險。
2. 保留後端 compatibility code，不改 API 契約。
3. 剩餘風險是 ticker 不同的 warning 仍使用後端訊息；目前 ticker 本身已可讀。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認缺少 `compareWarningMessage` 會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 創意思考 / #介入研究

狀態：完成

本次使用：用最小 UI 介入改善跨模式 warning，而不改後端資料產生邏輯。

核心判斷

1. 這個問題只影響顯示語意；直接改後端 warning 會把前端 mode label 耦合進服務層。
2. 前端介入能就地使用 `pipelineModeLabel`，成本低且與其他前端視圖一致。
3. 介入範圍應限於 `different_pipeline`，避免重寫所有 warning 造成行為漂移。

落地修改

1. warning 渲染從 `item.message || item` 改成 `compareWarningMessage(item, left, right)`。
2. 只有 `item.code === 'different_pipeline'` 被轉譯，其餘 warning 照舊。

優化說明

1. 將介入範圍壓到最小，降低 regressions。
2. 不影響 warning level 與 styling。
3. 後續若有更多 code 需要轉譯，可擴充同一 helper。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 創意思考 / #訪談調查

狀態：完成

本次使用：把使用者可能問出的困惑「v1 vs v2 是什麼意思？」轉成前端文案契約。

核心判斷

1. 尚未做真實使用者訪談，但既有批判思考已指出 raw id 在多個視圖中造成理解成本。
2. 對此類小文案問題，最低成本做法是把推定使用者困惑轉成可檢查的顯示契約。
3. 這不取代真實訪談；它只是先移除明顯的語意摩擦。

落地修改

1. `tests/test_static_history_filters.py` 要求 compare panel 包含 `兩份報告模式不同`。
2. HCS 紀錄標明此為推定使用者回饋，不是已完成真實訪談。

優化說明

1. 讓可能的使用者困惑有可重跑的防回歸測試。
2. 犧牲的是沒有外部訪談資料；收益是立即修掉低風險語意摩擦。
3. 後續若做 QA 或訪談，可再驗證這段 warning 是否足夠。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪創意思考第六批

### 第 1 輪 / 創意思考 / #觀察研究

狀態：完成

本次使用：觀察前端目前 raw mode 與共用 mode label 的使用位置，區分真正顯示問題與資料傳遞 fallback。

核心判斷

1. 掃描 `backend/static` 後，主要使用者可見 mode 顯示已集中在 `pipelineModeLabel` 或 `renderPipelineModeBadge`。
2. 剩餘 `pipeline_id || 'v1'` 多數是 openReport、action payload、data attribute 或 rerun fallback，不一定是顯示問題。
3. Report compare 是本輪最有代表性的可見缺口：summary、result grid、warning 都會被操作者直接讀到。

落地修改

1. 將觀察結果寫入本 strict log，作為創意思考收尾依據。
2. `tests/test_static_history_filters.py` 已鎖住 compare panel 使用 `pipelineModeLabel`、`比較基準`、`比較樣本`、`compareWarningMessage`。

優化說明

1. 避免為了消滅所有 `pipeline_id` 字串而誤改資料傳遞路徑。
2. 聚焦真正會影響操作者理解的顯示面。
3. 剩餘風險是仍需瀏覽器視覺 QA 驗證 mobile wrapping。

驗證方式

- `rg -n "pipeline_id \\|\\| 'v1'|report\\.pipeline_id|left\\.pipeline_id|right\\.pipeline_id|pipelineModeLabel" backend/static -S`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 創意思考 / #研究複製

狀態：完成

本次使用：把已在 history、watchlist、active jobs 生效的共用 mode label 模式複製到 report compare。

核心判斷

1. 既有模式語意改善已在 history/watchlist/active jobs 使用共用 helper；report compare 應複製同一模式，而不是發明新 label。
2. 可複製模式包含三件事：options 傳入 helper、fallback 到 `window.StockAgentUi`、測試鎖住接線。
3. 這讓後續溝通思考可以專注於受眾與語意，而不是繼續修 raw id 顯示。

落地修改

1. `history_workspace.js` 傳入 `pipelineModeLabel: ui.pipelineModeLabel`。
2. `report_compare_panel.js` 同時在 selection summary、result grid 與 warning 使用同一 helper。
3. HCS 狀態測試新增創意思考收尾 checkpoint。

優化說明

1. 複製已驗證 pattern，降低新增不一致抽象的風險。
2. 保留 panel 內 fallback，讓單獨載入時仍可運作。
3. 剩餘風險是其他未掃到的使用者可見字串可能仍有內部語氣，留給溝通思考批次處理。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_creative_thinking_round_has_closing_checkpoint`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪創意思考收尾

已完成：17/17

已落地修改：

- `docs/pipeline-mode-contract.md` 新增模式選擇速記與決策樹。
- `backend/static/report_compare_panel.js` 使用共用 mode label 顯示選取摘要、比較基準、比較樣本與跨模式 warning。
- `backend/static/history_workspace.js` 將 `ui.pipelineModeLabel` 傳入 report compare panel。
- `tests/test_docs_contract.py`、`tests/test_static_history_filters.py`、`tests/test_hcs_plus_state.py` 鎖住文件與前端語意。

驗證基準：

- `tests/test_hcs_plus_state.py`
- `tests/test_docs_contract.py`
- `tests/test_static_history_filters.py`

剩餘風險：

- 尚未完成溝通思考與互動思考的第 1 輪嚴格單項巡迴。
- Report compare 的 mobile wrapping 尚未用瀏覽器截圖驗證。

下一步：第 1 輪 / 溝通思考 / #受眾

## 第 1 輪溝通思考第一批

### 第 1 輪 / 溝通思考 / #受眾

狀態：完成

本次使用：把 report compare warning 從工程讀者語氣調整成操作者可讀語氣。

核心判斷

1. `A vs B` 對工程讀者很短，但對中文操作者而言不如「A 與 B」自然。
2. 跨模式比較 warning 的受眾是正在判斷報告差異的操作者，不是查 debug log 的開發者。
3. 文案應說明比較性質，而不是只列出代碼或縮寫。

落地修改

1. `backend/static/report_compare_panel.js` 將 warning 中的 `vs` 改成中文「與」。
2. `tests/test_static_history_filters.py` 要求 report compare JS 不含 ` vs `。

優化說明

1. 降低非工程使用者閱讀 warning 的摩擦。
2. 不改 warning 觸發條件，只改顯示語氣。
3. 剩餘風險是其他面板仍可能有工程縮寫，後續溝通思考繼續掃描。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認 `跨視角比較` 缺失與 `vs` 存在會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 溝通思考 / #組成

狀態：完成

本次使用：讓 warning 組成包含左右模式與比較性質，而不是只有「不同」。

核心判斷

1. 好的 warning 需要回答三件事：哪兩份模式不同、這是否仍可比較、使用者應如何理解。
2. 目前最小足夠組成是「兩份報告模式不同：A 與 B；這是跨視角比較。」
3. 不必在 warning 裡加入長指令，避免讓 chip 變得太長。

落地修改

1. `compareWarningMessage` 將左右 mode label 與「跨視角比較」放在同一句。
2. 測試鎖住 `兩份報告模式不同` 與 `跨視角比較` 兩個語意元件。

優化說明

1. 讓 warning 同時具備差異資訊與解讀框架。
2. 犧牲的是比原本短句稍長；但 warning 只在跨模式比較時出現。
3. 若 mobile chip 過長，後續可把 compatibility chips 改成多行內容。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 溝通思考 / #語意含義

狀態：完成

本次使用：修正文案中可能造成對立感或工程感的符號語意。

核心判斷

1. `vs` 暗示對抗或技術比較，不如「與」中性。
2. 「不同」若沒有補充，可能被看成不可比較；「跨視角比較」明確說明它是另一種比較目的。
3. 這能降低使用者看到 warning 就停止操作的機率。

落地修改

1. Warning 字串改為 `兩份報告模式不同：... 與 ...；這是跨視角比較。`
2. 靜態測試排除 ` vs `，並要求 `跨視角比較` 存在。

優化說明

1. 讓 warning 從阻斷語意改成解釋語意。
2. 不降低警示強度；只把差異的含義說清楚。
3. 後續可檢查其他 `warning` 是否也有「看起來像錯誤、其實是脈絡」的情況。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪溝通思考第二批

### 第 1 輪 / 溝通思考 / #組織結構

狀態：完成

本次使用：調整 report compare result 的資訊順序，先回答比較性質，再列出檔名與數字。

核心判斷

1. 使用者進入比較結果時，第一個問題是「這兩份報告是不是同一種比較」。
2. 原本 result grid 先列左右檔名，結論需要從 chip 與其他欄位拼湊。
3. 新增「比較結論」作為第一個 grid cell，可以讓資訊結構更符合決策閱讀順序。

落地修改

1. `backend/static/report_compare_panel.js` 新增 `compareSummaryLabel`。
2. Result grid 第一列新增 `比較結論`，內容依 compatibility 顯示同股票同模式、股票不同、跨視角比較或需留意。

優化說明

1. 讓比較結果先交代閱讀框架，再進入左右檔案與 delta。
2. 不改後端 payload，只重排前端顯示。
3. 剩餘風險是 grid cell 變多，仍需後續視覺 QA 檢查 mobile wrapping。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認缺少 `比較結論` 與 `compareSummaryLabel` 會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`
- 行數限制：`tests/test_static_history_filters.py::test_frontend_static_modules_are_sized`

### 第 1 輪 / 溝通思考 / #專業性

狀態：完成

本次使用：讓比較性質用專業但不誇大的語氣呈現。

核心判斷

1. 「同股票同模式」能說明這是較直接的時間/版本比較。
2. 「跨視角比較」能說明不同 pipeline 的比較目的，不把它說成錯誤。
3. 「需留意」保留不確定狀態，避免 compatibility 缺資料時過度肯定。

落地修改

1. `compareSummaryLabel` 使用 `同股票同模式`、`股票不同`、`跨視角比較`、`需留意` 四種語氣。
2. 靜態契約要求 `同股票同模式` 存在於 compare panel。

優化說明

1. 補強專業語氣：既不過度阻斷，也不把風險淡化。
2. 不新增投資建議，只描述比較條件。
3. 後續可把同樣語氣套用到 report preview 的 rerun/refresh 判斷。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 溝通思考 / #論點

狀態：完成

本次使用：把 compare result 的論點從隱含狀態變成明確第一句。

核心判斷

1. Result grid 的核心論點不是「左右檔案各是什麼」，而是「這次比較應如何被理解」。
2. 將「比較結論」放第一列，能避免使用者先讀數字再回頭查是否可比。
3. 這與前面批判思考的可驗證性一致：結論必須先聲明條件。

落地修改

1. Grid rows array 第一個元素改為 `['比較結論', compareSummaryLabel(compatibility)]`。
2. 測試鎖定 `compareSummaryLabel` 與 `比較結論`。

優化說明

1. 讓論點先行，數字與檔名作為支持資訊。
2. 犧牲一格版面；換來更清楚的比較閱讀入口。
3. 剩餘風險是 summary label 邏輯目前在前端，若後端也需要同語意需再抽共用。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪溝通思考第三批

### 第 1 輪 / 溝通思考 / #溝通設計

狀態：完成

本次使用：收斂 compare panel 的溝通設計，避免為了表達完整而加入過多視覺與文案。

核心判斷

1. Compare panel 已具備 selection summary、compatibility chip、比較結論、比較基準、比較樣本與核心 delta。
2. 再加入更多說明會降低掃讀效率，尤其是在 preview 側欄內。
3. 本輪更合理的設計是「收尾並測試固定」，把後續大型視覺改善留給專門 QA 或設計批次。

落地修改

1. `tests/test_hcs_plus_state.py` 新增溝通思考收尾 checkpoint。
2. 本文件新增溝通思考收尾，明確記錄暫不擴張 compare panel 的設計決策。

優化說明

1. 避免 compare panel 變成第二個完整報告視圖。
2. 犧牲的是沒有新增圖表或多媒體；收益是維持側欄工具的掃讀性。
3. 剩餘風險是 mobile wrapping 尚未實測，留給後續視覺 QA。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少溝通收尾會失敗。
- GREEN：`tests/test_hcs_plus_state.py::test_hcs_plus_communication_thinking_round_has_closing_checkpoint`

### 第 1 輪 / 溝通思考 / #表達

狀態：完成

本次使用：把本輪 compare 文案原則寫成可接續的收尾摘要。

核心判斷

1. 本輪表達原則是：少用代碼、先說比較性質、再呈現檔名與數字。
2. 「同股票同模式」「跨視角比較」「比較基準」「比較樣本」已形成一致用語。
3. 收尾摘要能讓後續溝通批次沿用這套表達，而不是重新命名。

落地修改

1. 本文件「第 1 輪溝通思考收尾」新增已落地修改與文案原則。
2. `tests/test_hcs_plus_state.py` 要求 `已完成：10/10` 與下一步互動思考入口。

優化說明

1. 固定可重用表達，降低後續回到 raw id 或工程語氣的風險。
2. 不新增產品字串，只把已完成的表達原則寫成狀態契約。
3. 剩餘風險是其他頁面仍可能有未掃到的工程語氣。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_communication_thinking_round_has_closing_checkpoint`

### 第 1 輪 / 溝通思考 / #媒介

狀態：完成

本次使用：確認 report compare 目前應維持文字 grid 與 chip，而不是切換成圖表或複雜媒介。

核心判斷

1. Report compare 的資訊是左右報告脈絡與少量 delta，文字 grid 比圖表更直接。
2. Compatibility warning 適合 chip，因為它是短狀態訊息，不是完整說明段落。
3. 圖表或多媒體會增加實作與 QA 成本，且不一定提升當前決策效率。

落地修改

1. 在溝通收尾記錄目前媒介選擇：文字 grid/chip。
2. 測試固定 compare panel 不需要新增額外多媒體 artifact 才能完成本輪。

優化說明

1. 把媒介選擇說清楚，避免後續誤以為未加入圖表就是缺漏。
2. 保持現有 CSS 與行數限制穩定。
3. 若未來比較維度增加，再另開視覺設計批次。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_communication_thinking_round_has_closing_checkpoint`
- `tests/test_static_history_filters.py::test_frontend_static_modules_are_sized`

### 第 1 輪 / 溝通思考 / #多媒體

狀態：完成

本次使用：判斷本輪是否需要加入圖表、截圖或多媒體比較；結論是暫不加入。

核心判斷

1. 目前 compare panel 是嵌在 report preview 的輔助工具，不是獨立分析儀表板。
2. 多媒體化會需要額外 responsive QA，且可能與「側欄掃讀」目標衝突。
3. 目前最有價值的多媒體工作是後續瀏覽器截圖驗證，而不是新增使用者可見媒體。

落地修改

1. 溝通收尾明確標示「暫不引入圖表/截圖式比較」。
2. 下一步轉入互動思考，檢查倫理與使用者操作風險，而不是繼續擴張溝通媒介。

優化說明

1. 避免為了多媒體而多媒體，維持工具型 UI 的節制。
2. 承認剩餘風險：仍需實際瀏覽器 QA 驗證視覺 wrapping。
3. 將多媒體相關工作保留為驗證/設計 QA，而不是本輪功能需求。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_hcs_plus_state.py::test_hcs_plus_communication_thinking_round_has_closing_checkpoint`

## 第 1 輪溝通思考收尾

已完成：10/10

已落地修改：

- `backend/static/report_compare_panel.js` 的比較結果先顯示「比較結論」，再顯示檔名、比較基準、比較樣本與 delta。
- `backend/static/report_compare_panel.js` 的跨模式 warning 使用完整中文語意，不再使用 `vs`。
- `tests/test_static_history_filters.py` 鎖住 compare panel 的 mode label、比較結論、跨視角文案與前端模組行數。
- `tests/test_hcs_plus_state.py` 鎖住溝通思考 10/10 收尾與下一步入口。

文案原則：

- 少用 raw id 與工程縮寫。
- 先說比較性質，再呈現檔名與數字。
- Warning 以解釋脈絡為主，不把可理解的跨視角比較說成錯誤。

剩餘風險：

- Report compare 的 mobile wrapping 尚未用瀏覽器截圖驗證。
- 其他面板仍可能有未掃到的工程語氣，留給後續互動與第二輪巡檢。

下一步：第 1 輪 / 互動思考 / #倫理考量

## 第 1 輪互動思考第一批

### 第 1 輪 / 互動思考 / #倫理考量

狀態：完成

本次使用：避免 report compare 的建議變化被使用者誤讀成即時交易指令。

核心判斷

1. 比較兩份既有報告只是在回顧報告差異，不等於產生新的交易建議。
2. 原本欄位名稱「建議」過短，容易被掃讀成當下系統指令。
3. 需要在比較結果中明確提醒：此處只比較既有報告。

落地修改

1. `backend/static/report_compare_panel.js` 新增「使用提醒」欄位。
2. 提醒文字為 `僅比較既有報告，不代表即時交易指令`。
3. `tests/test_static_history_filters.py` 鎖住該提醒文字。

優化說明

1. 降低使用者把歷史報告比較當成即時交易訊號的風險。
2. 不移除報告建議資訊，只補上使用邊界。
3. 剩餘風險是完整報告內仍可能有強行動語氣，後續可檢查報告模板。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認缺少「使用提醒」與「不代表即時交易指令」會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 互動思考 / #倫理勇氣

狀態：完成

本次使用：主動弱化過度權威的「建議」標籤，即使它原本較短、較醒目。

核心判斷

1. 投資系統應避免把模型/報告輸出包裝成無條件行動命令。
2. 把「建議」改為「報告建議變化」更誠實，因為它描述的是兩份報告之間的差異。
3. 這會稍微拉長欄位 label，但能降低過度自信使用。

落地修改

1. `report_compare_panel.js` 將 grid row label 從 `建議` 改成 `報告建議變化`。
2. 測試排除 compare panel 的 `['建議'` row。

優化說明

1. 以清楚邊界取代短而權威的命令感。
2. 不改 recommendation delta 的資料來源。
3. 後續可檢查 preview 的 `投資建議` 標題是否也需要更細緻的 context。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 互動思考 / #倫理判斷

狀態：完成

本次使用：判斷哪個位置最需要倫理提醒，並避免把提醒灑滿 UI 造成疲乏。

核心判斷

1. Report compare 是最容易被誤讀為「新結論」的位置，因此先在 compare result 補提醒。
2. 不應在每個數字格都加 disclaimer，否則使用者會忽略真正重要的警示。
3. 最小足夠提醒是單一「使用提醒」欄，搭配「報告建議變化」label。

落地修改

1. `tests/test_static_history_filters.py` 要求 `報告建議變化`、`使用提醒`、`不代表即時交易指令` 同時存在。
2. HCS 狀態測試納入 `#倫理考量`、`#倫理勇氣`、`#倫理判斷`。

優化說明

1. 在最可能誤用的互動點放置倫理邊界。
2. 控制提醒密度，避免 UI 噪音。
3. 剩餘風險是 rerun 完成 notification 可能仍讓使用者過度信任新報告，後續可檢查。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪互動思考第二批

### 第 1 輪 / 互動思考 / #複雜因果

狀態：完成

本次使用：避免使用者把兩份報告差異直接歸因為市場因果。

核心判斷

1. 報告建議變化可能來自資料更新、模型輸出差異、時間窗口不同或市場真實變化。
2. Compare panel 若只顯示 delta，使用者容易把報告差異當成市場因果。
3. 需要用一句短提醒把因果邊界說清楚。

落地修改

1. `backend/static/report_compare_panel.js` 新增「判讀層次」欄位。
2. 文案為 `報告差異不等於市場因果；搭配資料可信度與追蹤報酬判讀`。

優化說明

1. 降低把模型/報告差異誤當作市場原因的風險。
2. 不改演算法，只補足互動判讀脈絡。
3. 剩餘風險是完整因果分析仍需要閱讀完整報告與外部資料。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認缺少「判讀層次」會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 互動思考 / #湧現特性

狀態：完成

本次使用：提醒報告差異、資料可信度與追蹤報酬交互後才形成可判讀結果。

核心判斷

1. 單一欄位無法說明決策品質；報告建議、資料可信度與追蹤報酬一起才有意義。
2. 這種交互是湧現特性，不應被單一 delta 簡化。
3. 因此提醒應指向「搭配資料可信度與追蹤報酬判讀」。

落地修改

1. `tests/test_static_history_filters.py` 要求 compare panel 包含 `搭配資料可信度與追蹤報酬判讀`。
2. HCS log 記錄此提醒的湧現判讀理由。

優化說明

1. 引導使用者同時看多個訊號。
2. 不增加新的複雜模型或圖表。
3. 後續可在 performance panel 或 decision tracking 中補更多跨訊號說明。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 互動思考 / #分析層次

狀態：完成

本次使用：把 report compare 的判讀分成報告層、資料層與市場追蹤層。

核心判斷

1. 「報告建議變化」屬於報告層。
2. 「資料可信度」屬於資料層。
3. 「追蹤報酬」屬於市場結果追蹤層；三者不能混成同一結論。

落地修改

1. Result grid 新增「判讀層次」欄，並保留「資料可信度」「追蹤報酬」各自欄位。
2. HCS 測試納入 `#複雜因果`、`#湧現特性`、`#分析層次`。

優化說明

1. 幫助使用者在互動中分層判斷，不把所有變化壓成單一買賣訊號。
2. 不重排整個 grid，降低視覺衝擊。
3. 剩餘風險是文字提醒偏長，需後續 mobile QA。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_frontend_static_modules_are_sized`

## 第 1 輪互動思考第三批

### 第 1 輪 / 互動思考 / #網絡

狀態：完成

本次使用：把 report compare 的 warning 連回重跑流程，而不是讓 warning 孤立存在。

核心判斷

1. 當 compare API 回傳 `left_decision_needs_rerun` 或 `right_decision_needs_rerun`，代表資料快照與結論不同步。
2. 這不是單純的比較警告，而是 compare、data refresh、rerun 三個系統節點之間的網絡關係。
3. 前端 warning 應直接指出下一步系統動作：先重跑結論。

落地修改

1. `backend/static/report_compare_panel.js` 的 `compareWarningMessage` 新增 `decision_needs_rerun` 分支。
2. Warning 文字改為 `左側/右側報告需先重跑結論，再比較投資判斷。`

優化說明

1. 將 warning 從狀態描述推進到系統入口提示。
2. 不新增按鈕，避免在 compare panel 複製 rerun 操作面。
3. 剩餘風險是使用者仍需回到 preview 的 rerun 按鈕；後續可評估是否提供更直接入口。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認缺少 `decision_needs_rerun` 與重跑提示會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 互動思考 / #系統動力學

狀態：完成

本次使用：呈現資料更新後的正確動態順序：資料刷新後，結論需重跑，再比較投資判斷。

核心判斷

1. 如果資料快照已刷新但投資結論未重跑，直接比較投資判斷會混合不同時間層。
2. 系統正確順序應是 refresh data → rerun conclusion → compare decision。
3. Warning 需要用順序語言「先...再...」提醒使用者。

落地修改

1. Compare warning 文案使用 `需先重跑結論，再比較投資判斷`。
2. 靜態契約測試鎖住該順序語意。

優化說明

1. 減少使用者在資料已變更但結論未更新時做錯比較。
2. 不更改後端狀態機，只讓前端解讀更貼近系統動態。
3. 後續若要更完整，可把 suggested action 放進 compare API。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 互動思考 / #系統圖像

狀態：完成

本次使用：讓使用者看到 compare、資料可信度、追蹤報酬與 rerun 不是四個孤立功能。

核心判斷

1. Compare panel 已顯示比較結論、資料可信度、追蹤報酬與使用提醒。
2. 新增 rerun warning 轉譯後，使用者能看到資料更新與重跑結論之間的系統關係。
3. 這讓 compare panel 更像系統地圖上的一個節點，而不是孤立的 diff viewer。

落地修改

1. `tests/test_static_history_filters.py` 要求 compare panel 包含 `decision_needs_rerun` 與重跑提示。
2. HCS 狀態測試納入 `#網絡`、`#系統動力學`、`#系統圖像`。

優化說明

1. 補上跨功能關係提示，而不新增功能入口。
2. 控制改動面：只轉譯現有 warning code。
3. 剩餘風險是缺少可點擊的直接跳轉，留給後續互動思考批次判斷。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_frontend_static_modules_are_sized`

## 第 1 輪互動思考第四批

### 第 1 輪 / 互動思考 / #談判

狀態：完成

本次使用：把 compare warning 的重跑提示從命令式改成條件式，讓系統與使用者共同決定下一步。

核心判斷

1. 「需先重跑結論，再比較投資判斷」是正確順序，但語氣偏命令。
2. 使用者可能只是查看差異，不一定要立刻比較投資判斷。
3. 條件式「若要比較投資判斷，需先重跑結論」更像談判：說明前提與後果，而不是直接強推動作。

落地修改

1. `backend/static/report_compare_panel.js` 將 decision-needs-rerun warning 改成 `若要比較投資判斷，需先重跑結論`。
2. `tests/test_static_history_filters.py` 鎖住新語氣並排除舊命令式文案。

優化說明

1. 保留系統安全順序，同時尊重使用者當下目的。
2. 不新增彈窗或確認流程，避免打斷閱讀。
3. 剩餘風險是沒有直接跳到重跑按鈕的入口，後續可評估。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認舊文案會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 互動思考 / #說服

狀態：完成

本次使用：降低系統文案的強說服性，避免把使用者推向立即重跑。

核心判斷

1. 金融決策工具的 warning 應該說明條件，而不是用強勢語氣推動操作。
2. 「若要...需先...」比「需先...再...」更清楚地把重跑放在使用者目標之下。
3. 這種說服方式比較透明：不是要求你重跑，而是說明若要做某種比較，前置條件是什麼。

落地修改

1. 前端靜態測試新增 `需先重跑結論，再比較投資判斷` 不得出現在 compare panel。
2. Compare warning 仍保留 `decision_needs_rerun` code 分支，不隱藏風險。

優化說明

1. 降低 action bias。
2. 不弱化資料不同步風險。
3. 後續可檢查其他成功 toast 是否也過度肯定。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 互動思考 / #形塑行為

狀態：完成

本次使用：用條件式順序形塑審慎比較流程。

核心判斷

1. 好的行為引導不是更多按鈕，而是讓使用者知道何時該做哪一步。
2. 「若要比較投資判斷，需先重跑結論」把行為順序明確化。
3. 這有助於避免使用者在資料已更新但結論未重跑時，仍直接比較投資判斷。

落地修改

1. `compareWarningMessage` 的 rerun warning 文案改為條件式順序。
2. HCS 狀態測試納入 `#談判`、`#說服`、`#形塑行為`。

優化說明

1. 以文案形塑正確流程，而不是新增強制流程。
2. 保留使用者自主權。
3. 剩餘風險是沒有強制阻止錯誤比較；目前先採低摩擦提醒。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_completed_batches_have_traceable_changes_and_checks`
- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

## 第 1 輪互動思考第五批

### 第 1 輪 / 互動思考 / #從眾

狀態：完成

本次使用：檢查 report preview 是否用介面語氣把使用者推向跟隨報告結論。

核心判斷

1. Legacy preview 預設標題是「投資建議」，主指標 label 是「建議」。
2. 對金融研究工具而言，這種裸露語氣容易把報告輸出包裝成使用者應跟隨的行動。
3. 改成「報告建議」能保留資訊，同時提醒這是報告中的欄位，不是群體或系統命令。

落地修改

1. `backend/static/report_preview_panel.js` 將 legacy preview 預設標題從 `${report.ticker} 投資建議` 改成 `${report.ticker} 報告建議`。
2. 同一模組將 primary label 從 `建議` 改成 `報告建議`。
3. `tests/test_static_history_filters.py` 新增靜態與 Node 行為測試，鎖住 legacy preview 的新語氣。

優化說明

1. 解決 preview 預設入口過度強化單一結論的問題。
2. 犧牲是標題略長，但能明確標示來源層級。
3. 剩餘風險是後端已產生的 `preview.title` 仍可能帶有舊語氣，後續可檢查報告生成端。

驗證方式

- RED：`tests/test_static_history_filters.py::test_report_preview_panel_uses_decision_boundary_for_legacy_preview` 先確認舊標題會失敗。
- GREEN：`tests/test_static_history_filters.py::test_report_preview_panel_uses_decision_boundary_for_legacy_preview`

### 第 1 輪 / 互動思考 / #差異

狀態：完成

本次使用：區分報告產生的建議與使用者最後採取的判斷。

核心判斷

1. 「報告建議」仍然可能被誤讀成最後決策。
2. Preview 摘要是使用者最容易停留的閱讀點，適合放低摩擦邊界提醒。
3. 「仍需自行判斷」把報告輸出與使用者決策責任分開，不否定報告價值。

落地修改

1. `backend/static/report_preview_panel.js` 新增 `FALLBACK_SUMMARY`，在沒有可讀摘要時顯示「報告建議仍需自行判斷」。
2. `show()` 的 summary fallback 與 `legacyPreview()` 共用同一提醒，避免兩處文案漂移。
3. 靜態測試要求 `report_preview_panel.js` 包含「仍需自行判斷」。

優化說明

1. 補上決策邊界，不新增彈窗或阻斷流程。
2. 只影響缺少摘要的 fallback 與 legacy path，不改動模式化 preview 的既有摘要。
3. 剩餘風險是使用者若只看 primary metric 仍可能忽略提醒。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`
- `tests/test_static_history_filters.py::test_report_preview_panel_renders_mode_specific_preview_metrics`

### 第 1 輪 / 互動思考 / #情緒智商

狀態：完成

本次使用：降低買入、賣出或持有訊號在 preview 中造成的情緒化操作推力。

核心判斷

1. 使用者看到「投資建議」與「建議：買入」時，容易把資訊當成立即行動。
2. 「報告建議」比「建議」多一層來源標記，能降低被單一詞觸發的急迫感。
3. 摘要提醒保留冷靜判斷空間，適合金融研究場景。

落地修改

1. `tests/test_static_history_filters.py` 明確排除 `${report.ticker} 投資建議` 與 `label: '建議'` 回到 preview source。
2. `backend/static/report_preview_panel.js` 使用「報告建議」與自行判斷提醒作為預設文案。
3. HCS 狀態測試納入 `#從眾`、`#差異`、`#情緒智商` 的完成要求。

優化說明

1. 以語氣調整降低情緒化採用，而非隱藏投資資訊。
2. 維持既有追蹤報酬與 rerun 操作，不改變資料流。
3. 剩餘風險是完整報告內文仍可能使用強烈投資語氣，後續可在報告模板層處理。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認缺少「報告建議」與「仍需自行判斷」會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`
- GREEN：`tests/test_hcs_plus_state.py`

## 第 1 輪互動思考第六批

### 第 1 輪 / 互動思考 / #領導原則

狀態：完成

本次使用：檢查系統在 preview/rerun 入口如何帶領使用者理解下一步。

核心判斷

1. 「重跑最終建議」像是系統要重新發布最後判斷，容易把使用者帶向接受結果。
2. 更好的領導方式是說明 rerun 產出的是「報告結論」，讓使用者知道這仍是研究材料。
3. 靜態 preview 骨架也應先呈現「報告建議」，避免 JS 尚未覆寫時露出舊語氣。

落地修改

1. `backend/static/report_preview_panel.js` 將 rerun final button 文字改成 `重跑${shortLabel}報告結論`。
2. `backend/static/index.html` 將 preview 預設標題改為「報告建議」。
3. `tests/test_static_history_filters.py` 用靜態與 Node 測試鎖住 rerun button 的新文案。

優化說明

1. 讓系統帶領使用者回到「報告產物」而非「最終命令」。
2. 不新增流程和確認視窗，保持操作效率。
3. 剩餘風險是後端 `scope_label` 成功通知仍可能使用不同語氣，後續可追蹤。

驗證方式

- RED：`tests/test_static_history_filters.py::test_report_preview_panel_uses_decision_boundary_for_legacy_preview` 先確認舊 rerun 文案會失敗。
- GREEN：`tests/test_static_history_filters.py::test_report_preview_panel_uses_decision_boundary_for_legacy_preview`

### 第 1 輪 / 互動思考 / #權力動態

狀態：完成

本次使用：降低 UI 文字把系統放在過高權威位置的風險。

核心判斷

1. 「最終建議」把權威集中在系統輸出，且暗示它已是最後答案。
2. 「報告結論」保留分析結果的專業性，但權力位置比較清楚：報告提供結論，使用者做判斷。
3. Close button 的 aria label 也不應繼續說「投資建議預覽」。

落地修改

1. `backend/static/index.html` 將關閉按鈕 aria label 改為「關閉報告預覽」。
2. 靜態測試排除「關閉投資建議預覽」與「重跑最終建議」。
3. `report_preview_panel.js` 不再包含 `重跑${shortLabel}最終建議`。

優化說明

1. 以用字調整權力關係，不改變功能權限。
2. 改動同時涵蓋可視文字與輔助科技文字。
3. 剩餘風險是其他頁面仍有「投資建議」作為 filter label，需在後續判斷是否屬於欄位名稱或權威語氣。

驗證方式

- `tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`

### 第 1 輪 / 互動思考 / #責任

狀態：完成

本次使用：讓 preview 初始狀態、動態渲染與 rerun 行為都清楚標示報告層級。

核心判斷

1. 責任邊界不只存在 summary 文字，也存在標題、label、按鈕和 aria label 的一致性。
2. 若靜態 HTML 還留著「建議」和「投資建議」，就會和 JS 的「報告建議」產生責任邊界不一致。
3. 將 HTML fallback 同步為「報告建議」可避免載入前或測試環境中的語意回退。

落地修改

1. `backend/static/index.html` 將 preview 預設 label 從「建議」改為「報告建議」。
2. 同檔將 rerun button fallback 改為「重跑報告結論」。
3. HCS 狀態測試納入 `#領導原則`、`#權力動態`、`#責任`。

優化說明

1. 讓責任邊界從 JS runtime 擴展到 HTML 初始骨架。
2. 避免使用者或輔助工具先接觸到舊的權威語氣。
3. 剩餘風險是完整報告正文與篩選器仍有「投資建議」作為名詞，下一批可用自我覺察/制定策略決定是否收斂。

驗證方式

- RED：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired` 先確認 index fallback 舊文案會失敗。
- GREEN：`tests/test_static_history_filters.py::test_provider_sla_and_manual_refresh_controls_are_wired`
- GREEN：`tests/test_hcs_plus_state.py`

## 第 1 輪互動思考第七批

### 第 1 輪 / 互動思考 / #自我覺察

狀態：完成

本次使用：讓前端 UI 清楚知道自己是在呈現報告資料，而不是代替使用者做投資決策。

核心判斷

1. 後端報告、prompt 與測試中的「投資建議」是領域契約，不適合在本批大範圍改名。
2. History filter 的「投資建議 / 全部建議」屬於使用者掃讀入口，會和 preview 的「報告建議」角色不一致。
3. UI 應自覺地把自己定位成報告瀏覽器與決策追蹤工具，而不是交易指令面板。

落地修改

1. `backend/static/index.html` 將 history recommendation filter label 改為「報告建議」。
2. 同一 filter 的 all option 改為「全部報告建議」。
3. `tests/test_frontend_visual_optional.py` 同步 optional visual fixture 的 filter 與 preview label。

優化說明

1. 收斂前端操作入口的角色語氣。
2. 保留後端領域契約中的「投資建議」，避免破壞報告解析與既有測試。
3. 剩餘風險是完整報告正文仍有強烈語氣，下一輪需從批判思考重新拆解是否要動報告生成層。

驗證方式

- RED：`tests/test_static_history_filters.py::test_history_data_trust_filter_is_wired_to_api_params` 先確認舊 filter label 會失敗。
- GREEN：`tests/test_static_history_filters.py::test_history_data_trust_filter_is_wired_to_api_params`

### 第 1 輪 / 互動思考 / #制定策略

狀態：完成

本次使用：把第 1 輪互動思考收尾，並設定第 2 輪從問題拆解重新開始。

核心判斷

1. 第 1 輪互動思考已從倫理、因果、系統、行為引導、權力關係一路收斂到 UI 自我定位。
2. 下一輪不應直接繼續擴大文案修改，而應回到批判思考重新拆解剩餘高風險問題。
3. 最合理的下一批是第 2 輪批判思考的 `#拆解問題`、`#問對問題`、`#差距分析`。

落地修改

1. `tests/test_hcs_plus_state.py` 新增互動思考收尾 checkpoint。
2. `docs/hcs-plus-optimization-state.md` 將第 2 輪批判思考第一批標成下一批。
3. 本嚴格輪巡附件記錄互動思考 20/20 完成。

優化說明

1. 把下一步從「繼續改文案」提升為「重新檢查問題結構」。
2. 不宣稱 HCS Plus 完整完成，因為仍需第 2、3 輪與最後綜合優化。
3. 剩餘風險是第 2 輪可能需要重新選擇更高影響的產品層切入點。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少互動思考收尾會失敗。
- GREEN：`tests/test_hcs_plus_state.py`

## 第 1 輪互動思考收尾

- 已完成：20/20。
- 已落地：report compare 的使用提醒、因果層次、重跑條件式提示；report preview 的報告建議語氣、自行判斷提醒、報告結論 rerun CTA；history filter 的報告欄位定位。
- 已驗證：`tests/test_hcs_plus_state.py`、`tests/test_static_history_filters.py` 相關前端契約與 Node 行為測試。
- 剩餘風險：後端報告正文仍使用「投資建議」作為領域契約；是否要調整需在第 2 輪重新拆解成本與風險。
- 下一步：第 2 輪 / 批判思考 / #拆解問題。

## 第 2 輪批判思考第一批

### 第 2 輪 / 批判思考 / #拆解問題

狀態：完成

本次使用：把第 1 輪留下的「投資建議」語氣問題拆成可分別處理的層級。

核心判斷

1. 前端顯示層已改用「報告建議 / 報告結論」，但後端報告正文與 prompt 契約仍保留「投資建議」。
2. 這不一定是錯誤；它可能是報告解析、合規檢查與既有測試依賴的領域契約。
3. 第 2 輪要先拆清楚三層：報告正文契約、prompt/agent 輸出契約、前端顯示層。

落地修改

1. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪批判思考問題雷達」。
2. 問題雷達將「報告正文契約 vs 前端顯示層」列為第一個高風險問題。
3. `tests/test_hcs_plus_state.py` 新增第 2 輪問題雷達測試，避免後續只靠敘述記憶。

優化說明

1. 先拆問題，而不是貿然改報告正文，避免破壞解析契約。
2. 犧牲是本批沒有直接改善 UI；換來後續改動能先看清責任邊界。
3. 剩餘風險是雷達本身仍需下一批變數與偏誤分析來排序。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少第 2 輪 section 與問題雷達會失敗。
- GREEN：`tests/test_hcs_plus_state.py`

### 第 2 輪 / 批判思考 / #問對問題

狀態：完成

本次使用：把下一步從「是否繼續改投資建議」改成可驗證的判斷問題。

核心判斷

1. 壞問題是「還有哪些地方有投資建議四個字？」因為它會推向盲目替換。
2. 好問題是「哪些使用者入口需要顯示層降權威語氣，哪些後端契約必須保留原詞以維持解析？」
3. 第 2 輪需要把問題和證據綁住，避免純文案潔癖。

落地修改

1. 問題雷達新增 `關鍵問題` 欄。
2. 第一列問題要求分辨報告契約與前端顯示層。
3. HCS 狀態測試要求狀態表包含 `關鍵問題`。

優化說明

1. 把思考焦點從字串搜尋轉成契約邊界判斷。
2. 保留後續改正文的可能性，但要求先建立證據。
3. 剩餘風險是尚未列出所有變數，下一批處理。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_problem_radar_tracks_remaining_high_risk_gaps`

### 第 2 輪 / 批判思考 / #差距分析

狀態：完成

本次使用：量出第 1 輪成果與第 2 輪目標之間的缺口。

核心判斷

1. 現況：前端主要入口已標示「報告建議」，但完整報告正文、prompt 與測試仍使用「投資建議」。
2. 目標：使用者入口不把系統輸出表述成交易指令，同時後端契約不因文案調整失去可解析性。
3. 缺口：還沒有明確證據說明哪些層該保留領域詞，哪些層該降權威語氣。

落地修改

1. 問題雷達新增 `差距` 與 `驗證證據` 欄。
2. `docs/hcs-plus-optimization-state.md` 將第 2 輪第一批標成完成，下一批移到 `#變數分析/#偏誤辨識/#偏誤降低`。
3. 本嚴格輪巡附件同步下一步為第 2 輪 / 批判思考 / #變數分析。

優化說明

1. 讓第 2 輪後續改動有可對照的目標和缺口。
2. 不把「保留投資建議」或「全部改名」預設成答案。
3. 剩餘風險是尚未衡量各層變數影響，下一批處理。

驗證方式

- `tests/test_hcs_plus_state.py`

## 第 2 輪批判思考第二批

### 第 2 輪 / 批判思考 / #變數分析

狀態：完成

本次使用：列出影響「投資建議」契約詞是否可替換的主要變數。

核心判斷

1. 同一個詞在不同層級有不同功能：使用者顯示詞可以降權威，機器契約詞可能必須保留。
2. 變數至少包含：使用者入口、報告正文標題、prompt 區塊、parser/conformance 測試、歷史 fixtures。
3. 沒有變數表就直接替換，容易讓 UI 變漂亮但報告解析壞掉。

落地修改

1. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪批判思考變數與偏誤護欄」。
2. 變數表區分「可改名顯示層」與「需保留契約層」。
3. `tests/test_hcs_plus_state.py` 要求狀態表記錄 `可改名顯示層` 與 `需保留契約層`。

優化說明

1. 把後續改名決策拆成可觀察變數。
2. 避免把所有文字都當成同一種 UI 文案。
3. 剩餘風險是尚未量化每個變數的改動成本，下一批用決策樹處理。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少變數與偏誤護欄會失敗。
- GREEN：`tests/test_hcs_plus_state.py`

### 第 2 輪 / 批判思考 / #偏誤辨識

狀態：完成

本次使用：辨識第 2 輪最可能把專案帶偏的兩種偏誤。

核心判斷

1. 字串潔癖偏誤：看到「投資建議」就想全部替換，忽略它在 parser 和測試中的契約用途。
2. 過度保守契約偏誤：因為後端契約需要保留，就拒絕改善使用者入口的權威語氣。
3. 兩種偏誤都會傷害目標；正確方向是依層級分開處理。

落地修改

1. 變數與偏誤護欄表新增 `字串潔癖偏誤`。
2. 同表記錄顯示層與契約層的不同處理方向。
3. HCS 測試要求狀態表包含該偏誤名稱。

優化說明

1. 讓下一批決策不被「全改」或「全不改」綁架。
2. 將偏誤寫進狀態表，方便後續檢查 diff 時回扣。
3. 剩餘風險是偏誤護欄目前仍是文件約束，尚未有專門 parser coverage map。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_variable_and_bias_guardrails_are_recorded`

### 第 2 輪 / 批判思考 / #偏誤降低

狀態：完成

本次使用：把偏誤轉成下一批改動前必查的測試與證據。

核心判斷

1. 降低字串潔癖偏誤的方法不是停止改名，而是要求先跑前端契約與解析契約回歸。
2. 降低過度保守偏誤的方法是允許顯示層改名，只要契約層測試維持綠燈。
3. 「解析契約回歸」必須成為下一批前置證據。

落地修改

1. 變數與偏誤護欄表新增 `解析契約回歸` 證據要求。
2. `docs/hcs-plus-optimization-state.md` 將第 2 輪第二批標成完成，下一批移到 `#決策樹/#目的/#效用`。
3. 本嚴格輪巡附件同步下一步為第 2 輪 / 批判思考 / #決策樹。

優化說明

1. 讓下一批若要改報告正文或 prompt，必須先說明會跑哪些契約測試。
2. 把「改名」從主觀偏好變成可驗證決策。
3. 剩餘風險是尚未選定最佳決策路徑，下一批處理。

驗證方式

- `tests/test_hcs_plus_state.py`

## 第 2 輪批判思考第三批

### 第 2 輪 / 批判思考 / #決策樹

狀態：完成

本次使用：把契約詞後續處理轉成明確分支，避免「全改」或「全不改」。

核心判斷

1. 使用者顯示層：應優先使用「報告建議 / 報告結論」這類降權威語氣。
2. 機器解析契約：若 parser、prompt 或 conformance test 依賴 `[投資建議]`，預設保留契約詞。
3. 完整報告正文：屬於混合層，需先補 coverage map，再決定加註、拆分或保留。

落地修改

1. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪批判思考契約詞決策樹」。
2. 決策樹用 `使用者顯示層`、`機器解析契約`、`完整報告正文` 三個分支記錄處理策略。
3. `tests/test_hcs_plus_state.py` 要求狀態表包含該決策樹與三個分支。

優化說明

1. 把下一步從主觀命名偏好轉成可分流決策。
2. 避免破壞契約，也避免因契約存在而停止改善顯示層。
3. 剩餘風險是尚未實際列出全部契約依賴，下一批用統計/覆蓋盤點處理。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少契約詞決策樹會失敗。
- GREEN：`tests/test_hcs_plus_state.py`

### 第 2 輪 / 批判思考 / #目的

狀態：完成

本次使用：明確本輪處理契約詞的目的，不讓工作滑向單純美化文案。

核心判斷

1. 目的不是消滅「投資建議」四個字。
2. 目的是真實降低使用者入口的交易指令感，同時保住報告可解析、可稽核、可測試。
3. 若完整報告正文要改，必須服務這個目的，而不是只追求語氣一致。

落地修改

1. 契約詞決策樹新增目的描述：降低權威感與保留解析契約並重。
2. 狀態表將 `最高效用路徑` 指向 coverage map，而非立即改正文。
3. HCS 測試要求狀態表包含 `最高效用路徑`。

優化說明

1. 防止第 2 輪偏離產品可信度目標。
2. 讓後續大改前先問效用與風險。
3. 剩餘風險是 coverage map 還未建立。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_contract_term_decision_tree_is_recorded`

### 第 2 輪 / 批判思考 / #效用

狀態：完成

本次使用：選擇目前期望效用最高、風險最低的下一步。

核心判斷

1. 立即改完整報告正文的效用不明，破壞契約的風險較高。
2. 只停在文件分析效用有限；下一步需要盤點實際測試與契約依賴。
3. 最高效用路徑是先補契約 coverage map，再決定是否拆分正文顯示詞與機器契約詞。

落地修改

1. 契約詞決策樹列出 `最高效用路徑`。
2. `docs/hcs-plus-optimization-state.md` 將第 2 輪第三批標成完成，下一批移到 `#信賴區間/#相關性/#描述統計`。
3. 本嚴格輪巡附件同步下一步為第 2 輪 / 批判思考 / #信賴區間。

優化說明

1. 用效用判斷避免過早大改。
2. 下一批將從「有哪些契約依賴」走向「依賴覆蓋與統計盤點」。
3. 剩餘風險是 coverage map 若太粗，仍可能低估正文改動成本。

驗證方式

- `tests/test_hcs_plus_state.py`

## 第 2 輪批判思考第四批

### 第 2 輪 / 批判思考 / #信賴區間

狀態：完成

本次使用：界定契約詞 coverage map 的可信邊界，避免把 grep 結果誤當完整母體。

核心判斷

1. 直接掃 `backend/` 會把 `backend/output/` 生成報告納入，導致樣本膨脹。
2. 本批 coverage map 只代表可維護來源檔：`tests/` 與排除生成輸出的 `backend/`。
3. 因此這是最低可觀測樣本，不是完整母體信賴區間。

落地修改

1. `tests/test_hcs_plus_state.py` 新增 `_files_containing_contract_terms()`，自動統計契約詞出現在 `tests/` 與 `backend/` 的來源檔數。
2. 同 helper 排除 `backend/output/`、`__pycache__` 與 `.pytest_cache`。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪批判思考契約覆蓋統計」。

優化說明

1. 讓數字有邊界，不把生成輸出當成源碼依賴。
2. 犧牲是 coverage map 暫不涵蓋所有 runtime 產物。
3. 剩餘風險是仍需下一批判斷改正文的機率與顯著性。

驗證方式

- RED：`tests/test_hcs_plus_state.py::test_hcs_plus_round2_contract_coverage_map_has_observed_counts` 先確認缺少 coverage 統計會失敗。
- GREEN：`tests/test_hcs_plus_state.py`

### 第 2 輪 / 批判思考 / #相關性

狀態：完成

本次使用：避免把「檔案含有契約詞」直接推論成「該檔必須保留契約詞」或「該檔可以替換」。

核心判斷

1. `tests/test_static_history_filters.py` 含「投資建議」是為了排除前端舊語氣，不代表它依賴契約詞。
2. `backend/structured_output_parser.py` 含 `[投資建議]` 則高度相關於 parser 契約。
3. 因此契約詞出現只是一個警訊，相關不等於可替換，也不等於不可替換。

落地修改

1. coverage 統計加入「相關不等於可替換」說明。
2. 狀態表把測試檔與後端檔分開計數，避免混成單一風險。
3. HCS 測試要求狀態表包含該相關性提醒。

優化說明

1. 降低由字串搜尋導出的錯誤結論。
2. 讓下一批能再按 parser、prompt、UI test 細分。
3. 剩餘風險是尚未人工分類每個檔案的契約強度。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_contract_coverage_map_has_observed_counts`

### 第 2 輪 / 批判思考 / #描述統計

狀態：完成

本次使用：把契約詞依賴從口頭描述變成可更新的檔案數。

核心判斷

1. 目前可維護來源中，`tests/` 有 22 個檔案含契約詞。
2. 排除生成輸出後，`backend/` 有 25 個來源檔含契約詞。
3. 這表示契約詞影響面不小，完整報告正文或 prompt 改名不能只靠單一測試判斷。

落地修改

1. `docs/hcs-plus-optimization-state.md` 記錄 `測試檔案數：22` 與 `後端檔案數：25`。
2. `tests/test_hcs_plus_state.py` 用目前 repo 自動計算這兩個數字，要求狀態表同步。
3. 本嚴格輪巡附件將下一批推進到 `#機率/#迴歸/#顯著性`。

優化說明

1. 讓 coverage map 具備可重跑的描述統計。
2. 未來檔案數變動時，測試會逼狀態表更新。
3. 剩餘風險是描述統計只算檔案數，尚未評估每個檔案的權重。

驗證方式

- `tests/test_hcs_plus_state.py`

## 第 2 輪批判思考第五批

### 第 2 輪 / 批判思考 / #機率

狀態：完成

本次使用：估計契約詞改動最可能造成哪類回歸。

核心判斷

1. 直接改 `[投資建議]` 或 `最終投資建議` 的高機率回歸點是 parser、conformance、report preview 與 audit rules。
2. 前端顯示層已由 static tests 鎖住，回歸機率較可控。
3. 完整報告正文屬混合層，回歸機率取決於是否同時改 parser/template/test fixture。

落地修改

1. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪批判思考契約回歸風險排序」。
2. 風險表標記 `高機率回歸`。
3. `tests/test_hcs_plus_state.py` 要求狀態表包含該風險等級。

優化說明

1. 把「可能會壞」拆成具體高機率風險。
2. 避免下一批只靠直覺選測試。
3. 剩餘風險是尚未實際跑所有解析測試矩陣。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少風險排序會失敗。
- GREEN：`tests/test_hcs_plus_state.py`

### 第 2 輪 / 批判思考 / #迴歸

狀態：完成

本次使用：把契約詞改動的回歸檢查轉成具名測試組。

核心判斷

1. `tests/test_report_preview.py` 能攔住 preview 抽取與 legacy report 行為回歸。
2. `tests/test_report_conformance.py` 能攔住報告結構契約回歸。
3. `tests/test_static_history_filters.py` 能攔住前端顯示層回到交易指令語氣。

落地修改

1. 風險排序表新增 `回歸測試組` 欄。
2. 狀態表列出 `tests/test_report_preview.py`、`tests/test_report_conformance.py`、`tests/test_static_history_filters.py`。
3. HCS 測試要求上述測試檔名出現在狀態表。

優化說明

1. 讓後續契約詞改動有明確測試入口。
2. 測試組橫跨 parser、conformance、front-end 三層。
3. 剩餘風險是還需把 audit/prompt tests 納入更完整的矩陣。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_contract_regression_risk_ranking_is_recorded`

### 第 2 輪 / 批判思考 / #顯著性

狀態：完成

本次使用：定義什麼樣的契約詞改動算顯著，必須提高驗證強度。

核心判斷

1. 只改前端顯示 label 且不碰 parser/template，屬低顯著性，可用前端契約測試驗證。
2. 改 `[投資建議]`、`[/投資建議]`、`最終投資建議` 或 report template decision heading，屬高顯著性。
3. 高顯著性改動必須跑 parser/conformance/report-preview/audit 相關測試，不能只跑單一靜態測試。

落地修改

1. 風險排序表新增 `顯著性門檻`。
2. `docs/hcs-plus-optimization-state.md` 將第 2 輪第五批標成完成，下一批移到 `#證據基礎/#演繹/#歸納`。
3. 本嚴格輪巡附件同步下一步為第 2 輪 / 批判思考 / #證據基礎。
4. 歷史 checkpoint：下一步：第 2 輪 / 批判思考 / #證據基礎。

優化說明

1. 把驗證強度與改動風險綁定。
2. 後續若要動完整報告正文，必須先承認是高顯著性改動。
3. 剩餘風險是尚未把完整測試矩陣自動編排成單一命令。

驗證方式

- `tests/test_hcs_plus_state.py`

## 第 2 輪批判思考第六批

### 第 2 輪 / 批判思考 / #證據基礎

狀態：完成

本次使用：把上一批 coverage map 與回歸風險排序轉成改檔前可查的測試證據矩陣。

核心判斷

1. 目前最可靠的證據不是單一測試，而是 `tests/` 22 檔與 `backend/` 25 檔的契約詞分布，加上高/中/低回歸風險排序。
2. 高顯著性契約詞改動的證據鏈必須同時看 parser、conformance、audit 與 prompt routing。
3. 前端顯示層已另有 static/visual tests，不能拿來證明 parser 或 prompt 契約安全。

落地修改

1. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪批判思考契約測試矩陣」。
2. 矩陣把 `高顯著性改動`、混合層正文/模板改動、低顯著性顯示層改動分別映射到必跑測試。
3. `tests/test_hcs_plus_state.py` 新增測試，要求矩陣列出證據基礎、演繹規則、歸納限制與必跑測試。

優化說明

1. 解決「知道風險但不知道下一步跑什麼測試」的落地缺口。
2. 犧牲的是矩陣仍需人工判斷改動層級；不把它包成單一自動命令。
3. 剩餘風險是矩陣仍未評估每個真實報告輸出的語意品質。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少矩陣與第六批紀錄會失敗。
- GREEN：`tests/test_hcs_plus_state.py`

### 第 2 輪 / 批判思考 / #演繹

狀態：完成

本次使用：把「改動層級」演繹成最小必跑測試組，避免每次靠臨場直覺選測試。

核心判斷

1. 若改 `[投資建議]`、`[/投資建議]`、`最終投資建議`、prompt 契約、parser regex 或 template decision heading，必須視為高顯著性機器契約變更。
2. 若只改完整報告正文或模板顯示，仍可能經過渲染、儲存與 HTTP preview 流程，不能只跑前端字串測試。
3. 若只改 filter、preview、compare、rerun CTA 等前端 label，才可用前端契約測試作為主要門檻。

落地修改

1. 契約測試矩陣新增 `演繹規則` 欄。
2. 高顯著性改動映射到 `tests/test_report_preview.py`、`tests/test_report_conformance.py`、`tests/test_audit_rules.py`、`tests/test_prompt_context_routing.py`。
3. 混合層與顯示層分別映射到 report template/storage/http 與 static/visual 測試。

優化說明

1. 把測試選擇從模糊風險感轉為明確規則。
2. 避免只因某次小改通過 static tests，就錯誤推論 parser/prompt 合約安全。
3. 剩餘風險是規則需在未來新增契約詞或報告管線時同步更新。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_required_contract_test_matrix_is_recorded`

### 第 2 輪 / 批判思考 / #歸納

狀態：完成

本次使用：標出測試矩陣能外推到哪裡、不能外推到哪裡。

核心判斷

1. 從現有來源檔與測試矩陣只能歸納出「目前可維護來源中的代表性契約風險」。
2. 測試通過不能歸納成所有生成報告、所有 LLM 輸出或所有使用者解讀都安全。
3. 下一批必須檢查謬誤、來源品質與情境脈絡，防止矩陣變成過度自信的保證書。

落地修改

1. 契約測試矩陣新增 `歸納限制` 欄，明確寫出每類測試的外推邊界。
2. 主狀態表把第 2 輪批判思考第六批標成完成，下一批移到 `#謬誤/#來源品質/#情境脈絡`。
3. 本嚴格輪巡附件同步下一步為第 2 輪 / 批判思考 / #謬誤。
4. 歷史 checkpoint：下一步：第 2 輪 / 批判思考 / #謬誤。

優化說明

1. 保留測試矩陣的實用性，同時避免把測試通過當成語意品質完整證明。
2. 把下一批目標自然接到錯誤推論與來源品質檢查。
3. 剩餘風險是尚未把矩陣做成自動化 pytest marker 或腳本。

驗證方式

- `tests/test_hcs_plus_state.py`

## 第 2 輪批判思考第七批

### 第 2 輪 / 批判思考 / #謬誤

狀態：完成

本次使用：檢查契約測試矩陣可能誘發的錯誤推論，避免測試綠燈被誤讀成完整語意安全。

核心判斷

1. 最大謬誤是「測試通過不等於語意安全」：合約測試只證明指定契約未回退，不證明使用者不會把報告當交易指令。
2. 第二個謬誤是「coverage map 不等於完整母體」：22 個測試檔與 25 個後端來源檔不是所有生成報告或未來 LLM 輸出。
3. 第三個謬誤是「frontend tests 不等於 parser/prompt safety」：前端 label 測試不能支持機器契約詞替換。

落地修改

1. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪批判思考契約矩陣反謬誤護欄」。
2. 護欄表列出三個易犯謬誤、錯誤推論、來源品質分級與情境脈絡護欄。
3. `tests/test_hcs_plus_state.py` 新增測試，要求這些謬誤與第七批紀錄存在。

優化說明

1. 讓矩陣從「測試清單」升級成「有推論邊界的驗證工具」。
2. 犧牲的是狀態表更長，但換來後續改契約詞時不容易把測試結果外推過頭。
3. 剩餘風險是尚未把這些護欄轉成 pytest marker 或自動選測腳本。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少反謬誤護欄與第七批紀錄會失敗。
- GREEN：`tests/test_hcs_plus_state.py`

### 第 2 輪 / 批判思考 / #來源品質

狀態：完成

本次使用：標出哪些證據可以支撐契約改動判斷，哪些只能作為輔助觀察，哪些不得當成完成證據。

核心判斷

1. 高品質來源是可重跑測試、parser/template source、prompt routing、audit 與 conformance 規則。
2. 次級來源是文件狀態表、人工閱讀摘要、前端 static/visual tests 對應到的顯示層觀察。
3. 單次生成報告、未重跑截圖、未標來源的口頭判斷不得作為完成證據。

落地修改

1. 反謬誤護欄表新增 `來源品質分級` 欄。
2. 每個謬誤都標明 `高品質來源`、`次級來源` 與 `不得作為完成證據`。
3. 主狀態表新增 D45，記錄測試綠燈不可外推成完整語意安全。

優化說明

1. 避免後續用低品質證據支持高顯著性契約變更。
2. 讓「文件紀錄」回到輔助角色，不取代可重跑測試。
3. 剩餘風險是未來若新增測試或報告生成路徑，來源分級需同步更新。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_contract_matrix_fallacy_source_context_guardrail_is_recorded`

### 第 2 輪 / 批判思考 / #情境脈絡

狀態：完成

本次使用：界定同一個測試矩陣在不同改動情境下的適用方式。

核心判斷

1. 機器契約變更包含 `[投資建議]`、prompt、parser regex、template decision heading，必須走高顯著性測試矩陣。
2. 使用者顯示層改動可以用 front-end static/visual tests 驗證，但不能證明 parser/prompt safety。
3. 完整報告正文改動屬混合情境，需同時看報告渲染、儲存、HTTP preview 與語氣邊界。

落地修改

1. 反謬誤護欄表新增 `情境脈絡護欄` 欄。
2. 主狀態表把第 2 輪批判思考第七批標成完成，下一批移到 `#批判/#估算/#詮釋框架`。
3. 本嚴格輪巡附件同步下一步為第 2 輪 / 批判思考 / #批判。
4. 歷史 checkpoint：下一步：第 2 輪 / 批判思考 / #批判。

優化說明

1. 讓測試矩陣按改動情境使用，而不是一張表套所有修改。
2. 保留前端顯示層降權威語氣的低成本驗證路徑，同時守住機器契約邊界。
3. 剩餘風險是下一批仍需批判矩陣是否過重，並估算是否值得做成命令分組。

驗證方式

- `tests/test_hcs_plus_state.py`

## 第 2 輪批判思考第八批

### 第 2 輪 / 批判思考 / #批判

狀態：完成

本次使用：重新檢查契約測試矩陣本身是否太重，會不會讓操作者因為表格複雜而乾脆不跑測試。

核心判斷

1. 矩陣過重風險是真實存在的：目前已有 coverage、風險排序、測試矩陣與反謬誤護欄四層資訊。
2. 直接做自動選測腳本仍太早，因為改動層級仍需要人工判斷；過早工具化可能把判斷責任藏進命令。
3. 最小批判後的決策是先把矩陣收斂成 3 組命令，而不是新增測試架構。

落地修改

1. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪批判思考契約矩陣可執行性評估」。
2. 狀態表新增 D46，記錄暫不新增自動選測腳本，先用最小命令分組降低執行摩擦。
3. `tests/test_hcs_plus_state.py` 新增測試，要求可執行性評估、第八批紀錄與下一步 checkpoint 存在。

優化說明

1. 把矩陣從「完整但可能不好用」推向「可依情境直接複製命令」。
2. 犧牲的是還沒有全自動選測；換來人工判斷仍清楚留在流程中。
3. 剩餘風險是下一批仍需檢查這個 4/3/2 分組是否合理且可驗證。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少可執行性評估與第八批紀錄會失敗。
- GREEN：`tests/test_hcs_plus_state.py`

### 第 2 輪 / 批判思考 / #估算

狀態：完成

本次使用：估算不同改動情境的最低測試成本，讓操作者能在改檔前快速選測。

核心判斷

1. 高顯著性機器契約變更的 estimated scope 是 4 個測試檔：preview、conformance、audit、prompt routing。
2. 混合層正文或模板顯示改動的 estimated scope 是 3 個測試檔：mode templates、report storage、frontend HTTP e2e。
3. 低顯著性使用者顯示層改動的 estimated scope 是 2 個測試檔：static history filters、optional visual fixture。

落地修改

1. 可執行性評估表新增 `estimated scope` 欄。
2. 評估表列出 4 個測試檔、3 個測試檔與 2 個測試檔三種最小命令分組。
3. 每組都提供可直接執行的 `$(scripts/project_python.sh) -m pytest ... -q` 命令。

優化說明

1. 把「要跑哪些測試」從文件推理降成一眼可選的成本估算。
2. 避免每次小型顯示層改動都被高顯著性矩陣拖慢。
3. 剩餘風險是估算只看檔案數，不代表實際 runtime 或 flakiness 成本。

驗證方式

- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_contract_matrix_operability_estimate_frame_is_recorded`

### 第 2 輪 / 批判思考 / #詮釋框架

狀態：完成

本次使用：定義最小命令分組的綠燈、紅燈與不得解讀為，避免測試結果再度被過度外推。

核心判斷

1. 綠燈代表該情境下的已知契約未回退，不代表所有生成報告語意安全。
2. 紅燈代表該改動不可繼續合併或宣稱完成，需要回頭修契約或調整改動層級。
3. 不得解讀為用來切斷詮釋過度：前端綠燈不得解讀為 parser/prompt safety，混合層綠燈不得解讀為使用者已正確理解語氣。

落地修改

1. 可執行性評估表新增 `詮釋框架` 欄。
2. 每個改動情境都寫入 `綠燈代表`、`紅燈代表`、`不得解讀為`。
3. 主狀態表把第 2 輪第八批標成完成，下一批移到 `#合理性/#可驗證性`。
4. 歷史 checkpoint：下一步：第 2 輪 / 批判思考 / #合理性。

優化說明

1. 讓命令分組不只是測試清單，也包含結果判讀規則。
2. 把第七批反謬誤護欄延伸到實際執行後的詮釋。
3. 剩餘風險是下一批需確認整個第 2 輪批判思考是否合理收尾，並用測試鎖住。

驗證方式

- `tests/test_hcs_plus_state.py`

## 第 2 輪批判思考第九批

### 第 2 輪 / 批判思考 / #合理性

狀態：完成

本次使用：檢查第 2 輪批判思考是否以合理方式收尾，而不是為了追求表面一致直接改動後端契約詞。

核心判斷

1. 第 2 輪批判思考的合理路徑是先建立契約詞決策、coverage、回歸風險、測試矩陣、反謬誤護欄與最小命令分組。
2. 暫不新增自動選測腳本是合理取捨，因為契約層級仍需人工判斷；過早工具化會掩蓋責任邊界。
3. 此階段可以轉入創意思考，下一輪應把矩陣從可驗證推向更容易被操作者學會與採用。

落地修改

1. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪批判思考收尾檢查」。
2. 主狀態表新增 D47，記錄第 2 輪批判思考以 26/26 單項完成作為合理收尾。
3. 本嚴格輪巡附件將第 2 輪 / 批判思考 / `#合理性` 標成完成。

優化說明

1. 防止本輪停在「下一批待辦」而沒有收斂判斷。
2. 讓下一分類入口有明確理由：接下來不是繼續批判矩陣，而是設計更好學、更好採用的矩陣體驗。
3. 剩餘風險是矩陣仍未工具化，後續需在創意思考中判斷低成本採用方式。

驗證方式

- RED：`tests/test_hcs_plus_state.py` 先確認缺少第 2 輪批判思考收尾與 `#合理性/#可驗證性` 章節會失敗。
- GREEN：`tests/test_hcs_plus_state.py`

### 第 2 輪 / 批判思考 / #可驗證性

狀態：完成

本次使用：把第 2 輪批判思考完成狀態轉成可重跑檢查，避免只靠人工記憶說 26/26 已完成。

核心判斷

1. 可驗證性需要同時鎖住三層：主狀態表收尾檢查、嚴格附件單項章節、下一分類入口。
2. `tests/test_hcs_plus_state.py` 能證明 26 個第 2 輪批判思考單項都有 `核心判斷`、`落地修改`、`驗證方式` 與 `狀態：完成`。
3. 相關回歸仍需搭配 docs/frontend 契約測試，不能只看 HCS 狀態測試。

落地修改

1. 主狀態表新增 `第 2 輪批判思考完成：26/26`、`可重跑驗證` 與 `下一分類入口`。
2. `tests/test_hcs_plus_state.py` 新增 `test_hcs_plus_round2_critical_thinking_closing_checkpoint_is_recorded`。
3. 本嚴格輪巡附件新增「第 2 輪批判思考收尾」，並將下一步推進到第 2 輪 / 創意思考 / #學習科學。

優化說明

1. 將本輪批判思考從一連串矩陣文件收束成可驗證 checkpoint。
2. 明確保留 HCS Plus 尚未完成的事實：目前只是第 2 輪批判思考完成，完整流程還要繼續。
3. 剩餘風險是第 2 輪創意思考尚未開始，還未把矩陣轉成更好學的使用體驗。

驗證方式

- `tests/test_hcs_plus_state.py`
- `tests/test_docs_contract.py`
- `tests/test_static_history_filters.py`
- `tests/test_frontend_visual_optional.py`

## 第 2 輪批判思考收尾

- 已完成：26/26。
- 合理性結論：契約矩陣、反謬誤護欄與最小命令分組足以支撐下一分類，暫不新增自動選測腳本。
- 可驗證性結論：第 2 輪批判思考 26 個單項都已在本附件留下完成章節，並由 `tests/test_hcs_plus_state.py` 鎖住。
- 下一步：第 2 輪 / 創意思考 / #學習科學。

## 第 2 輪創意思考第一批

### 第 2 輪 / 創意思考 / #學習科學

狀態：完成

本次使用：把上一批的契約矩陣轉成更容易第一次使用的學習入口，降低操作者需要同時讀多張表的負擔。

核心判斷

1. 第 2 輪批判思考已完成矩陣與命令分組，但新操作者仍可能不知道先看哪裡。
2. 最適合的學習入口不是新增更多表，而是把判斷順序壓成「先問三題」。
3. 速學卡應保留原矩陣的風險邊界，不把學習便利性包裝成語意安全保證。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣速學卡`。
2. 速學卡新增 `先問三題`，分別對應機器契約、混合層報告呈現與前端顯示層。
3. `docs/hcs-plus-optimization-state.md` 新增第 2 輪創意思考速學卡設計 checkpoint。

優化說明

1. 解決契約矩陣可驗證但不好學的問題。
2. 犧牲的是文件多一段重述；換來操作者可以先用三題決定測試路徑。
3. 剩餘風險是速學卡仍是文件型態，尚未變成互動式選測流程。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少速學卡與創意思考第一批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 創意思考 / #限制條件

狀態：完成

本次使用：在改善學習成本時保留明確限制，避免把仍需人工判斷的契約層級包成假自動化。

核心判斷

1. 契約矩陣目前最重要的限制條件是：不新增自動選測腳本。
2. 這個限制不是保守拖延，而是承認高顯著性、混合層、顯示層改動仍需人先判斷。
3. 本批最小可逆修改是文件速學卡與測試契約，不改 runtime、不改 parser、不改 prompt。

落地修改

1. `docs/pipeline-mode-contract.md` 明確寫入 `不新增自動選測腳本`。
2. `docs/hcs-plus-optimization-state.md` 新增 D48，記錄三題判斷與三道安檢通道的限制。
3. 主狀態表把第 2 輪創意思考第一批標成完成，下一批才進入演算法化思考。

優化說明

1. 讓創意思考不只追求新穎，也保留工程邊界。
2. 避免操作者誤以為速學卡會自動判斷所有契約風險。
3. 剩餘風險是未來若真的新增選測腳本，必須回頭更新本限制與驗證矩陣。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_quick_learning_card`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_creative_learning_constraint_analogy_is_recorded`

### 第 2 輪 / 創意思考 / #類比

狀態：完成

本次使用：用三道安檢通道類比契約矩陣，讓操作者先分流風險，再執行最小測試命令。

核心判斷

1. 高顯著性機器契約、混合層報告呈現、低顯著性顯示層很像三種安檢通道，通道不同，檢查項目也不同。
2. 類比能降低記憶負擔，但不能取代矩陣裡的推論邊界與測試詮釋。
3. 最好的落地方式是把三個通道直接放在契約文件，讓改檔前可以就地查看。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `高顯著性機器契約通道`、`混合層報告呈現通道`、`低顯著性顯示層通道`。
2. 每個通道都列出進入條件、最小測試命令與判讀方式。
3. 本嚴格輪巡附件將下一步推進到第 2 輪 / 創意思考 / #演算法。
4. 歷史 checkpoint：下一步：第 2 輪 / 創意思考 / #演算法。

優化說明

1. 把抽象風險矩陣變成可掃讀的操作通道。
2. 保留「不得解讀為所有生成報告語意安全」等判讀限制。
3. 剩餘風險是三通道仍需人手選擇，下一批可檢查是否要把它表述成更明確的演算法。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪創意思考第二批

### 第 2 輪 / 創意思考 / #演算法

狀態：完成

本次使用：把速學卡轉成可以照順序執行的操作流程，避免操作者只知道三個通道，卻不知道改檔前要先做哪一步。

核心判斷

1. 速學卡已降低記憶負擔，但仍缺少「從改動描述到測試命令」的固定順序。
2. 最小演算法不是自動選測腳本，而是四步人工流程：定位改動層級、選擇通道、執行測試、記錄判讀。
3. 若改動跨層，流程必須要求跑多組命令，不能把複合風險硬塞進單一通道。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣操作流程`。
2. 操作流程新增 `四步演算法`，列出定位、選通道、跑測試、記錄限制。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪創意思考契約矩陣操作流程設計」。

優化說明

1. 讓契約矩陣從速學卡推進到可重複執行的改檔前流程。
2. 犧牲的是仍需人工判斷；換來不把契約層級責任藏進工具。
3. 剩餘風險是尚未觀察這套流程是否真的降低錯選測試的比例。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少操作流程與第二批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 創意思考 / #設計思考

狀態：完成

本次使用：把操作流程對齊實際操作者情境，讓文件不是抽象分類，而是能支援改 parser、改報告模板、改前端文案三種常見工作。

核心判斷

1. 操作者通常不是先想到「高/中/低顯著性」，而是先知道自己正在改哪個檔案或哪類文案。
2. 三個高頻情境是 parser/prompt/decision heading、完整報告模板或正文標題、純前端顯示文案。
3. 情境設計必須保留交叉情境：若同一改動跨 parser 與前端，不能只跑低顯著性顯示層測試。

落地修改

1. `docs/pipeline-mode-contract.md` 在操作流程中新增 `三個操作者情境` 表格。
2. 三個情境分別對應高顯著性機器契約通道、混合層報告呈現通道、低顯著性顯示層通道。
3. 主狀態表新增第二批設計說明，說明情境設計的驗證邊界。

優化說明

1. 讓文件用操作者實際改檔情境切入，而不是只要求理解內部矩陣術語。
2. 保留「跨層改動跑多組測試」的邊界。
3. 剩餘風險是目前情境只覆蓋最常見三類，未來新增報告輸出路徑時需擴充。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_operation_flow`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_creative_algorithm_design_heuristic_is_recorded`

### 第 2 輪 / 創意思考 / #捷思法

狀態：完成

本次使用：把第一次判斷壓縮成三條快速規則，讓操作者在改檔前能用最短時間初篩測試通道。

核心判斷

1. 契約詞括號、使用者可見報告正文、純前端顯示層，是最容易快速辨識的三種線索。
2. 捷思規則只能做初篩，不能保證語意安全，也不能取代矩陣判讀。
3. 規則必須說清楚「才走低顯著性」的條件，避免前端測試被誤用來支持 parser/prompt 改動。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `三條捷思規則`。
2. 規則分別標出括號契約詞走高顯著性、使用者會直接閱讀的報告正文先走混合層、純前端且不被 parser 讀取才走低顯著性。
3. 本嚴格輪巡附件將下一步推進到第 2 輪 / 創意思考 / #最佳化。
4. 歷史 checkpoint：下一步：第 2 輪 / 創意思考 / #最佳化。

優化說明

1. 讓速學卡與操作流程多一層快速入口。
2. 避免捷思法變成偷懶規則；文件仍保留完整通道與測試命令。
3. 剩餘風險是尚未有資料顯示這些規則會減少錯選命令，下一批可用最佳化與假說發展處理。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪創意思考第三批

### 第 2 輪 / 創意思考 / #最佳化

狀態：完成

本次使用：把契約矩陣操作流程的最佳化目標從「文件更完整」收斂為「改檔前更不容易選錯測試命令」。

核心判斷

1. 目前最大摩擦不是命令不存在，而是操作者可能選錯通道或跨層改動漏跑命令。
2. 最小最佳化不是新增腳本，而是明確定義三個人工 review 目標：降低錯選、減少漏跑、保留人工判斷責任。
3. 若沒有採用觀測訊號，文件再完整也難判斷是否真的改善流程。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣採用觀測板`。
2. 觀測板新增 `最佳化目標`，列出降低錯選測試命令、減少跨層改動漏跑測試、保留人工判斷責任。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪創意思考契約矩陣採用觀測設計」。

優化說明

1. 把文件最佳化聚焦到改檔前選測流程，而不是擴張成新工具。
2. 明確保留不新增遙測或自動化蒐集的限制。
3. 剩餘風險是採用效果仍需未來真實變更案例觀察。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少採用觀測板與第三批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 創意思考 / #假說發展

狀態：完成

本次使用：把「這套流程會更好用」拆成可被未來變更紀錄支持或反證的假說。

核心判斷

1. 若只說流程更清楚，缺少可反證性；需要寫出什麼現象代表有效，什麼現象代表仍失敗。
2. 三個最有用的假說分別對應四步流程、三個操作者情境、三條捷思規則。
3. 每個假說都要有反證訊號，避免只收集支持性例子。

落地修改

1. `docs/pipeline-mode-contract.md` 的觀測板新增 `可觀察假說` 表格。
2. 表格列出假說 1、假說 2、假說 3，並寫出預期訊號與反證訊號。
3. 主狀態表 D50 記錄本批用假說與訊號檢查流程採用效果。

優化說明

1. 讓後續 HCS 批次可以用案例檢查假說，而不是只繼續堆文件。
2. 犧牲的是當前尚無真實樣本統計；換來下一批能進入建模與抽樣。
3. 剩餘風險是假說仍是定性觀察，尚未量化成 CI gate。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_adoption_observation_board`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_creative_optimization_hypothesis_visualization_is_recorded`

### 第 2 輪 / 創意思考 / #資料視覺化

狀態：完成

本次使用：把採用訊號做成可掃讀矩陣，讓 review 時一眼看出通道選擇、測試判讀與後續行動落在哪個狀態。

核心判斷

1. 對文件型流程而言，最輕量的資料視覺化是表格矩陣，而不是新 dashboard。
2. 綠色、黃色、紅色三欄能把採用狀態壓成可掃讀判斷，並保留人工 review 語境。
3. 視覺化必須說明它不新增遙測或自動化蒐集，避免被誤解成監控功能已完成。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `採用訊號矩陣`。
2. 矩陣用 `綠色`、`黃色`、`紅色` 三欄呈現通道選擇、測試判讀與後續行動。
3. 本嚴格輪巡附件將下一步推進到第 2 輪 / 創意思考 / #建模。
4. 歷史 checkpoint：下一步：第 2 輪 / 創意思考 / #建模。

優化說明

1. 讓採用情況從散文說明變成可掃讀矩陣。
2. 保留文件契約的小範圍改動，不新增前端或後端功能。
3. 剩餘風險是矩陣還未連到實際案例；下一批可用建模、抽樣、個案研究補上。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪創意思考第四批

### 第 2 輪 / 創意思考 / #建模

狀態：完成

本次使用：把採用觀測板轉成可對照的案例模型，讓操作者能把當次改動映射到具體風險型態。

核心判斷

1. 採用觀測板指出綠/黃/紅訊號，但還需要模型來回答「這次改動像哪一類案例」。
2. 三個最小模型應對應既有三條通道：高顯著性機器契約、混合層報告呈現、低顯著性顯示層。
3. 模型只服務改檔前判斷，不應被解讀為涵蓋所有未來資料流。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣案例模型`。
2. 案例模型表新增 `模型 A：高顯著性機器契約案例`、`模型 B：混合層報告呈現案例`、`模型 C：低顯著性顯示層案例`。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪創意思考契約矩陣案例模型設計」。

優化說明

1. 讓抽象通道變成可引用的模型，方便 review 時要求改動者對照。
2. 保留模型邊界，不宣稱三類模型可覆蓋所有未來系統變更。
3. 剩餘風險是模型尚未和真實變更樣本比較，下一批可用比較組處理。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少案例模型與第四批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 創意思考 / #抽樣

狀態：完成

本次使用：定義代表性抽樣規則，避免用單一順利案例外推成整個契約矩陣已被驗證。

核心判斷

1. 每次契約相關變更至少要對照一個案例模型，否則採用觀測板容易停在抽象判讀。
2. 跨層改動必須同時抽樣兩個模型，因為單一通道測試不足以代表複合風險。
3. 單一綠燈案例只能支持當次改動，不能代表未來所有改動。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `代表性抽樣規則`。
2. 抽樣規則要求每次契約相關變更至少對照一個案例模型。
3. 抽樣規則明示跨層改動同時抽樣兩個模型，並不得以單一綠燈案例代表所有未來改動。

優化說明

1. 把採用觀測從「看訊號」推進到「選代表樣本」。
2. 避免幸存者偏誤：不能只記錄最容易通過的低風險案例。
3. 剩餘風險是抽樣規則目前仍是人工文件要求，尚未成為 PR template 或 CI gate。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_case_model`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_creative_modeling_sampling_case_study_is_recorded`

### 第 2 輪 / 創意思考 / #個案研究

狀態：完成

本次使用：建立案例卡格式，讓後續每次契約改動可以留下可比較、可審查的個案紀錄。

核心判斷

1. 模型與抽樣規則仍需要一個固定欄位格式，否則每次 review 記錄會不一致。
2. 最小案例卡應包含改動描述、選擇通道、必跑命令與採用訊號。
3. 案例卡證明當次有被檢查，不證明歷史報告或未來輸出都安全。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `案例卡格式`。
2. 案例卡要求記錄 `改動描述`、`選擇通道`、`必跑命令`、`採用訊號`。
3. 本嚴格輪巡附件將下一步推進到第 2 輪 / 創意思考 / #比較組。
4. 歷史 checkpoint：下一步：第 2 輪 / 創意思考 / #比較組。

優化說明

1. 讓後續契約改動可以留下同構案例，而不是散落在不同 PR 描述裡。
2. 保留文件型態，不新增新工具或模板檔。
3. 剩餘風險是尚未比較有無案例卡時的選測品質差異，下一批可處理比較組與介入研究。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪創意思考第五批

### 第 2 輪 / 創意思考 / #比較組

狀態：完成

本次使用：把案例模型採用效果拆成基準組與介入組，讓後續 review 可以比較「只看流程」與「加案例卡」的差異。

核心判斷

1. 目前文件已有速學卡、操作流程、案例模型，但尚未定義如何比較案例模型是否真的改善選測品質。
2. 最小比較組是基準組只使用速學卡與操作流程，介入組加上案例模型與案例卡。
3. 比較指標需要聚焦錯選通道、漏跑命令、判讀限制缺漏，而不是泛稱使用者覺得更清楚。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣比較與回饋設計`。
2. 新增 `比較組設計`，列出基準組與介入組。
3. 新增 `比較指標`，鎖定錯選通道、漏跑命令與判讀限制缺漏。

優化說明

1. 讓案例模型的價值可以被人工比較，而不是只停在文件完整度。
2. 保留限制：比較組是 review 方法，不是統計實驗。
3. 剩餘風險是尚未觀察真實改動案例，下一批需進入觀察研究。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少比較與回饋設計、第五批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 創意思考 / #介入研究

狀態：完成

本次使用：定義低成本介入，讓操作者在改檔前先填案例卡，降低漏跑測試與判讀限制缺漏。

核心判斷

1. 介入不應是新增工具，而是把「先填案例卡」放到改檔前流程中。
2. 跨層改動是最容易漏跑命令的情境，因此要強制列出兩個模型與兩組命令。
3. 黃色或紅色採用訊號需要有回退路徑，回到比較指標補齊通道、命令或判讀限制。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `介入方案`。
2. 介入方案要求改檔前先填案例卡。
3. 介入方案要求跨層改動強制列出兩個模型，並在黃/紅訊號時回到比較指標修正。

優化說明

1. 把案例卡從靜態格式推進成改檔前介入。
2. 不新增產品遙測或自動化蒐集，維持目前文件契約範圍。
3. 剩餘風險是介入效果尚未用真實操作者回饋驗證。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_comparison_feedback_design`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_creative_comparison_intervention_survey_is_recorded`

### 第 2 輪 / 創意思考 / #訪談調查

狀態：完成

本次使用：把採用感受轉成三個低成本回饋題，避免只用作者自己的判斷推論流程好用。

核心判斷

1. 操作者能否在 2 分鐘內選出通道，是最直接的可用性回饋。
2. 哪一條規則讓人猶豫，可以暴露速學卡、捷思法或案例模型仍不清楚的地方。
3. 案例卡是否幫忙發現漏跑命令或判讀限制，是介入是否有效的具體回饋。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `訪談回饋題`。
2. 訪談回饋題包含 2 分鐘選通道、猶豫規則、案例卡是否發現漏跑/判讀限制。
3. 本嚴格輪巡附件將下一步推進到第 2 輪 / 創意思考 / #觀察研究。
4. 歷史 checkpoint：下一步：第 2 輪 / 創意思考 / #觀察研究。

優化說明

1. 讓下一批觀察研究可以蒐集具體回饋，而不是空泛詢問是否滿意。
2. 明確註記訪談回覆不能替代 pytest 或契約測試。
3. 剩餘風險是目前尚未收集真實回饋，下一批再處理觀察與複製。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪創意思考第六批

### 第 2 輪 / 創意思考 / #觀察研究

狀態：完成

本次使用：把比較與回饋設計轉成實際觀察欄位，讓後續每次契約變更可以留下可檢查紀錄。

核心判斷

1. 若沒有固定觀察欄位，訪談與案例卡容易只留下散文心得，無法支援後續複製。
2. 最小觀察欄位應包含變更案例、實際選擇通道、實際執行命令與觀察結果。
3. 觀察紀錄不能變成測試替代品；它只輔助判斷流程是否被正確使用。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣觀察與複製準則`。
2. 準則新增 `觀察記錄欄位`，要求記錄 `變更案例`、`實際選擇通道`、`實際執行命令`、`觀察結果`。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪創意思考契約矩陣觀察複製設計」。

優化說明

1. 讓契約矩陣採用效果有可觀察紀錄，而不是只看測試是否通過。
2. 保留邊界：不新增產品遙測或自動化蒐集。
3. 剩餘風險是觀察欄位尚未被真實 PR 使用，下一輪溝通思考需讓操作者更容易理解。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少觀察/複製準則與第六批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 創意思考 / #研究複製

狀態：完成

本次使用：定義下一位操作者如何複製同一套契約矩陣判斷，而不必閱讀完整 HCS 附件。

核心判斷

1. 可複製的重點是同一案例模型、同一必跑命令、同一判讀限制。
2. 下一位操作者應能只看 `docs/pipeline-mode-contract.md`，找到通道、模型、命令與判讀限制。
3. 研究複製不代表所有未來輸出都安全；它只證明流程可以被重複套用。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `複製檢查清單`。
2. `docs/pipeline-mode-contract.md` 新增 `可複製完成條件`，明確要求下一位操作者不用讀完整 HCS 附件也能套用流程。
3. 主狀態表與嚴格附件新增第 2 輪創意思考 17/17 收尾，下一步推進到第 2 輪 / 溝通思考 / #受眾。

優化說明

1. 將第 2 輪創意思考從學習、流程、採用、案例、比較與觀察收束成可複製契約。
2. 明確保留 HCS Plus 尚未完成：目前只是第 2 輪創意思考完成，完整流程還要繼續。
3. 剩餘風險是契約矩陣語言仍偏流程導向，下一批需用溝通思考改善受眾、組成與語意。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`
- `tests/test_static_history_filters.py`
- `tests/test_frontend_visual_optional.py`

## 第 2 輪創意思考收尾

- 已完成：17/17。
- 收尾結論：第 2 輪創意思考已把契約矩陣從批判性測試矩陣，推進成可學、可操作、可觀測、可建模、可比較、可觀察、可複製的文件契約。
- 可驗證性結論：第 2 輪創意思考 17 個單項都已在本附件留下完成章節，並由 `tests/test_hcs_plus_state.py` 鎖住。
- 下一步：第 2 輪 / 溝通思考 / #受眾。

## 第 2 輪溝通思考第一批

### 第 2 輪 / 溝通思考 / #受眾

狀態：完成

本次使用：把契約矩陣文件從單一流程文件，改成三種維護者都能找到自己入口的讀者路徑。

核心判斷

1. 一般改文案者最容易誤以為低顯著性文案變更沒有責任邊界。
2. 報告模板維護者需要先判斷自己是否處在混合層，而不是只看 template 測試是否通過。
3. parser/prompt 維護者需要先看到高顯著性機器契約風險，避免把文件通道誤讀成自動化保證。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣讀者路徑`。
2. 讀者路徑新增 `三種受眾` 表格：一般改文案者、報告模板維護者、parser/prompt 維護者。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪溝通思考契約矩陣讀者路徑設計」。

優化說明

1. 讓不同維護者不用先讀完整 HCS 附件，也能找到契約矩陣入口。
2. 犧牲的是文件更長一點；換來更低的誤用與漏讀機率。
3. 剩餘風險是章節排序仍可能偏長，下一批用組織結構與論點再收斂。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少讀者路徑與第 2 輪溝通思考紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 溝通思考 / #組成

狀態：完成

本次使用：把讀者路徑的組成從材料清單改成可執行的閱讀順序，讓操作者知道先判斷、再執行、最後紀錄。

核心判斷

1. 契約矩陣已有速學卡、操作流程、案例模型與觀察準則，但缺少明確順序。
2. 最小清楚順序是先讀速學卡、再用操作流程、最後填案例卡。
3. 組成順序必須保留測試矩陣與必跑命令，不可把文件閱讀本身當成驗證。

落地修改

1. `docs/pipeline-mode-contract.md` 在 `契約矩陣讀者路徑` 中新增 `閱讀順序`。
2. 閱讀順序明確寫出 `先讀速學卡`、`再用操作流程`、`最後填案例卡`。
3. 主狀態表記錄本批把受眾、組成與語意含義合併成一個文件契約 patch。

優化說明

1. 讓文件從「有哪些材料」變成「如何走完一次契約判斷」。
2. 不新增自動選測工具，維持人工判斷與測試命令的責任邊界。
3. 剩餘風險是案例卡尚未被實際 PR 使用，後續仍需觀察真實採用訊號。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_reader_path`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_communication_audience_composition_semantics_is_recorded`

### 第 2 輪 / 溝通思考 / #語意含義

狀態：完成

本次使用：限制讀者對文件契約的推論範圍，避免把文件、觀察紀錄或低顯著性標籤誤解成安全保證。

核心判斷

1. 文件契約不是自動化保證；它只能要求操作者先做人工判斷並執行對應測試。
2. 觀察紀錄不是測試替代品；它記錄流程使用方式，不證明 parser、prompt 或報告模板安全。
3. 低顯著性不代表低責任；純前端顯示文案仍可能影響使用者是否把報告看成交易指令。

落地修改

1. `docs/pipeline-mode-contract.md` 在讀者路徑中新增 `語意邊界`。
2. 語意邊界列出文件契約、觀察紀錄與低顯著性的三個不得誤讀。
3. 嚴格輪巡進度將下一批推進到第 2 輪 / 溝通思考 / #組織結構。
4. 歷史 checkpoint：下一步：第 2 輪 / 溝通思考 / #組織結構。

優化說明

1. 把契約矩陣的溝通風險從「看不懂」推進到「不容易誤解」。
2. 明確保留 HCS Plus 尚未完成：目前只是第 2 輪溝通思考前三個單項完成。
3. 剩餘風險是整份契約仍需要更好的章節排序與核心論點，下一批繼續處理。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪溝通思考第二批

### 第 2 輪 / 溝通思考 / #組織結構

狀態：完成

本次使用：把契約矩陣文件的多個章節整理成可遵循的維護順序，降低讀者在速學卡、案例模型與模式對照之間來回迷路的機率。

核心判斷

1. 讀者路徑已經分出受眾，但整份文件仍需要一條跨章節的導覽。
2. 最小可用組織是先判斷改動層級、再選案例模型、最後確認模式對照。
3. 章節導覽不能改變測試矩陣本身，只能讓維護者更快走到正確章節。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣維護導覽`。
2. 維護導覽新增 `章節導覽` 表格，排列先判斷改動層級、再選案例模型、最後確認模式對照。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪溝通思考契約矩陣維護導覽設計」。

優化說明

1. 把契約矩陣從材料集合整理成維護流程。
2. 犧牲的是文件多一個導覽段落；換來後續維護者更容易引用。
3. 剩餘風險是目前仍以文字和表格為主，下一批再評估溝通媒介是否足夠。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少維護導覽與第二批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 溝通思考 / #專業性

狀態：完成

本次使用：把契約文件的完成敘述限制在專業、可證明的範圍內，避免把測試綠燈包裝成過度安全宣稱。

核心判斷

1. 測試綠燈只能說明已知契約未回退，不應宣稱投資語意安全或使用者一定理解。
2. 跨層改動需要列出多組命令，並說清楚各自保護的契約面。
3. 文件或觀察紀錄只能證明維護判斷已被記錄，不能證明 runtime 行為。

落地修改

1. `docs/pipeline-mode-contract.md` 在維護導覽中新增 `專業維護語氣`。
2. 專業維護語氣明確寫出只證明已知契約未回退、不得宣稱投資語意安全、跨層改動需列出多組命令。
3. 主狀態表 D55 記錄此批把維護導覽收斂成可引用的專業規範。

優化說明

1. 降低文件把測試結果誇大成使用者語意安全的風險。
2. 保留人工責任：跨層改動仍要由維護者列明命令與判讀限制。
3. 剩餘風險是專業語氣仍需在真實 PR 描述中被採用。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_maintenance_guide`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_communication_structure_professional_claim_is_recorded`

### 第 2 輪 / 溝通思考 / #論點

狀態：完成

本次使用：把維護導覽的核心主張寫清楚，讓後續改動不把契約矩陣理解成自動選測工具。

核心判斷

1. 契約矩陣的核心論點是人工判斷先行，再用最小測試驗證。
2. 碰到 parser/prompt/template 時，應優先視為契約變更，再判斷是否跨報告呈現或前端顯示。
3. 低顯著性前端通道仍需維持報告層級語氣，不可把報告建議寫成即時交易指令。

落地修改

1. `docs/pipeline-mode-contract.md` 在維護導覽中新增 `核心論點`。
2. 核心論點寫明契約矩陣的目的不是自動化選測，而是先保留人工判斷，再用最小測試驗證。
3. 嚴格輪巡進度將下一批推進到第 2 輪 / 溝通思考 / #溝通設計。
4. 歷史 checkpoint：下一步：第 2 輪 / 溝通思考 / #溝通設計。

優化說明

1. 讓維護者可以引用一段清楚主張，而不是只引用零散表格。
2. 明確保留 HCS Plus 尚未完成：目前只是第 2 輪溝通思考六個單項完成。
3. 剩餘風險是最後四個溝通單項尚未處理文件呈現形式與媒介取捨。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪溝通思考第三批

### 第 2 輪 / 溝通思考 / #溝通設計

狀態：完成

本次使用：把完整契約矩陣設計成可快速引用的一頁摘要，讓維護者在改檔前能先用三步完成初判。

核心判斷

1. 維護導覽適合完整閱讀，但改檔前仍需要更短的入口。
2. 三步短版摘要可涵蓋高顯著性、混合層與低顯著性三種通道。
3. 一頁摘要必須指回完整契約矩陣，不能取代案例模型、測試命令與限制判讀。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣一頁摘要`。
2. 一頁摘要新增 `短版摘要`，包含先看 parser/prompt/template、再看使用者是否直接閱讀、最後看是否只在前端顯示。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪溝通思考契約矩陣摘要與媒介設計」。

優化說明

1. 讓操作者可先用短版摘要進入契約矩陣，而不是在多張表之間尋找入口。
2. 保留完整章節作為詳細判斷來源。
3. 剩餘風險是短版摘要可能被過度簡化使用，因此同節保留不得解讀為的句型。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少一頁摘要與溝通思考收尾會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 溝通思考 / #表達

狀態：完成

本次使用：把維護者回報方式寫成固定句型，降低只貼測試通過、未說明通道與限制的風險。

核心判斷

1. 回報需要同時說明選擇的通道、已執行命令與不得解讀為。
2. 固定句型比散文提醒更容易在 PR、HCS 狀態或變更紀錄中複製。
3. 表達句型不能替代測試證據，只能讓證據與限制更清楚。

落地修改

1. `docs/pipeline-mode-contract.md` 在一頁摘要中新增 `建議表達`。
2. 建議表達包含「我選擇的通道是」、「我已執行的命令是」、「不得解讀為」。
3. 主狀態表 D56 記錄一頁摘要與建議表達完成溝通思考收尾。

優化說明

1. 讓維護者更容易用同一套語句回報契約判斷。
2. 降低測試結果被誇大成投資語意安全的機率。
3. 剩餘風險是句型仍需在實際變更中被採用，後續互動思考會檢查倫理邊界。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_one_page_summary`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_communication_design_expression_media_closing_is_recorded`

### 第 2 輪 / 溝通思考 / #媒介

狀態：完成

本次使用：決定契約矩陣目前應以文字與表格作為主要媒介，優先支援複製判斷、命令與限制。

核心判斷

1. 契約矩陣是維護文件，不是產品儀表板。
2. 文字與表格更適合保留命令、限制與不得解讀為的精確語句。
3. 若改成圖像優先，可能讓操作者跳過文字限制或忽略測試命令。

落地修改

1. `docs/pipeline-mode-contract.md` 在一頁摘要中新增 `媒介取捨`。
2. 媒介取捨明確採用文字與表格優先。
3. 主狀態表記錄媒介選擇的驗證邊界：適用本文件，不禁止未來產品 UI 另行設計。

優化說明

1. 讓文件媒介服務維護任務，而不是為了視覺化而視覺化。
2. 保留未來產品 UI 設計空間，但不在本輪加入。
3. 剩餘風險是文字表格仍可能偏長，後續可用實際採用紀錄再評估。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 2 輪 / 溝通思考 / #多媒體

狀態：完成

本次使用：明確記錄本輪不新增圖像或多媒體，避免把人工判斷包裝成看似自動化的流程圖。

核心判斷

1. 多媒體若只把三通道畫成流程圖，可能強化「自動選測」錯覺。
2. 本文件最重要的是限制條件、命令與不得解讀為，文字不可被圖像取代。
3. 未來若新增圖像，仍必須保留文字版通道、命令與限制。

落地修改

1. `docs/pipeline-mode-contract.md` 的 `媒介取捨` 明確寫出暫不新增圖像或多媒體。
2. 同段寫明避免圖像把人工判斷包成自動流程。
3. 主狀態表與嚴格附件新增第 2 輪溝通思考 10/10 收尾，下一步推進到第 2 輪 / 互動思考 / #倫理考量。

優化說明

1. 把溝通思考從「補更多形式」收斂為「用最適合的形式承載限制」。
2. 明確保留 HCS Plus 尚未完成：目前只是第 2 輪溝通思考完成，仍需第 2 輪互動思考、第 3 輪與綜合優化。
3. 剩餘風險是契約矩陣的倫理宣稱邊界尚未被第 2 輪互動思考檢查。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`
- `tests/test_static_history_filters.py`
- `tests/test_frontend_visual_optional.py`

## 第 2 輪溝通思考收尾

- 已完成：10/10。
- 收尾結論：第 2 輪溝通思考已把契約矩陣轉成分受眾、可導覽、可短版引用、可固定表達且媒介取捨清楚的維護文件。
- 可驗證性結論：第 2 輪溝通思考 10 個單項都已在本附件留下完成章節，並由 `tests/test_hcs_plus_state.py` 鎖住。
- 下一步：第 2 輪 / 互動思考 / #倫理考量。

## 第 2 輪互動思考第一批

### 第 2 輪 / 互動思考 / #倫理考量

狀態：完成

本次使用：把契約矩陣的測試、文件與低顯著性通道加上倫理底線，避免維護者把有限證據包裝成投資或語意安全。

核心判斷

1. 測試綠燈只證明指定契約未回退，不代表投資建議安全。
2. 契約矩陣是維護者判斷工具，不是可以承擔責任的主體。
3. 低顯著性通道仍可能影響使用者如何理解報告文案，不能被用來淡化使用者風險。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣倫理邊界`。
2. 倫理邊界新增 `倫理底線`，明確禁止把測試綠燈寫成投資建議安全、把責任轉嫁給工具或文件、用低顯著性通道淡化使用者風險。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪互動思考契約矩陣倫理邊界設計」。

優化說明

1. 把溝通思考的「不得解讀為」推進到互動層面的責任邊界。
2. 犧牲的是文件多一段倫理規範；換來更低的過度安全宣稱風險。
3. 剩餘風險是局部測試與整體系統行為的因果關係仍需下一批處理。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少倫理邊界與互動思考第一批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 互動思考 / #倫理勇氣

狀態：完成

本次使用：把「必要時要說不」寫成可引用的阻擋條件，讓維護者在證據不足時能暫停高風險改動。

核心判斷

1. 缺少 parser/prompt/template 證據時，不能用文件通道替代高顯著性驗證。
2. 報告文案若可能被讀成交易指令，應先補責任邊界，而不是用低顯著性通道快速放行。
3. 跨層改動只跑單一命令時，應要求補跑或拆分改動。

落地修改

1. `docs/pipeline-mode-contract.md` 在倫理邊界新增 `必要時要說不`。
2. 說不條件包含缺少 parser/prompt/template 證據不可合併高顯著性改動。
3. 說不條件要求交易指令式報告文案先補責任邊界，跨層改動需補跑或拆分。

優化說明

1. 讓維護者有明確理由拒絕看似已通過、實際證據不足的改動。
2. 保留低風險改動的通道，不把所有改動都升級為阻擋。
3. 剩餘風險是阻擋條件仍需在真實 review 中被採用。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_ethics_boundary`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_interaction_ethics_courage_judgment_is_recorded`

### 第 2 輪 / 互動思考 / #倫理判斷

狀態：完成

本次使用：把允許發布與禁止發布的敘述分開，並定義何時要從低顯著性升級到混合層、從混合層升級到高顯著性。

核心判斷

1. 維護者需要知道哪些敘述可以發布，哪些敘述會誇大證據。
2. 升級條件要把使用者理解、parser/prompt/template 與 runtime 宣稱分開。
3. 文件判斷若被拿來宣稱實際執行行為，就必須升級為 runtime 驗證。

落地修改

1. `docs/pipeline-mode-contract.md` 在倫理邊界新增 `倫理判斷` 表格。
2. 倫理判斷表分開 `允許發布的敘述` 與 `禁止發布的敘述`。
3. 倫理邊界新增 `升級條件`，包含從低顯著性升級為混合層、從混合層升級為高顯著性、從文件判斷升級為 runtime 驗證。
4. 嚴格輪巡進度將下一批推進到第 2 輪 / 互動思考 / #複雜因果。
5. 歷史 checkpoint：下一步：第 2 輪 / 互動思考 / #複雜因果。

優化說明

1. 把倫理邊界轉成可審查的允許/禁止敘述，降低模糊判斷。
2. 明確保留 HCS Plus 尚未完成：目前只是第 2 輪互動思考前三項完成。
3. 剩餘風險是複雜因果與系統層級風險尚未處理，下一批會接續。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪互動思考第二批

### 第 2 輪 / 互動思考 / #複雜因果

狀態：完成

本次使用：把局部測試、文件紀錄與前端語氣改善可能造成的錯誤推論寫成因果圖譜，避免把單一綠燈擴張成整體安全。

核心判斷

1. parser/prompt/template 測試通過，仍可能留下使用者誤解或報告語氣風險。
2. 文件與觀察紀錄完整，可能降低漏跑測試，但不能保證真實採用。
3. 前端語氣改善不能保證完整報告正文、preview、儲存流程或使用者閱讀情境一致改善。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣系統風險邊界`。
2. 系統風險邊界新增 `複雜因果圖譜`，列出局部證據、錯誤推論與系統邊界。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪互動思考契約矩陣系統風險邊界設計」。

優化說明

1. 把倫理邊界從禁止誇大，推進到說清楚為什麼局部證據不能外推。
2. 保留現有測試矩陣價值，但限制它的可宣稱範圍。
3. 剩餘風險是系統關係尚未整理成維護網絡，下一批處理。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少系統風險邊界與第二批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 互動思考 / #湧現特性

狀態：完成

本次使用：記錄多個低風險改動累積後可能出現的新風險，避免只看單次改動顯著性。

核心判斷

1. 多個低顯著性改動可能累積成高風險，尤其是持續調整責任與報告建議語氣時。
2. 跨模式文案一致可能提高掃讀性，也可能模糊長線、交易與逆勢模式的責任差異。
3. 觀察紀錄增加可能讓維護者誤以為驗證已經足夠，反而減少實際測試。

落地修改

1. `docs/pipeline-mode-contract.md` 在系統風險邊界新增 `湧現風險`。
2. 湧現風險列出低顯著性累積、跨模式責任模糊、觀察紀錄替代實際驗證三種風險。
3. 主狀態表 D58 記錄本批把局部證據與系統風險分開。

優化說明

1. 讓契約矩陣不只處理單次改動，也提醒維護者看累積效果。
2. 不新增遙測或工具，先用文件契約降低誤讀風險。
3. 剩餘風險是湧現風險仍需未來真實變更案例來觀察。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_system_risk_boundary`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_interaction_complex_emergent_layers_is_recorded`

### 第 2 輪 / 互動思考 / #分析層次

狀態：完成

本次使用：把文件層、測試層、runtime 層與使用者行為層分開，要求每個宣稱都對齊自己的證據層級。

核心判斷

1. 文件層證據不能替代測試層或 runtime 層。
2. 測試層證據不能替代使用者行為層，也不能保證所有未測 runtime 路徑。
3. 使用者行為層需要真實操作者是否誤解、漏跑或過度採用報告建議的證據。

落地修改

1. `docs/pipeline-mode-contract.md` 在系統風險邊界新增 `分析層次` 表格。
2. 分析層次表區分 `文件層`、`測試層`、`runtime 層`、`使用者行為層`。
3. 同節新增不得用下一層證據替代上一層證據，也不得反向替代的規則。
4. 嚴格輪巡進度將下一批推進到第 2 輪 / 互動思考 / #網絡。
5. 歷史 checkpoint：下一步：第 2 輪 / 互動思考 / #網絡。

優化說明

1. 讓完成敘述必須說清楚證據層級，降低跨層誇大。
2. 明確保留 HCS Plus 尚未完成：目前只是第 2 輪互動思考六個單項完成。
3. 剩餘風險是尚未把層級關係整理成網絡與系統圖像。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪互動思考第三批

### 第 2 輪 / 互動思考 / #網絡

狀態：完成

本次使用：把契約矩陣涉及的前端、報告模板、parser/prompt、測試矩陣與使用者判讀整理成維護網絡。

核心判斷

1. 前端顯示層、報告模板層與 parser/prompt 層彼此互相影響，不能只看單一檔案類型。
2. 測試矩陣連接多個層級，但測試綠燈本身不能代表使用者判讀安全。
3. 使用者判讀受到前端文案、報告正文與倫理邊界共同影響。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣系統關係圖`。
2. 系統關係圖新增 `維護網絡` 表格，列出前端顯示層、報告模板層、parser/prompt 層、測試矩陣與使用者判讀。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪互動思考契約矩陣系統關係設計」。

優化說明

1. 讓維護者看到契約矩陣不是單張測試表，而是多層互動網絡。
2. 保留文字表格形式，避免新增不可測的圖像 artifact。
3. 剩餘風險是 review 對話如何引導維護者補證據尚未處理。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少系統關係圖與第三批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 互動思考 / #系統動力學

狀態：完成

本次使用：記錄契約矩陣的動態回路，避免單純加規則後忽略維護成本與形式化副作用。

核心判斷

1. 語氣改善會降低權威感，但若不同層不同步，可能增加契約漂移。
2. 更多觀察紀錄會降低漏跑測試，但也可能讓維護者形式化填寫而減少實際驗證。
3. 更嚴格升級條件會降低錯放高風險改動，但可能增加低風險變更的維護成本。

落地修改

1. `docs/pipeline-mode-contract.md` 在系統關係圖新增 `系統動力學`。
2. 系統動力學列出語氣改善、觀察紀錄、升級條件三個回路。
3. 主狀態表 D59 記錄本批把維護網絡與動態回路合併。

優化說明

1. 讓契約矩陣同時呈現風險降低與副作用。
2. 避免把「更多規則」誤認成單向改善。
3. 剩餘風險是目前尚未有真實 review 數據量化這些回路。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_system_relationship_map`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_interaction_network_dynamics_system_image_is_recorded`

### 第 2 輪 / 互動思考 / #系統圖像

狀態：完成

本次使用：把維護流程收斂成系統圖像：改動先定位層級、證據再對齊層次、宣稱最後受倫理邊界限制。

核心判斷

1. 若不先定位層級，維護者容易用錯通道。
2. 若證據不對齊層次，容易把文件、測試、runtime 或使用者行為證據互相替代。
3. 若宣稱不受倫理邊界限制，測試綠燈容易被說成投資語意安全。

落地修改

1. `docs/pipeline-mode-contract.md` 在系統關係圖新增 `系統圖像`。
2. 系統圖像明確寫出改動先定位層級、證據再對齊層次、宣稱最後受倫理邊界限制。
3. 嚴格輪巡進度將下一批推進到第 2 輪 / 互動思考 / #談判。
4. 歷史 checkpoint：下一步：第 2 輪 / 互動思考 / #談判。

優化說明

1. 把前面多個表格收斂成一條維護流程。
2. 明確保留 HCS Plus 尚未完成：目前只是第 2 輪互動思考九個單項完成。
3. 剩餘風險是這套流程尚未轉成 review 對話與行為引導。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪互動思考第四批

### 第 2 輪 / 互動思考 / #談判

狀態：完成

本次使用：把系統關係與倫理邊界轉成補證據協商，避免 review 只剩下「擋」或「放」兩種立場。

核心判斷

1. 缺證據的改動若直接被否決，容易讓維護者防衛；若直接通過，又會把風險推到使用者。
2. 比較好的談判順序是先承認改動目的，再指出缺少的證據層，最後提出最小補證據路徑。
3. 協商重點不是降低標準，而是把補跑測試、填案例卡或拆分改動變成可接受的下一步。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣 review 對話`。
2. review 對話新增 `補證據協商` 表格，明確寫出先承認改動目的、再指出缺少的證據層、最後提出最小補證據路徑。
3. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪互動思考契約矩陣 review 對話設計」。

優化說明

1. 讓 review 的談判語氣從立場對抗改成證據補齊。
2. 犧牲的是文件再增加一段維護規範；換來高風險改動更容易被拆成可驗證步驟。
3. 剩餘風險是團隊仍可能為了趕進度忽略協商句型，下一批需處理從眾與情緒壓力。

驗證方式

- RED：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少 review 對話與第四批紀錄會失敗。
- GREEN：`$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 互動思考 / #說服

狀態：完成

本次使用：把補跑命令、升級通道與拆分改動的理由說成共同降低風險，而不是 review 者單方面增加負擔。

核心判斷

1. 「請再跑測試」若沒有說明風險，很容易被聽成形式要求。
2. 「升級通道」若沒有說明保護對象，很容易被誤解成否定低風險改善。
3. 「拆分改動」若沒有說明成本，容易被看成重工，而不是降低 review 成本。

落地修改

1. `docs/pipeline-mode-contract.md` 的 review 對話新增 `說服原則`。
2. 說服原則要求把補跑命令說成降低錯放風險。
3. 說服原則要求把升級通道說成保護 parser/prompt/template，並把拆分改動說成降低 review 成本。

優化說明

1. 讓維護者知道要求補證據的理由，而不是只看到流程負擔。
2. 保留嚴格邊界：說服語氣不能把測試綠燈說成投資語意安全。
3. 剩餘風險是真實 review 中仍需有人主動引用這段原則。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_review_dialogue`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_interaction_negotiation_persuasion_behavior_is_recorded`

### 第 2 輪 / 互動思考 / #形塑行為

狀態：完成

本次使用：把 review 對話轉成預設行為，讓操作者自然留下通道、命令、案例卡與採用訊號限制。

核心判斷

1. 只有規則不夠；若沒有預設格式，操作者仍可能忘記寫通道、命令與不得解讀為。
2. 跨層改動最容易漏掉案例卡，因此應預設先填案例卡再合併。
3. 紅色或黃色採用訊號若被合併成綠燈，會讓契約矩陣失去警示作用。

落地修改

1. `docs/pipeline-mode-contract.md` 的 review 對話新增 `形塑行為`。
2. 形塑行為要求預設使用一頁摘要句型，跨層改動預設填案例卡。
3. 形塑行為明確規定紅色或黃色採用訊號不得合併。
4. 歷史 checkpoint：下一步：第 2 輪 / 互動思考 / #從眾。

優化說明

1. 把前面的一頁摘要、案例模型與採用觀測板串成 review 預設。
2. 這不新增自動化審核器，仍保留人工判斷與測試命令。
3. 下一批需檢查預設行為是否會造成從眾、忽略差異，或在高壓情境下被情緒化採用。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪互動思考第五批

### 第 2 輪 / 互動思考 / #從眾

狀態：完成

本次使用：檢查 review 對話是否可能讓操作者因多數同意、前例綠燈或測試全綠而省略證據層判斷。

核心判斷

1. 契約矩陣越完整，越容易被當成「大家都同意就安全」的社會證明。
2. 前例綠燈只能證明前一次改動，不代表本次改動層級相同。
3. 測試全綠如果沒有不得解讀為，仍可能被團隊誤說成語意或使用者行為安全。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣 review 防從眾檢查`。
2. 防從眾檢查明確寫出不得用多數人同意取代證據層。
3. 防從眾檢查明確寫出不得用前例綠燈取代本次改動層級，且不得用測試全綠取代不得解讀為。

優化說明

1. 讓 review 對話在降低摩擦後，仍保留對群體壓力的抵抗力。
2. 犧牲的是文件多一道檢查；換來高風險合併不會被社會認同感稀釋。
3. 剩餘風險是實際 review 仍需有人願意引用這段檢查。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少防從眾檢查與第五批紀錄會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 互動思考 / #差異

狀態：完成

本次使用：避免契約矩陣因格式一致而壓扁高顯著性、混合層、低顯著性，以及不同 pipeline 模式的責任差異。

核心判斷

1. 通道名稱相鄰出現在同一張矩陣時，操作者可能把不同風險合併成一段完成敘述。
2. 長線、交易、逆勢、短線模式的決策用途不同，不能只因報告格式一致就共用同一種責任語氣。
3. 文件層、測試層、runtime 層與使用者行為層若被合併回報，會模糊哪一層已驗證。

落地修改

1. `docs/pipeline-mode-contract.md` 在 review 防從眾檢查中新增 `差異保留`。
2. 差異保留要求高顯著性、混合層、低顯著性不得合併敘述。
3. 差異保留要求不同 pipeline 模式與不同證據層分開回報。

優化說明

1. 讓操作者在追求掃讀性時，不會把責任邊界壓成同一種語氣。
2. 保留了既有矩陣格式，但補上防止格式誤導的語意護欄。
3. 剩餘風險是差異保留仍需要下一批處理誰負責維持。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_review_conformity_guard`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_interaction_conformity_difference_emotion_is_recorded`

### 第 2 輪 / 互動思考 / #情緒智商

狀態：完成

本次使用：把高壓 review 的情緒處理寫成順序，避免時程、失敗或疲勞把限制句擠掉。

核心判斷

1. 高壓合併時，操作者常不是不知道規則，而是想快速結束不舒服的 review。
2. 直接要求全面返工會放大壓力，反而讓人更想略過契約矩陣。
3. 較好的情緒順序是先命名壓力，再回到最小補證據路徑，最後用限制句收尾。

落地修改

1. `docs/pipeline-mode-contract.md` 在 review 防從眾檢查中新增 `情緒智商`。
2. 情緒智商要求先命名壓力，例如時程、回歸失敗或 review 疲勞。
3. 情緒智商要求回到最小補證據路徑，最後用限制句收尾。
4. 歷史 checkpoint：下一步：第 2 輪 / 互動思考 / #領導原則。

優化說明

1. 讓契約矩陣能處理真實 review 中的壓力，而不只是在冷靜情境下成立。
2. 不降低證據要求；只是把補證據限制在最小可執行路徑。
3. 下一批需處理領導原則、權力動態與責任，確定誰要主動要求升級或阻止錯放。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪互動思考第六批

### 第 2 輪 / 互動思考 / #領導原則

狀態：完成

本次使用：把 review 防從眾檢查推進成主責與 review 主導者必須採取的領導動作。

核心判斷

1. 若沒有人先宣告改動層級，review 會把分類責任推給最晚發現問題的人。
2. review 主導者若不主動要求升級通道，高風險改動可能被低顯著性通道錯放。
3. 完成敘述若沒有不得解讀為，領導者等於把測試綠燈誤導成語意安全。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣 review 責任分工`。
2. 責任分工新增 `領導原則`，要求主責先宣告改動層級。
3. 領導原則要求 review 主導者必須要求升級通道，並確保完成敘述保留不得解讀為。

優化說明

1. 讓 review 領導不是掌控合併速度，而是保護證據與責任邊界。
2. 犧牲的是每個契約相關 patch 多一段角色宣告；換來錯放通道時有人必須主動攔下。
3. 剩餘風險是責任分工仍是文件契約，沒有自動 enforcement。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少 review 責任分工與第六批紀錄會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 互動思考 / #權力動態

狀態：完成

本次使用：防止職位、資深度、產品壓力或合併權限覆蓋證據層與採用訊號。

核心判斷

1. 高權限同意容易被誤當成「不用補證據」。
2. 低權限操作者如果不能引用契約矩陣，紅色或黃色訊號容易被壓過。
3. 合併權限應該用來確認證據完整，而不是把紅色或黃色訊號改成綠色。

落地修改

1. `docs/pipeline-mode-contract.md` 的 review 責任分工新增 `權力動態`。
2. 權力動態明確寫出不得用職位或資深度取代證據。
3. 權力動態明確寫出低權限操作者可以引用契約矩陣要求補證據，高權限操作者不得覆蓋紅色或黃色採用訊號。

優化說明

1. 把契約矩陣從「資深者的建議」改成任何操作者都可引用的共同護欄。
2. 保留合併權限，但要求它服務證據，而不是替代證據。
3. 剩餘風險是實際團隊文化仍可能影響低權限操作者是否敢引用。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_contract_matrix_review_responsibility_map`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round2_interaction_leadership_power_responsibility_is_recorded`

### 第 2 輪 / 互動思考 / #責任

狀態：完成

本次使用：把改動者、reviewer、合併者的責任拆開，避免完成敘述與限制句落在沒有人負責的空白地帶。

核心判斷

1. 改動者最知道碰到哪些層級，因此要負責描述改動層級。
2. reviewer 最適合核對通道與命令是否對齊，不能只看文字是否合理。
3. 合併者最後承擔接受改動的責任，因此要確認限制句與剩餘風險存在。

落地修改

1. `docs/pipeline-mode-contract.md` 的 review 責任分工新增 `責任`。
2. 責任段落要求改動者負責描述改動層級。
3. 責任段落要求 reviewer 負責核對通道與命令，合併者負責確認限制句存在。
4. 歷史 checkpoint：下一步：第 2 輪 / 互動思考 / #自我覺察。

優化說明

1. 讓契約矩陣的完成敘述有角色可追溯，不再只是模糊的「團隊應該」。
2. 不新增工具或權限模型；先把角色責任寫進文件契約。
3. 下一批需用自我覺察與制定策略檢查：這套責任分工是否過度官僚，並收尾第 2 輪互動思考。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪互動思考第七批

### 第 2 輪 / 互動思考 / #自我覺察

狀態：完成

本次使用：檢查契約矩陣自己是否正在變成過度官僚或假自動化。

核心判斷

1. 契約矩陣已累積倫理邊界、系統風險、review 對話、防從眾與責任分工；若不自我稽核，可能讓低風險改動也背上過重流程。
2. 矩陣不是自動化審核器，不能替維護者判斷所有 runtime 與使用者行為風險。
3. 低顯著性顯示層仍需要輕量通道，否則契約矩陣會阻礙原本要改善的前端語氣與維護效率。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣 review 自我稽核與收尾策略`。
2. 自我覺察段落明確寫出契約矩陣不是自動化審核器。
3. 自我覺察段落明確寫出規則變多可能增加官僚成本，低顯著性顯示層不得被迫跑高顯著性全矩陣。

優化說明

1. 讓契約矩陣有自己的使用邊界，避免保護機制變成新負擔。
2. 保留高風險升級條件，同時維持低風險輕量通道。
3. 剩餘風險是第三輪仍需重新批判矩陣是否過重與是否需要收斂。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少自我稽核與收尾策略會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 2 輪 / 互動思考 / #制定策略

狀態：完成

本次使用：把第 2 輪互動思考收尾，並把下一輪入口推回批判思考重新拆解問題。

核心判斷

1. 第 2 輪互動思考已完成 20/20，但這不代表 HCS Plus 完成。
2. 最合理的下一步不是繼續往規則堆疊，而是第 3 輪批判思考重新檢查契約矩陣是否過重、是否仍有高風險缺口。
3. 策略上應先選最小足夠路徑，高風險升級，低風險保留輕量通道。

落地修改

1. `docs/pipeline-mode-contract.md` 的自我稽核段落新增 `制定策略` 與 `收尾聲明`。
2. `docs/hcs-plus-optimization-state.md` 新增「第 2 輪互動思考完成：20/20」與第 3 輪批判思考入口。
3. 嚴格輪巡進度將下一批推進到第 3 輪 / 批判思考 / #拆解問題。

優化說明

1. 明確收斂第 2 輪互動思考，不讓流程停在下一批待辦。
2. 明確保留 HCS Plus 尚未完成：仍需第 3 輪完整習慣輪巡與後續綜合優化。
3. 下一批要用批判思考重新檢查目前契約矩陣的成本、缺口與可驗證性。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

## 第 2 輪互動思考收尾

- 已完成：20/20。
- 已落地：倫理邊界、系統風險邊界、系統關係圖、review 對話、防從眾檢查、責任分工、自我稽核與收尾策略。
- 取捨：不新增自動審核器或自動選測工具，保留人工判斷與最小測試命令。
- 剩餘風險：契約矩陣可能仍偏重，且尚未經第 3 輪批判思考重新拆解。
- 下一步：第 3 輪 / 批判思考 / #拆解問題。

## 第 3 輪批判思考第一批

### 第 3 輪 / 批判思考 / #拆解問題

狀態：完成

本次使用：把第 2 輪互動思考收尾後的契約矩陣重新拆解，避免完整矩陣在保護高風險改動時拖慢日常低風險維護。

核心判斷

1. 契約矩陣已能保護 parser/prompt/template、報告呈現與前端顯示層，但它本身已形成矩陣過重風險。
2. 最高影響問題不是再新增規則，而是維護者是否能在 2 分鐘內選到通道。
3. 低顯著性顯示層若被高顯著性流程拖慢，原本降低文案權威感的改善會變得難以維護。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪問題雷達`。
2. 問題雷達把矩陣過重、2 分鐘選通道、低顯著性被拖慢與責任分工限制句落地拆成可檢查項。
3. `docs/hcs-plus-optimization-state.md` 新增第 3 輪批判思考契約矩陣瘦身問題雷達，說明目前套用在文件契約與測試層，尚未變成 runtime 自動流程。

優化說明

1. 解決「契約矩陣越完整越難用」的第三輪入口問題。
2. 取捨是暫不新增自動選測工具，先用文件與測試鎖住應用邊界。
3. 剩餘風險是下一批仍需分析哪些變數會造成錯誤升級或錯誤降級。

驗證方式

- `tests/test_docs_contract.py` 檢查 `契約矩陣第 3 輪問題雷達` 與矩陣過重內容。
- `tests/test_hcs_plus_state.py` 檢查第 3 輪批判思考第一批已寫入狀態表與嚴格附件。

### 第 3 輪 / 批判思考 / #問對問題

狀態：完成

本次使用：把「矩陣是不是太重」改成能決定下一步的三個問題，而不是停在籠統抱怨流程複雜。

核心判斷

1. 最該問的是哪個規則可以被一頁摘要取代，因為這直接影響日常維護入口。
2. 仍需問哪個情境必須保留完整矩陣，避免瘦身後削弱高顯著性契約保護。
3. 還要問哪個證據層仍然沒有 runtime 驗證，避免把文件契約誤當系統自動保證。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪問題雷達新增 `關鍵問題`。
2. 關鍵問題明確列出一頁摘要取代範圍、完整矩陣保留情境與 runtime 驗證缺口。
3. 主狀態表同步記錄「如何應用到系統」的邊界：目前是文件契約與測試層，不是 runtime 自動流程。

優化說明

1. 把下一批工作從「繼續加文件」轉成「決定哪些規則應瘦身、哪些不能瘦身」。
2. 保留高風險升級場景，避免一頁摘要被誤用來跳過完整矩陣。
3. 剩餘風險是關鍵問題尚未轉成 PR 模板或自動檢查。

驗證方式

- `tests/test_docs_contract.py` 檢查關鍵問題中的一頁摘要、完整矩陣與 runtime 驗證缺口。
- `tests/test_hcs_plus_state.py` 檢查 `問對問題` 已在第 3 輪第一批紀錄中完成。

### 第 3 輪 / 批判思考 / #差距分析

狀態：完成

本次使用：對照已完成的契約矩陣能力與仍缺的系統套用方式，找出下一批最小可落地缺口。

核心判斷

1. 已完成速學卡、一頁摘要、三通道命令、倫理邊界、防從眾與責任分工。
2. 仍缺口是日常入口可能太分散、限制句靠人記得寫、低顯著性通道可能被誤用到 parser/prompt/template。
3. 最小下一步不是立刻工具化，而是先用變數分析、偏誤辨識與偏誤降低定義錯誤升級與錯誤降級的護欄。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪問題雷達新增 `差距分析` 表格。
2. `docs/hcs-plus-optimization-state.md` 將第 3 輪第一批標記為完成，並把下一批推進到 `#變數分析/#偏誤辨識/#偏誤降低`。
3. 本嚴格輪巡附件同步新增第 3 輪批判思考第一批與下一步 checkpoint。
4. 歷史 checkpoint：下一步：第 3 輪 / 批判思考 / #拆解問題。

優化說明

1. 解決「知道矩陣可能過重，但不知道下一個最小修改是什麼」的缺口。
2. 取捨是暫時只改善文件與測試契約，不聲稱系統已自動判斷 review 層級。
3. 下一批需檢查哪些變數會讓一頁摘要過度簡化，或讓完整矩陣被不必要套用。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少第 3 輪問題雷達與進度更新會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪批判思考第二批

### 第 3 輪 / 批判思考 / #變數分析

狀態：完成

本次使用：把契約矩陣瘦身的判斷拆成會影響升級或降級的變數，避免只用「看起來小」或「看起來危險」做分類。

核心判斷

1. 改動層級是第一變數：純前端顯示層、報告模板層與 parser/prompt 層需要不同通道。
2. 證據層是第二變數：文件層、測試層、runtime 層與使用者行為層不可互相替代。
3. 可逆性與時程壓力會扭曲判斷；跨層大改或趕合併時，最容易漏掉限制句與案例卡。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪變數與偏誤降低護欄`。
2. `變數分析` 表格列出改動層級、證據層、可逆性與時程壓力。
3. `docs/hcs-plus-optimization-state.md` 新增第 3 輪批判思考契約矩陣變數與偏誤降低護欄。

優化說明

1. 將矩陣瘦身從主觀感覺改成可檢查變數。
2. 保留低風險輕量路徑，但要求跨層改動先升級或拆分。
3. 剩餘風險是變數排序仍需下一批決策樹收斂。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_variable_bias_guardrails`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_critical_variable_bias_reduction_is_recorded`

### 第 3 輪 / 批判思考 / #偏誤辨識

狀態：完成

本次使用：標出契約矩陣瘦身最容易犯的偏誤，避免流程不是變太重，就是變太鬆。

核心判斷

1. 過度升級偏誤會讓低顯著性前端文案被迫跑高顯著性全矩陣。
2. 過度降級偏誤會把 parser/prompt/template 或完整報告正文改動包裝成只改文案。
3. 工具化幻覺與綠燈擴張偏誤會把文件契約或指定測試誤讀成 runtime 與使用者行為已驗證。

落地修改

1. `docs/pipeline-mode-contract.md` 的新護欄章節新增 `偏誤辨識`。
2. 偏誤辨識明確列出過度升級偏誤、過度降級偏誤、工具化幻覺與綠燈擴張偏誤。
3. 本嚴格輪巡附件把上述偏誤列為第 3 輪第二批的完成項。

優化說明

1. 把「矩陣過重」和「矩陣失守」兩種相反風險同時放進護欄。
2. 不把偏誤辨識寫成抽象提醒，而是連到具體誤判：錯誤升級、錯誤降級、錯誤自動化、錯誤宣稱。
3. 剩餘風險是偏誤仍需要下一批決策樹與效用判斷來排序。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 3 輪 / 批判思考 / #偏誤降低

狀態：完成

本次使用：把偏誤轉成可操作的降低規則，讓維護者知道何時用輕量路徑、何時升級、何時必填限制句。

核心判斷

1. 一頁摘要優先可以降低過度升級偏誤，但不能覆蓋跨層與高顯著性改動。
2. 跨層改動升級、證據分層回報與限制句必填可以降低過度降級與綠燈擴張。
3. 案例卡觸發應只套在跨層、黃色或紅色採用訊號，避免低顯著性改動被過度流程化。

落地修改

1. `docs/pipeline-mode-contract.md` 的新護欄章節新增 `偏誤降低`。
2. 偏誤降低規則包含一頁摘要優先、跨層改動升級、證據分層回報、限制句必填與案例卡觸發。
3. `docs/hcs-plus-optimization-state.md` 將第 3 輪批判思考第二批標記為完成，並把下一批推進到 `#決策樹/#目的/#效用`。
4. 歷史 checkpoint：下一步：第 3 輪 / 批判思考 / #變數分析。

優化說明

1. 讓契約矩陣真正能被套用：低風險先輕量，高風險或跨層就升級，完成回報必須分層。
2. 取捨是仍不新增自動工具；目前先把行為規範鎖在文件與測試中。
3. 下一批需要把護欄轉成決策樹、目的與效用檢查，避免維護者不知道先套哪條規則。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少變數與偏誤護欄會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪批判思考第三批

### 第 3 輪 / 批判思考 / #決策樹

狀態：完成

本次使用：把前一批的變數與偏誤護欄排成可執行的分流順序，讓維護者先照決策樹選路。

核心判斷

1. 分流第一步應先判斷是否只碰前端顯示層，避免低風險改動被完整矩陣拖慢。
2. 一旦碰 parser/prompt/template 或核心契約詞，就直接升級高顯著性機器契約通道。
3. 完整報告正文、報告模板與跨層改動需要獨立分流，不能被前端顯示層或高顯著性通道概括。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪分流決策與效用校準`。
2. `決策樹` 把一頁摘要與低顯著性命令、高顯著性機器契約通道、混合層報告呈現通道、案例卡或拆分 patch、文件契約測試排成五步。
3. `docs/hcs-plus-optimization-state.md` 新增第 3 輪批判思考契約矩陣分流決策與效用校準。

優化說明

1. 解決「知道護欄但不知道先套哪條」的操作缺口。
2. 保留低風險效率，同時讓高風險改動無法繞過升級條件。
3. 剩餘風險是決策樹目前由文件測試鎖住，尚未有實際 review 樣本統計。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_decision_purpose_utility`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_critical_decision_purpose_utility_is_recorded`

### 第 3 輪 / 批判思考 / #目的

狀態：完成

本次使用：校準每條分流規則的目的，避免為了流程完整而增加沒有明確價值的步驟。

核心判斷

1. 決策樹的主要目的，是降低 2 分鐘選通道摩擦，而不是建立更厚的審核文件。
2. 高顯著性保護不能因瘦身而被削弱；parser/prompt/template 仍要直接升級。
3. 每個分流結果都要防止綠燈擴張，並保留低顯著性效率。

落地修改

1. `docs/pipeline-mode-contract.md` 的新章節新增 `目的校準`。
2. 目的校準列出降低 2 分鐘選通道摩擦、保住高顯著性契約、防止綠燈擴張與保留低顯著性效率。
3. 主狀態表同步記錄此批目的不是新增 runtime 自動選測，而是建立維護流程契約。

優化說明

1. 讓分流規則有可審查目的，避免矩陣瘦身又變成新官僚成本。
2. 把使用者或維護者效益放在前面：快選通道、少誤判、少過度宣稱。
3. 剩餘風險是目的目前仍偏設計假設，需要下一批用信賴區間與相關性檢查證據強度。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 3 輪 / 批判思考 / #效用

狀態：完成

本次使用：檢查每條分流規則的預期效用、成本與升級或停用條件，避免規則只增加負擔。

核心判斷

1. 一頁摘要優先的效用是降低選通道成本，但跨層或高風險變更時必須停用輕量路徑。
2. 高顯著性與混合層通道的效用是保護契約與報告呈現，但成本是測試與 review 較重。
3. 案例卡、拆分 patch 與證據分層回報有助防止漏跑與過度宣稱，但要保留升級或停用條件。

落地修改

1. `docs/pipeline-mode-contract.md` 的新章節新增 `效用校準` 表格。
2. 效用校準列出每條規則的預期效用、成本、升級或停用條件。
3. `docs/hcs-plus-optimization-state.md` 將第 3 輪第三批標記為完成，並把下一批推進到 `#信賴區間/#相關性/#描述統計`。
4. 歷史 checkpoint：下一步：第 3 輪 / 批判思考 / #決策樹。

優化說明

1. 讓每條規則都能被日後保留、升級或停用，不把流程視為永久正確。
2. 避免只看安全效益而忽略維護成本。
3. 下一批需要用信賴區間、相關性與描述統計整理哪些觀察訊號能支持這些效用假設。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少分流決策、目的與效用校準會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪批判思考第四批

### 第 3 輪 / 批判思考 / #信賴區間

狀態：完成

本次使用：校準分流決策目前能相信到什麼程度，避免把文件契約與測試綠燈外推成真實 review 或 runtime 行為。

核心判斷

1. 目前樣本只包含文件契約、HCS 狀態測試與相關前端回歸測試。
2. 不可外推成所有 review 都會正確選通道，也不可外推成 runtime 或使用者行為已驗證。
3. 至少需要觀察多個契約相關變更案例，才能討論調整決策樹。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪證據校準與觀測統計`。
2. `信賴區間` 段落列出目前樣本、不可外推範圍與觀察窗口。
3. `docs/hcs-plus-optimization-state.md` 新增第 3 輪批判思考契約矩陣證據校準與觀測統計。

優化說明

1. 把決策樹從「看起來合理」降回「目前證據有限但可觀察」。
2. 保留文件契約的價值，但禁止用它宣稱 runtime 自動化或使用者理解。
3. 下一批需把觀察資料轉成機率與顯著性門檻。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_evidence_observation_stats`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_critical_confidence_correlation_stats_is_recorded`

### 第 3 輪 / 批判思考 / #相關性

狀態：完成

本次使用：區分可觀測訊號與因果宣稱，避免把選通道時間下降或限制句出現率上升誤當成流程必然有效。

核心判斷

1. 選通道時間下降只能支持決策樹可能降低摩擦，不能證明通道一定選對。
2. 錯選通道下降可能和決策樹相關，也可能只是樣本較簡單或 reviewer 較熟。
3. 限制句出現率與案例卡觸發率只能說明流程被採用，不代表風險已降低。

落地修改

1. `docs/pipeline-mode-contract.md` 的新章節新增 `相關性` 表格。
2. 表格列出選通道時間、錯選通道、限制句出現率與案例卡觸發率的可支持判斷與不可推論事項。
3. 本嚴格輪巡附件將相關性限制寫入第 3 輪第四批。

優化說明

1. 降低「觀測訊號變好就是流程有效」的錯誤推論。
2. 讓後續回顧能同時看訊號與樣本脈絡。
3. 剩餘風險是仍需下一批建立回歸監測與顯著性門檻。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 3 輪 / 批判思考 / #描述統計

狀態：完成

本次使用：定義後續要記錄哪些統計欄位，讓分流決策的效用可以被觀察，而不是停在主觀回饋。

核心判斷

1. 樣本數是第一欄位；沒有樣本數，任何改善率都可能只是零散個案。
2. 中位選通道時間比平均時間更適合追蹤 2 分鐘摩擦，避免極端案例扭曲。
3. 錯選率、跨層改動比例、案例卡觸發率與限制句出現率能分別觀察分流品質、樣本難度、案例卡採用與完成回報品質。

落地修改

1. `docs/pipeline-mode-contract.md` 的新章節新增 `描述統計` 表格。
2. 描述統計定義樣本數、中位選通道時間、錯選率、跨層改動比例、案例卡觸發率與限制句出現率。
3. `docs/hcs-plus-optimization-state.md` 將第 3 輪第四批標記為完成，並把下一批推進到 `#機率/#迴歸/#顯著性`。
4. 歷史 checkpoint：下一步：第 3 輪 / 批判思考 / #信賴區間。

優化說明

1. 讓分流決策後續能被比較，而不是只能靠文字感覺。
2. 保留「目前不可外推」的邊界，避免小樣本統計被過度使用。
3. 下一批需要判斷哪些機率、回歸與顯著性門檻能支撐後續收斂。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少證據校準與觀測統計會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪批判思考第五批

### 第 3 輪 / 批判思考 / #機率

狀態：完成

本次使用：把前一批描述統計轉成風險機率判讀，避免錯選率、限制句缺漏率與案例卡漏觸發率只停在記錄欄位。

核心判斷

1. 錯選率是決策樹分流品質的主要風險機率，但少於至少 5 個案例時只能當作個案訊號。
2. 限制句缺漏率只要大於 0%，就代表完成回報仍可能把測試綠燈誇大成安全證明。
3. 案例卡漏觸發率能檢查跨層或黃色紅色訊號是否被低估，尤其是混合層與高顯著性機器契約改動。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪風險機率與顯著性門檻`。
2. `機率` 表格定義錯選率、限制句缺漏率、案例卡漏觸發率與對應風險機率判讀。
3. `docs/hcs-plus-optimization-state.md` 新增第 3 輪批判思考契約矩陣風險機率與顯著性門檻。

優化說明

1. 把「觀察到了什麼」推進成「何時應視為風險」。
2. 犧牲的是門檻仍屬暫定文件契約；它不能替代實際 review 或 runtime 自動檢查。
3. 下一批需檢查這些門檻背後的證據品質。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_probability_regression_significance_thresholds`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_critical_probability_regression_significance_is_recorded`

### 第 3 輪 / 批判思考 / #迴歸

狀態：完成

本次使用：定義何時把觀測訊號視為流程回歸，而不是把單一窗口波動誤當成趨勢。

核心判斷

1. 連續兩個觀察窗口同方向惡化，才足以作為穩定回歸監測訊號。
2. 回歸監測必須同時看跨層改動比例；樣本變難時，錯選率上升不一定代表決策樹變差。
3. parser/prompt/template 改動被放入低顯著性通道是紅色高風險案例，可立即升級，不必等待第二窗口。

落地修改

1. `docs/pipeline-mode-contract.md` 的第五批章節新增 `迴歸` 規則。
2. `迴歸` 規則要求連續兩個觀察窗口，並保留紅色高風險例外。
3. `docs/hcs-plus-optimization-state.md` 的第五批系統應用方式要求同方向回歸才調整決策樹或案例卡規則。

優化說明

1. 降低單次失敗就過度改規則的機率。
2. 同時保留高風險契約錯放時的立即升級路徑。
3. 剩餘風險是目前仍缺真實窗口資料；本批只建立監測契約。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 3 輪 / 批判思考 / #顯著性

狀態：完成

本次使用：設定小樣本限制與升級門檻，避免測試通過、文件存在或單一案例變好被宣稱成流程改善。

核心判斷

1. 少於至少 5 個案例時，所有統計只能描述個案與待觀察風險，不得宣稱改善。
2. 至少 5 個案例後，錯選率超過 20%、限制句缺漏率大於 0%、案例卡漏觸發率超過 10% 都應升級 review。
3. 調整決策樹前要確認連續兩個觀察窗口同方向回歸，並排除樣本層級改變。

落地修改

1. `docs/pipeline-mode-contract.md` 的第五批章節新增 `顯著性` 規則。
2. `顯著性` 規則明確寫入小樣本、至少 5 個案例、升級門檻、調整決策樹與不得宣稱改善。
3. `docs/hcs-plus-optimization-state.md` 將第 3 輪 `#機率/#迴歸/#顯著性` 標記為完成，並把下一批推進到 `#證據基礎/#演繹/#歸納`。
4. 歷史 checkpoint：下一步：第 3 輪 / 批判思考 / #機率。

優化說明

1. 把「看起來有改善」降回可驗證的顯著性條件。
2. 保留小樣本邊界，避免文件契約被包裝成已證實成效。
3. 下一批需要檢查風險門檻背後的證據基礎、演繹規則與歸納限制。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少風險機率、回歸監測與顯著性門檻會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪批判思考第六批

### 第 3 輪 / 批判思考 / #證據基礎

狀態：完成

本次使用：檢查上一批風險門檻能被哪些證據支持，避免單次測試綠燈、未標樣本數比例或章節存在被誤當成改善證據。

核心判斷

1. 文件契約測試只能證明章節與 checkpoint 還在，不能證明 review 採用或 runtime 安全。
2. 觀察窗口紀錄必須包含樣本數、改動層級與風險欄位，否則比例沒有可解釋性。
3. 案例卡能支持單一跨層案例的升級或拆分判斷，但不能代表全部生成報告母體。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪證據規則與外推邊界`。
2. `證據基礎` 表格列出文件契約測試、觀察窗口紀錄與案例卡三類可接受證據。
3. 同章節新增 `不可作為證據`，排除單次綠燈、未標樣本數比例與單純章節存在。

優化說明

1. 把「有證據」拆成證據類型與可支持判斷，降低證據層混用。
2. 犧牲的是完成回報會更嚴格；換來更少過度宣稱。
3. 下一批需檢查常見謬誤，避免維護者仍把文件綠燈當成流程成效。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_evidence_rules_induction_boundaries`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_critical_evidence_deduction_induction_is_recorded`

### 第 3 輪 / 批判思考 / #演繹

狀態：完成

本次使用：把可接受證據轉成可執行推論規則，避免每次靠臨場判斷是否升級、是否可宣稱改善。

核心判斷

1. 若碰 parser/prompt/template 或核心契約詞，應立即升級到高顯著性機器契約通道，不等待觀察窗口。
2. 若少於至少 5 個案例，只能描述個案與待觀察風險，不能演繹為決策樹已改善。
3. 只有連續兩個觀察窗口同方向回歸，且跨層改動比例未同步升高，才可推論需要調整決策樹或案例卡規則。

落地修改

1. `docs/pipeline-mode-contract.md` 的第六批章節新增 `演繹` 規則。
2. `演繹` 規則明確寫入立即升級、小樣本限制與連續窗口條件。
3. `docs/hcs-plus-optimization-state.md` 的第六批摘要記錄這些規則如何套用到完成回報。

優化說明

1. 讓高風險契約改動不被統計等待拖延。
2. 讓低樣本比例不被誤用成趨勢證明。
3. 剩餘風險是規則仍需來源品質分級支撐，下一批會處理。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 3 輪 / 批判思考 / #歸納

狀態：完成

本次使用：明確寫出這批證據規則能外推到哪裡、不能外推到哪裡，避免有限文件與案例被包成完整安全證明。

核心判斷

1. 文件契約測試只能歸納到目前文件與 HCS 狀態保留護欄。
2. 觀察窗口紀錄只能歸納到已記錄案例，不能代表未記錄改動或全部 review 行為。
3. 案例卡只能歸納到代表性跨層案例，不能代表生成報告母體、歷史輸出或未來 LLM 回覆。

落地修改

1. `docs/pipeline-mode-contract.md` 的第六批章節新增 `歸納` 與 `外推邊界`。
2. `歸納` 規則明確寫入不得外推到 runtime 安全、真實使用者理解與生成報告母體。
3. `docs/hcs-plus-optimization-state.md` 將第 3 輪 `#證據基礎/#演繹/#歸納` 標記為完成，並把下一批推進到 `#謬誤/#來源品質/#情境脈絡`。
4. 歷史 checkpoint：下一步：第 3 輪 / 批判思考 / #證據基礎。

優化說明

1. 把有限觀察的邊界寫明，降低「文件有了所以系統安全」的錯誤歸納。
2. 保留後續升級空間：若要證明 runtime 或使用者理解，仍需新的證據來源。
3. 下一批將處理謬誤、來源品質與情境脈絡，防止證據規則在使用時被誤讀。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少證據規則與外推邊界會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪批判思考第七批

### 第 3 輪 / 批判思考 / #謬誤

狀態：完成

本次使用：檢查證據規則最容易被誤用成哪些錯誤推論，避免文件護欄反而被包裝成流程成效或安全證明。

核心判斷

1. 測試綠燈謬誤會把文件契約測試通過誤讀成 runtime 安全或真實使用者理解改善。
2. 樣本數謬誤會把未標樣本數的比例變化誤讀成決策樹已改善。
3. 案例代表性謬誤會把單一案例卡誤讀成所有跨層改動或生成報告母體都安全。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪反謬誤與來源情境邊界`。
2. `謬誤` 表格列出測試綠燈謬誤、樣本數謬誤、案例代表性謬誤，以及各自錯誤推論與反謬誤護欄。
3. `docs/hcs-plus-optimization-state.md` 新增第 3 輪批判思考契約矩陣反謬誤與來源情境邊界。

優化說明

1. 把「證據可以支持什麼」再補上「證據最常被誤用成什麼」。
2. 犧牲的是文件更嚴格；換來完成回報不容易過度宣稱。
3. 下一批需批判目前矩陣是否已過重，避免護欄本身造成摩擦。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_fallacy_source_context_boundaries`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_critical_fallacy_source_context_is_recorded`

### 第 3 輪 / 批判思考 / #來源品質

狀態：完成

本次使用：把證據來源分成高品質來源、次級來源與不得作為完成證據，避免低品質觀察支撐高風險結論。

核心判斷

1. 高品質來源需要可重跑、可對照 diff、含樣本數與改動層級，或完整案例卡。
2. 次級來源可以輔助理解，但不能單獨支持流程改善或使用者理解改善。
3. 單次綠燈、未標樣本數比例、未列改動層級觀察與未寫限制句完成回報，都不得作為完成證據。

落地修改

1. `docs/pipeline-mode-contract.md` 的第七批章節新增 `來源品質` 表格。
2. 來源品質表把可使用來源與不得作為完成證據分開。
3. `docs/hcs-plus-optimization-state.md` 的第七批摘要記錄來源分級如何套用到完成回報。

優化說明

1. 防止低品質證據支撐高風險契約結論。
2. 讓 reviewer 可以要求補測試輸出、補樣本數或補案例卡，而不是只接受口頭說明。
3. 下一批需估算這些來源品質欄位增加多少維護成本。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 3 輪 / 批判思考 / #情境脈絡

狀態：完成

本次使用：限制反謬誤與來源品質規則適用在哪些情境，避免一般 UI 小改也被完整契約矩陣拖慢。

核心判斷

1. 本護欄只適用於契約相關變更，例如 parser/prompt/template、報告正文、跨層改動、案例卡或分流決策。
2. 一般 UI 文案、純排版、靜態樣式或不碰報告語意的微調，不適用完整契約矩陣。
3. 黃色、紅色、跨層、核心契約詞或樣本不足卻要調整規則的情境，需要人工 review。

落地修改

1. `docs/pipeline-mode-contract.md` 的第七批章節新增 `情境脈絡` 規則。
2. 情境脈絡規則明確寫入只適用於契約相關變更、不適用於一般 UI 文案、需要人工 review、不得替代 runtime 驗證、不得替代使用者研究。
3. `docs/hcs-plus-optimization-state.md` 將第 3 輪 `#謬誤/#來源品質/#情境脈絡` 標記為完成，並把下一批推進到 `#批判/#估算/#詮釋框架`。
4. 歷史 checkpoint：下一步：第 3 輪 / 批判思考 / #謬誤。

優化說明

1. 避免安全流程外溢到一般 UI 小改，保留低風險改動效率。
2. 同時保留高風險契約變更的人工 review 與 runtime/使用者研究邊界。
3. 下一批需批判矩陣負擔、估算執行成本，並建立完成回報詮釋框架。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少反謬誤與來源情境邊界會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪批判思考第八批

### 第 3 輪 / 批判思考 / #批判

狀態：完成

本次使用：批判前面新增的契約矩陣是否已造成矩陣過重，避免護欄本身拖慢低風險 UI 與一般顯示微調。

核心判斷

1. 矩陣過重風險已出現，尤其是把每個 UI 小改都拉進完整案例卡或人工 review 時。
2. 必留護欄應保留給 parser/prompt/template、核心契約詞、跨層改動、黃色或紅色採用訊號。
3. 低風險 UI、純排版、靜態樣式與不碰報告語意的顯示微調，應可短句替代；自動選測、案例卡資料庫與觀察窗口儀表板可延後工具化。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪負擔估算與完成詮釋框架`。
2. `批判` 表格分出必留護欄、可短句替代、可延後工具化，避免同一套矩陣套到所有改動。
3. `docs/hcs-plus-optimization-state.md` 新增第 3 輪批判思考契約矩陣負擔估算與完成詮釋框架，並把本批判斷轉成系統應用方式。

優化說明

1. 這次修改不是降低高風險契約的要求，而是避免高風險規則外溢到低風險 UI。
2. 犧牲的是文件多一層分類；換來 reviewer 可以快速判斷何時用短句、何時用完整矩陣。
3. 下一批需檢查這個分層是否足夠合理，避免又新增無法驗證的抽象語句。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_burden_estimate_interpretation_frame`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_critical_critique_estimation_frame_is_recorded`

### 第 3 輪 / 批判思考 / #估算

狀態：完成

本次使用：估算不同改動層級的完成回報成本，讓系統應用方式不只說「要更嚴謹」，也知道大約要花多少成本。

核心判斷

1. 低風險 UI 完成回報應控制在 2 分鐘內，用 1 句通道判斷加前端測試結果即可。
2. 混合層報告呈現應控制在 3 分鐘內，補上改動層級、測試命令與限制句。
3. 高風險契約不設硬上限，因為 parser/prompt/template 或核心契約詞的錯放成本高於回報成本。

落地修改

1. `docs/pipeline-mode-contract.md` 的 `估算` 表格新增低風險 UI、混合層報告呈現與高風險契約三種完成回報成本。
2. 每種情境都寫入建議上限與最小證據，讓完成回報可以直接引用。
3. `docs/hcs-plus-optimization-state.md` 記錄「低風險 UI 2 分鐘、混合層 3 分鐘、高風險契約不設硬上限」的套用規則。

優化說明

1. 成本估算避免文件契約變成無限擴張的 checklist。
2. 低風險情境保留效率，高風險情境保留完整證據。
3. 仍需下一批用可驗證性把 26/26 完成狀態鎖住，避免估算只停在文字宣稱。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 3 輪 / 批判思考 / #詮釋框架

狀態：完成

本次使用：建立完成回報詮釋框架，限制文件契約、觀察窗口、runtime 驗證與使用者研究各自能支持的結論。

核心判斷

1. 文件契約通過只能代表護欄仍存在，不得宣稱安全、runtime 已驗證或使用者理解改善。
2. 觀察窗口有樣本只能支持已記錄案例的調整方向，不得宣稱理解改善，也不得推論未記錄案例。
3. runtime 驗證與使用者研究只能各自描述指定路徑或研究樣本中的結果，不能互相替代。

落地修改

1. `docs/pipeline-mode-contract.md` 的 `詮釋框架` 表格新增文件契約通過、觀察窗口有樣本、runtime 驗證通過、使用者研究完成四種證據狀態。
2. 每種證據狀態都新增禁止宣稱範圍，包含不得宣稱安全、不得宣稱理解改善與不得替代 parser/prompt/template 契約驗證。
3. `docs/hcs-plus-optimization-state.md` 將 `#批判/#估算/#詮釋框架` 標記完成，並把下一批推進到 `#合理性/#可驗證性`。
4. 歷史 checkpoint：下一步：第 3 輪 / 批判思考 / #批判。

優化說明

1. 這讓完成回報可以直接回答「這些修改如何應用到系統」：依改動層級選通道，依證據狀態限制宣稱。
2. 犧牲的是完成回報語氣更保守；換來文件測試、runtime 測試與使用者研究不會被混為一談。
3. 下一批需檢查第 3 輪批判思考是否能合理收尾，並用測試鎖住完整單項完成狀態。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少負擔估算與完成詮釋框架會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪批判思考第九批

### 第 3 輪 / 批判思考 / #合理性

狀態：完成

本次使用：檢查第 3 輪批判思考是否能合理收尾，而不是繼續堆疊契約矩陣、觀察欄位或工具化想像。

核心判斷

1. 第 3 輪批判思考已完成 26/26 單項，涵蓋問題拆解、變數偏誤、分流決策、證據統計、風險門檻、證據規則、反謬誤、來源情境、負擔估算與完成詮釋框架。
2. 目前合理收尾是保留文件契約與人工判斷，不新增自動選測腳本；跨層、黃色/紅色訊號與核心契約詞仍需要 reviewer 判斷。
3. 下一步應轉入第 3 輪創意思考，把矩陣從「可驗證」推向「更容易被操作者學會與採用」。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪收尾與可重跑驗證`。
2. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪批判思考收尾檢查` 與 D72 決策紀錄。
3. 本嚴格輪巡附件將第 3 輪 / 批判思考 / `#合理性` 標成完成，並把下一分類入口推進到第 3 輪創意思考。
4. 歷史 checkpoint：下一步：第 3 輪 / 批判思考 / #合理性。

優化說明

1. 這次收尾避免批判思考無限延伸，承認目前已足以支撐下一分類。
2. 犧牲的是暫不做自動選測工具；換來責任邊界更清楚，不把人工判斷包成假自動化。
3. 剩餘風險是矩陣仍可能學習成本偏高，因此下一批用創意思考處理學習科學、限制條件與類比。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少第 3 輪收尾與 26/26 checkpoint 會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 3 輪 / 批判思考 / #可驗證性

狀態：完成

本次使用：把第 3 輪批判思考完成狀態轉成可重跑檢查，避免只靠人工記憶宣稱 26/26 已完成。

核心判斷

1. 可驗證性需要同時鎖住四層：契約文件、主狀態表、嚴格附件、下一分類入口。
2. `tests/test_hcs_plus_state.py` 需證明第 3 輪批判思考 `#合理性/#可驗證性` 已完成，且第 3 輪創意思考成為下一批。
3. `tests/test_docs_contract.py` 需證明契約文件保留不得宣稱 HCS Plus 完成、保留人工判斷、失敗即回到批判思考等限制。

落地修改

1. `tests/test_docs_contract.py` 新增第 3 輪收尾與可重跑驗證契約測試。
2. `tests/test_hcs_plus_state.py` 新增第 3 輪批判思考收尾 checkpoint 測試，並把進度期待改成 `#合理性/#可驗證性` 完成。
3. 本嚴格輪巡附件新增「第 3 輪批判思考收尾」，並將下一步推進到第 3 輪 / 創意思考 / #學習科學。

優化說明

1. 將第 3 輪批判思考從多個契約矩陣章節收束成可驗證 checkpoint。
2. 明確保留 HCS Plus 尚未完成的事實：目前只是第 3 輪批判思考完成，完整流程還要繼續創意思考、溝通思考、互動思考與綜合優化。
3. 若後續測試或文件缺少限制句，必須回到批判思考補證據，不得直接推進。

驗證方式

- `tests/test_hcs_plus_state.py`
- `tests/test_docs_contract.py`
- `tests/test_static_history_filters.py`
- `tests/test_frontend_visual_optional.py`

## 第 3 輪批判思考收尾

- 已完成：26/26。
- 合理性結論：第 3 輪批判思考已完成契約矩陣瘦身、證據分層、反謬誤、來源情境、負擔估算與完成詮釋框架；可合理轉入創意思考，不新增自動選測腳本。
- 可驗證性結論：第 3 輪批判思考 26 個單項都已在本附件留下完成章節，並由 `tests/test_hcs_plus_state.py` 與 `tests/test_docs_contract.py` 鎖住。
- 邊界：不得宣稱 HCS Plus 完成、不得宣稱 runtime 安全、不得宣稱使用者理解改善。
- 下一步：第 3 輪 / 創意思考 / #學習科學。

## 第 3 輪創意思考第一批

### 第 3 輪 / 創意思考 / #學習科學

狀態：完成

本次使用：把第 3 輪批判思考收尾後的契約矩陣，轉成第一次使用也能快速進入的學習路徑。

核心判斷

1. 維護者不應先讀完整矩陣才知道怎麼開始；學習入口應先回答「現在要判斷什麼」。
2. 三層學習路徑最小足夠：10 秒判斷改動風險、90 秒執行命令與限制句、5 分鐘復盤錯選或漏證據。
3. 學習入口必須保留前一輪批判思考的限制，不可把易學性包成安全保證。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪創意學習入口`。
2. 該章節新增 `三層學習路徑`，分成 `10 秒判斷`、`90 秒執行`、`5 分鐘復盤`。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪創意思考契約矩陣學習入口`。
4. 歷史 checkpoint：下一步：第 3 輪 / 創意思考 / #學習科學。

優化說明

1. 這讓契約矩陣從完整規範變成可進入的學習流程。
2. 犧牲的是仍需人工判斷；換來維護者能先做小判斷，再逐步深入。
3. 下一批需把三層路徑轉成更明確的操作演算法。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_creative_learning_entry`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_creative_learning_constraints_analogy_is_recorded`

### 第 3 輪 / 創意思考 / #限制條件

狀態：完成

本次使用：界定學習入口不做哪些事，避免它被誤用成 runtime 改動、自動選測或遙測方案。

核心判斷

1. 本批只改文件契約與學習順序，不改 runtime 行為、parser、prompt、template、報告生成或前端互動。
2. 不新增自動選測腳本，也不新增遙測；目前仍靠操作者判斷改動層級並人工記錄觀察。
3. 黃色/紅色訊號、跨層改動與核心契約詞仍要人工 review，不能被學習入口取代。

落地修改

1. `docs/pipeline-mode-contract.md` 的創意學習入口新增 `限制條件`。
2. 限制條件明確寫入不改 runtime 行為、不新增自動選測腳本、不新增遙測、不替代人工 review。
3. `docs/hcs-plus-optimization-state.md` 將這些限制轉成系統應用方式，要求安檢通過不得外推為 runtime 安全或使用者理解改善。

優化說明

1. 限制條件讓學習入口保持輕量，不漂移成新工具專案。
2. 代價是沒有立即自動化；收益是維護責任與證據邊界仍清楚。
3. 下一批可用設計思考降低限制條件帶來的閱讀阻力。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 3 輪 / 創意思考 / #類比

狀態：完成

本次使用：用登機前安檢類比說明契約矩陣如何分流、補證據與限制外推。

核心判斷

1. 快速通道對應低風險 UI 與不碰報告語意的顯示微調。
2. 人工複檢對應黃色/紅色訊號、跨層改動、核心契約詞或高風險契約。
3. 證據托盤對應測試輸出、diff、案例卡、觀察窗口與完成回報限制句；不把安檢通過解讀成航程安全。

落地修改

1. `docs/pipeline-mode-contract.md` 的創意學習入口新增 `類比` 與登機前安檢對照表。
2. 對照表把快速通道、人工複檢、證據托盤連到系統改動層級與不可外推範圍。
3. `docs/hcs-plus-optimization-state.md` 將類比轉成系統應用方式：安檢通過不得宣稱 runtime 安全、使用者理解改善或 HCS Plus 完成。

優化說明

1. 類比降低抽象矩陣的進入成本，讓新維護者先理解分流與證據托盤。
2. 類比仍有邊界：它只輔助學習，不取代實際測試與 review。
3. 下一批需把這個類比轉成可直接套用的捷思規則與操作演算法。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少創意學習入口會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪創意思考第二批

### 第 3 輪 / 創意思考 / #演算法

狀態：完成

本次使用：把上一批的 10 秒判斷、90 秒執行與 5 分鐘復盤，轉成可直接照做的操作演算法。

核心判斷

1. 三層學習入口仍偏概念；操作者需要明確知道先判斷、再選通道、再裝證據托盤、最後怎麼完成回報。
2. 四步操作演算法可以降低第一次使用時的順序成本，也能讓 reviewer 快速看出缺在哪一步。
3. 演算法仍保留人工判斷，不把選通道自動化。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪操作演算法與捷思規則`。
2. 該章節新增 `四步操作演算法`：`步驟 1：10 秒判斷`、`步驟 2：選擇通道`、`步驟 3：裝好證據托盤`、`步驟 4：完成回報`。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪創意思考契約矩陣操作演算法與捷思規則`。
4. 歷史 checkpoint：下一步：第 3 輪 / 創意思考 / #演算法。

優化說明

1. 這把學習入口從「理解框架」推進成「可照做流程」。
2. 代價是文件稍長；收益是每一步都有明確產出與回退條件。
3. 下一批需檢查這套演算法是否能再最佳化，避免低風險 UI 被過度流程化。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_operation_algorithm_and_heuristics`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_creative_algorithm_design_heuristics_is_recorded`

### 第 3 輪 / 創意思考 / #設計思考

狀態：完成

本次使用：從操作者情境出發，讓不同改動類型走不同預設路徑，而不是要求所有人讀同一套矩陣。

核心判斷

1. 只改低風險 UI 的操作者需要快速通道，不應被高風險契約矩陣拖慢。
2. 改報告模板或正文呈現的操作者需要混合層報告呈現通道，避免只跑前端測試。
3. 改 parser、prompt、template 或核心契約詞的操作者需要先人工複檢，不能用短句帶過。

落地修改

1. `docs/pipeline-mode-contract.md` 的第二批章節新增 `設計思考` 表格。
2. 表格新增 `情境 A：只改低風險 UI`、`情境 B：改報告模板或正文呈現`、`情境 C：改 parser、prompt、template 或核心契約詞`。
3. `docs/hcs-plus-optimization-state.md` 將三個情境轉成系統應用方式。

優化說明

1. 情境化設計讓不同維護者不用自行翻譯矩陣。
2. 犧牲的是仍需判斷自己屬於哪個情境；下一批可用資料視覺化或採用訊號降低誤判。
3. 高風險情境仍保留案例卡、必跑命令與限制句。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 3 輪 / 創意思考 / #捷思法

狀態：完成

本次使用：把操作演算法壓成三條快速規則，讓維護者在高壓 review 或小改動時仍能正確分流。

核心判斷

1. 有核心契約詞就先人工複檢，避免把 parser/prompt/template 風險降級。
2. 只在前端顯示才走快速通道，避免前端測試被誤用成 parser/prompt 安全證明。
3. 缺少限制句就不得完成，避免完成回報過度宣稱。

落地修改

1. `docs/pipeline-mode-contract.md` 的第二批章節新增 `捷思法`。
2. 捷思法寫入 `有核心契約詞就先人工複檢`、`只在前端顯示才走快速通道`、`缺少限制句就不得完成`。
3. `docs/hcs-plus-optimization-state.md` 將 `#演算法/#設計思考/#捷思法` 標記完成，並把下一批推進到 `#最佳化/#假說發展/#資料視覺化`。

優化說明

1. 三條捷思規則讓四步演算法更容易在實務 review 中被記住。
2. 捷思規則不是例外通行證；任何命中高風險條件仍要回到完整通道。
3. 下一批需建立採用假說與可視化訊號，觀察這些規則是否降低錯選通道。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少操作演算法與捷思規則會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪創意思考第三批

### 第 3 輪 / 創意思考 / #最佳化

狀態：完成

本次使用：把操作演算法要最佳化的目標收斂成可觀察的採用摩擦，而不是抽象地說「流程更好用」。

核心判斷

1. 目前最重要的採用摩擦是錯選通道、漏跑命令、限制句缺漏與案例卡漏補。
2. 最佳化目標是降低 review 摩擦與缺漏，不是宣稱流程已改善。
3. 最小調整應先回到四步操作演算法、證據托盤或人工複檢提示，不新增工具或遙測。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪採用最佳化與訊號板`。
2. 該章節新增 `最佳化` 表格，把錯選通道、漏跑命令、限制句缺漏、案例卡漏補寫成採用摩擦。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪創意思考契約矩陣採用最佳化與訊號板`。
4. 歷史 checkpoint：下一步：第 3 輪 / 創意思考 / #最佳化。

優化說明

1. 這讓「操作演算法是否好用」能被具體觀察，而不是只靠主觀感受。
2. 犧牲的是暫時仍靠人工觀察；換來不新增遙測、不擴大 runtime 面。
3. 下一批需把採用摩擦轉成代表性案例模型與案例卡。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_adoption_optimization_signal_board`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_creative_optimization_hypothesis_visualization_is_recorded`

### 第 3 輪 / 創意思考 / #假說發展

狀態：完成

本次使用：把操作演算法、證據托盤與快速規則各自轉成可觀察假說，避免直接宣稱改善。

核心判斷

1. 假說 1：四步操作會降低錯選通道，但只有人工觀察與足夠樣本才能支持趨勢。
2. 假說 2：證據托盤會降低漏跑命令，但不能推論 runtime 安全或測試覆蓋完整。
3. 假說 3：三條快速規則會降低限制句缺漏，但不能推論使用者理解改善。

落地修改

1. `docs/pipeline-mode-contract.md` 的第三批章節新增 `假說發展`。
2. 假說表寫入三個可觀察假說、觀察方式與不可宣稱範圍。
3. `docs/hcs-plus-optimization-state.md` 記錄假說仍需下一批抽樣方式支撐，不得用單一觀察過度外推。

優化說明

1. 假說讓採用觀察有方向，但保留證據不足時不得宣稱改善。
2. 下一批必須處理抽樣與個案，否則訊號板容易只剩主觀顏色。
3. 仍維持文件契約，不新增產品事件或背景收集。

驗證方式

- `tests/test_docs_contract.py`
- `tests/test_hcs_plus_state.py`

### 第 3 輪 / 創意思考 / #資料視覺化

狀態：完成

本次使用：把人工觀察結果做成綠色、黃色、紅色採用訊號板，讓 reviewer 快速知道該保留、補提示或停止合併。

核心判斷

1. 綠色只代表目前人工觀察未見缺漏，不代表已改善。
2. 黃色代表出現 1 到 2 次採用摩擦，需要補案例、補提示或重寫步驟。
3. 紅色代表高風險契約被放進快速通道、核心契約詞缺人工複檢，或完成回報宣稱安全/理解改善，必須停止合併。

落地修改

1. `docs/pipeline-mode-contract.md` 的第三批章節新增 `資料視覺化` 與 `採用訊號板`。
2. 採用訊號板定義綠色、黃色、紅色訊號與對應行動。
3. `docs/hcs-plus-optimization-state.md` 將 `#最佳化/#假說發展/#資料視覺化` 標記完成，並把下一批推進到 `#建模/#抽樣/#個案研究`。

優化說明

1. 視覺化在這裡是文字訊號板，不新增 UI 或產品遙測。
2. 訊號板讓採用摩擦更容易掃讀，但不能替代測試、runtime 驗證或使用者研究。
3. 下一批要建立案例模型，讓每個黃色或紅色訊號可追溯到具體改動。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少採用最佳化與訊號板會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪創意思考第四批

### 第 3 輪 / 創意思考 / #建模

狀態：完成

本次使用：把採用訊號板轉成代表性案例模型，讓綠色、黃色與紅色不只是一個顏色，而是能回到具體改動類型與必看證據。

核心判斷

1. 訊號板若不能連回案例，黃色/紅色很難被複盤。
2. 四類模型足夠覆蓋目前維護情境：低風險快速通道、混合層報告呈現、高風險契約人工複檢、紅色阻擋。
3. 模型只代表案例類型，不代表母體趨勢。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪案例模型與抽樣案例卡`。
2. 章節新增 `代表性案例模型`，包含模型 A：低風險快速通道案例、模型 B：混合層報告呈現案例、模型 C：高風險契約人工複檢案例、模型 D：紅色阻擋案例。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪創意思考契約矩陣案例模型與抽樣案例卡`，並把 `#建模` 對應到同一份契約文件。
4. 歷史 checkpoint：下一步：第 3 輪 / 創意思考 / #建模。

優化說明

1. 建模讓每個訊號可以回到具體案例，不再停在抽象顏色。
2. 代價是文件多一層分類；收益是 review 時能先辨識通道與必看證據。
3. 仍不新增遙測、不新增 runtime 行為，也不把案例模型當作自動判斷器。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少案例模型與抽樣案例卡會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 3 輪 / 創意思考 / #抽樣

狀態：完成

本次使用：定義哪些觀察需要抽成案例，避免只挑方便或漂亮的綠色案例。

核心判斷

1. 每個觀察窗口至少要保留實際出現的代表性模型，未出現時要明記「本窗口未觀察到」。
2. 黃色或紅色必抽，因為錯選通道、漏跑命令、限制句缺漏或案例卡漏補才是最需要回放的學習材料。
3. 少於 5 個案例不得宣稱趨勢；只能描述個案與待觀察風險。

落地修改

1. `docs/pipeline-mode-contract.md` 的第四批章節新增 `抽樣`。
2. 抽樣規則寫入 `代表性抽樣規則`、`每個觀察窗口`、`黃色或紅色必抽` 與 `少於 5 個案例不得宣稱趨勢`。
3. `docs/hcs-plus-optimization-state.md` 的系統應用方式明確要求少於 5 個案例不得外推。

優化說明

1. 抽樣規則讓案例卡不只收集成功案例，也收集流程失守案例。
2. 這能支撐下一批比較組與介入研究，但目前仍只是觀察設計，不是改善證明。
3. 若某模型未出現，不得拿其他模型補位，避免代表性被偷換。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_case_models_sampling_cards`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_creative_models_sampling_case_cards_is_recorded`

### 第 3 輪 / 創意思考 / #個案研究

狀態：完成

本次使用：把抽到的案例收斂成案例卡格式，讓每個個案都有可追溯的改動、通道、證據、訊號與不可外推邊界。

核心判斷

1. 個案研究要能回答「這次改了什麼、選了哪條通道、看了哪些證據」。
2. 案例卡必須放入限制句與不可外推，避免單一案例被講成流程改善或 runtime 安全。
3. 補救行動要寫進案例卡，否則黃色或紅色訊號很容易只停在紀錄而沒有回到操作流程。

落地修改

1. `docs/pipeline-mode-contract.md` 的第四批章節新增 `個案研究` 與 `案例卡格式`。
2. 案例卡格式收斂為改動描述、改動層級、選擇通道、證據托盤、採用訊號、限制句、補救行動、不可外推。
3. `docs/hcs-plus-optimization-state.md` 將 `#建模/#抽樣/#個案研究` 標記完成，並把下一批推進到 `#比較組/#介入研究/#訪談調查`。

優化說明

1. 案例卡讓訊號板可被複盤，也讓下一批能比較案例模型使用前後的錯選通道、漏跑命令與限制句缺漏。
2. 目前不宣稱它已改善 review 行為；只宣稱文件契約與測試已鎖住案例格式。
3. 完整 HCS Plus 仍未完成，下一批需繼續創意思考的比較與介入設計。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少案例卡格式會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪創意思考第五批

### 第 3 輪 / 創意思考 / #比較組

狀態：完成

本次使用：把案例模型的使用前後拆成基準組與介入組，讓「是否更少錯選通道、漏跑命令與限制句缺漏」可以被觀察，而不是靠印象判斷。

核心判斷

1. 基準組只使用四步操作演算法、採用訊號板與既有完成回報，介入組加入案例模型、案例卡與補救回放。
2. 可觀察指標應聚焦錯選通道率、漏跑命令率、限制句缺漏率與案例卡補救率。
3. 比較組是 review 方法，不是統計實驗；不得宣稱因果改善。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪比較與介入回饋設計`。
2. 章節新增 `比較組`，定義基準組、介入組、錯選通道率、漏跑命令率、限制句缺漏率與案例卡補救率。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪創意思考契約矩陣比較與介入回饋設計`，並把 `#比較組` 對應到同一份契約文件。
4. 歷史 checkpoint：下一步：第 3 輪 / 創意思考 / #比較組。

優化說明

1. 比較組讓上一批案例模型有可觀察的使用前後對照。
2. 代價是仍需人工記錄觀察窗口；收益是下一批能把觀察欄位整理成可複製流程。
3. 目前只建立比較設計，不宣稱改善，也不新增產品遙測。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少比較與介入回饋設計會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 3 輪 / 創意思考 / #介入研究

狀態：完成

本次使用：把介入收斂成最小可執行動作，避免把案例模型變成厚重流程。

核心判斷

1. 最小介入應發生在改檔前與完成回報時，而不是等 review 結束才補紀錄。
2. 改檔前 60 秒案例模型選擇能讓操作者先承認風險層級；完成回報三欄補強能降低漏跑命令與限制句缺漏。
3. 介入停止條件必須保護低風險 UI 快速通道，也必須阻擋高風險契約被降級。

落地修改

1. `docs/pipeline-mode-contract.md` 的第五批章節新增 `介入研究`。
2. 介入研究寫入 `最小介入方案`、`改檔前 60 秒案例模型選擇`、`完成回報三欄補強`、`黃色或紅色補救回放` 與 `介入停止條件`。
3. `docs/hcs-plus-optimization-state.md` 將介入研究轉成系統應用方式：高風險或混合層改動先走介入組，低風險 UI 可保留快速通道。

優化說明

1. 這讓案例模型從分類工具變成改檔前的輕量介入。
2. 仍保留人工判斷與 pytest；介入只降低漏記與錯放風險，不替代測試。
3. 若介入流程拖慢低風險 UI，應回到短句回報，避免契約過度流程化。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_comparison_intervention_feedback_design`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_creative_comparison_intervention_feedback_is_recorded`

### 第 3 輪 / 創意思考 / #訪談調查

狀態：完成

本次使用：把操作者回饋壓成三題，檢查案例模型與案例卡是否真的可用，而不是只在文件中完整。

核心判斷

1. 回饋題要問能否在 2 分鐘內選出通道，因為選通道時間是第 3 輪一直追蹤的摩擦。
2. 詢問哪個案例模型最難判斷，可以暴露模型邊界不清或通道重疊。
3. 詢問案例卡是否暴露漏跑命令或限制句缺漏，可以檢查介入是否找到實際缺口。

落地修改

1. `docs/pipeline-mode-contract.md` 的第五批章節新增 `訪談調查` 與 `操作者回饋題`。
2. 回饋題寫入 `你能否在 2 分鐘內選出通道`、`哪個案例模型最難判斷`、`案例卡是否暴露漏跑命令或限制句缺漏`。
3. `docs/hcs-plus-optimization-state.md` 將 `#比較組/#介入研究/#訪談調查` 標記完成，並把下一批推進到 `#觀察研究/#研究複製`。

優化說明

1. 訪談調查讓比較設計有操作者回饋入口，但回饋答案只作為輔助證據。
2. 不新增產品遙測；也不得用回饋題答案替代 pytest 或人工 review。
3. 下一批需把觀察與複製流程寫清楚，讓同一設計能被下一位操作者重複使用。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少操作者回饋題會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪創意思考第六批

### 第 3 輪 / 創意思考 / #觀察研究

狀態：完成

本次使用：把比較組、介入方案與操作者回饋題轉成可填寫的觀察記錄欄位，讓觀察不只停在記憶、顏色訊號或完成回報印象。

核心判斷

1. 觀察研究需要固定欄位，否則錯選通道率、漏跑命令率與限制句缺漏率會在不同操作者之間失去口徑。
2. 觀察窗口、變更案例 ID、選定案例模型、實際選擇通道與實際執行命令，是追溯一個案例的最低資訊。
3. 完成回報三欄、觀察結果、操作者回饋摘要、補救行動與不可外推，能避免觀察紀錄被誤讀成改善證明。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪觀察與複製準則`。
2. 該章節新增 `觀察研究` 與 `觀察記錄欄位`，包含觀察窗口、變更案例 ID、選定案例模型、實際選擇通道、實際執行命令、完成回報三欄、觀察結果、操作者回饋摘要、補救行動與不可外推。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪創意思考契約矩陣觀察與複製準則`，並把 `#觀察研究` 對應到同一份契約文件。
4. 歷史 checkpoint：下一步：第 3 輪 / 創意思考 / #觀察研究。

優化說明

1. 觀察欄位讓第五批的比較與介入設計有固定資料入口。
2. 代價是每個觀察窗口需要多填欄位；收益是下一位操作者可以重做同一觀察。
3. 本章節仍不新增產品遙測，不替代 pytest 或人工 review，也不得宣稱改善。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少第 3 輪觀察與複製準則會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 3 輪 / 創意思考 / #研究複製

狀態：完成

本次使用：把觀察流程做成可複製檢查清單，讓下一位操作者不用讀完整 HCS 附件，也能用同一口徑記錄案例。

核心判斷

1. 可複製不是代表流程有效，而是代表下一位操作者能用同一觀察窗口定義、同一案例模型選項與同一指標口徑重做紀錄。
2. 同一介入停止條件與同一限制句能避免低風險 UI 被過度流程化，也避免高風險契約被錯誤降級。
3. 若沒有實際案例，必須記錄「本窗口未觀察到」，不得用假案例補位。

落地修改

1. `docs/pipeline-mode-contract.md` 的第六批章節新增 `研究複製`。
2. 複製檢查清單寫入同一觀察窗口定義、同一案例模型選項、同一指標口徑、同一介入停止條件與同一限制句。
3. `docs/hcs-plus-optimization-state.md` 將 `#觀察研究/#研究複製` 標記完成，並把下一批推進到第 3 輪 / 溝通思考 / `#受眾/#組成/#語意含義`。

優化說明

1. 這完成第 3 輪創意思考 17/17，將案例模型、比較介入與觀察複製收斂為一組可重做文件契約。
2. 剩餘風險轉向溝通思考：不同維護者是否能正確理解受眾、欄位組成與語意邊界。
3. 完整 HCS Plus 仍未完成；後續仍需第 3 輪溝通思考、互動思考與最終綜合優化。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_observation_replication_rules`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_creative_observation_replication_is_recorded`

## 第 3 輪創意思考收尾

- 已完成：17/17。
- 收尾結論：第 3 輪創意思考已把第 3 輪批判矩陣轉成學習入口、操作演算法、採用訊號、案例模型、比較介入、觀察欄位與複製準則。
- 邊界：不得宣稱 HCS Plus 完成、不得宣稱 runtime 安全、不得宣稱使用者理解改善、不得宣稱流程已改善。
- 下一步：第 3 輪 / 溝通思考 / #受眾。

## 第 3 輪溝通思考第一批

### 第 3 輪 / 溝通思考 / #受眾

狀態：完成

本次使用：把第 3 輪創意思考收尾後的觀察與複製準則，分成不同維護者能先進入的讀者角色。

核心判斷

1. 完整契約矩陣對低風險 UI 維護者太重，但對契約複檢維護者又不可省略。
2. 最小受眾分流需要四類：低風險 UI 維護者、報告呈現維護者、契約複檢維護者與觀察流程維護者。
3. 受眾分流只縮短閱讀路徑，不改變證據責任或通道升級條件。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪讀者語意入口`。
2. 該章節新增 `受眾` 表格，定義低風險 UI 維護者、報告呈現維護者、契約複檢維護者與觀察流程維護者。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪溝通思考契約矩陣讀者語意入口`，並把 `#受眾` 對應到同一份契約文件。
4. 歷史 checkpoint：下一步：第 3 輪 / 溝通思考 / #受眾。

優化說明

1. 受眾分流讓不同維護者先看自己最容易誤用的入口。
2. 代價是文件多一層角色分類；收益是低風險與高風險路徑不再互相拖慢。
3. 仍不新增產品遙測、不替代 pytest 或人工 review，也不改 runtime。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少第 3 輪讀者語意入口會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 3 輪 / 溝通思考 / #組成

狀態：完成

本次使用：把讀者入口拆成四步，避免受眾分類只停在名詞，而沒有可照做的閱讀順序。

核心判斷

1. 第一步要先判斷讀者角色，避免一開始就讀完整矩陣。
2. 第二步只讀對應入口，讓低風險 UI 維護者不被完整流程拖慢，高風險契約也不被誤放快速通道。
3. 第三步補齊觀察欄位，第四步用限制句收尾，讓閱讀入口仍保留證據與語意邊界。

落地修改

1. `docs/pipeline-mode-contract.md` 的讀者語意入口新增 `組成`。
2. 組成寫入 `第一步：先判斷讀者角色`、`第二步：只讀對應入口`、`第三步：補齊觀察欄位`、`第四步：用限制句收尾`。
3. `docs/hcs-plus-optimization-state.md` 將四步組成轉成系統應用方式。

優化說明

1. 組成讓讀者入口從角色表變成可執行順序。
2. 仍保留觀察欄位與限制句，避免簡化閱讀時也簡化責任。
3. 下一批需要把這四步整理成更清楚的章節導覽與專業核心主張。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_reader_semantic_entry`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_communication_audience_composition_semantics_is_recorded`

### 第 3 輪 / 溝通思考 / #語意含義

狀態：完成

本次使用：明確定義讀者角色、入口、觀察欄位、複製成功與低風險的語意邊界，避免讀者把入口誤讀成自動化或安全證明。

核心判斷

1. 讀者角色不是權限等級，不能被用來跳過證據或覆蓋紅色訊號。
2. 入口不是自動判斷器，觀察欄位不是 pytest，複製成功不是改善證明。
3. 低風險不代表低責任；即使走快速通道，也要保留限制句。

落地修改

1. `docs/pipeline-mode-contract.md` 的讀者語意入口新增 `語意含義`。
2. 語意含義寫入讀者角色不是權限等級、入口不是自動判斷器、觀察欄位不是 pytest、複製成功不是改善證明、低風險不代表低責任。
3. `docs/hcs-plus-optimization-state.md` 將 `#受眾/#組成/#語意含義` 標記完成，並把下一批推進到 `#組織結構/#專業性/#論點`。

優化說明

1. 語意邊界讓第 3 輪溝通思考不只改善閱讀，也避免新入口被誤用。
2. 這批仍只是文件契約，不新增產品遙測、不替代 pytest 或人工 review。
3. 完整 HCS Plus 仍未完成，下一批需整理章節結構、專業語氣與核心論點。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少語意邊界會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪溝通思考第二批

### 第 3 輪 / 溝通思考 / #組織結構

狀態：完成

本次使用：把讀者語意入口整理成可依序操作的章節導覽，讓維護者不用在角色、案例模型、觀察欄位與限制句之間來回找線索。

核心判斷

1. 讀者語意入口已經說明誰要讀什麼，但仍缺一條從入口到完成回報的章節順序。
2. 第 3 輪的組織結構應先定位讀者角色，再選通道與案例模型，接著補觀察欄位，最後用限制句與核心論點收尾。
3. 這個順序只改善維護導覽，不改變 pytest、人工 review 或高風險契約升級條件。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪維護導覽與核心論點`。
2. 章節導覽寫入先定位讀者角色、再選通道與案例模型、接著補觀察欄位、最後用限制句與核心論點收尾。
3. `docs/hcs-plus-optimization-state.md` 新增同名狀態章節，並將本批對應到第 3 輪溝通思考第二批。
4. 歷史 checkpoint：下一步：第 3 輪 / 溝通思考 / #組織結構。

優化說明

1. 組織結構讓前一批的受眾、組成與語意含義變成可照順序引用的維護導覽。
2. 代價是文件增加一個第 3 輪收斂章節；收益是後續完成回報更容易保持同一口徑。
3. 完整 HCS Plus 仍未完成，這批只完成第 3 輪溝通思考的第二組單項習慣。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少第 3 輪維護導覽與核心論點會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 3 輪 / 溝通思考 / #專業性

狀態：完成

本次使用：把維護回報語氣限制在可驗證範圍內，避免把文件契約、觀察窗口或測試綠燈誇大成安全證明。

核心判斷

1. 專業性不是把句子寫得更正式，而是準確說出證據層與未驗證範圍。
2. 維護語氣必須只描述觀察窗口、明列未跑命令、把紅色訊號說成停止條件、不得把測試綠燈寫成安全證明。
3. 若回報沒有說明限制，就容易把低風險快速通道誤讀成低責任，或把文件測試誤讀成 runtime 安全。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪維護導覽新增 `專業性` 與 `維護語氣` 表格。
2. 維護語氣明列四個要求：只描述觀察窗口、明列未跑命令、把紅色訊號說成停止條件、不得把測試綠燈寫成安全證明。
3. `docs/hcs-plus-optimization-state.md` 把專業性對應到同章節，並記錄下一批仍需整理成完成回報表達句型。

優化說明

1. 專業語氣降低了綠燈擴張、觀察替代 pytest 與紅色訊號被淡化的風險。
2. 本批沒有新增 runtime 驗證或產品遙測，因此回報必須明確說出未跑命令與不可宣稱範圍。
3. 這讓後續 review 更容易分辨「已記錄流程」和「已驗證行為」。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_maintenance_guide_core_argument`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_communication_structure_professional_argument_is_recorded`

### 第 3 輪 / 溝通思考 / #論點

狀態：完成

本次使用：把第 3 輪契約矩陣的核心主張收斂成一句可引用的目的，避免讀者以為文件越厚代表系統越安全。

核心判斷

1. 契約矩陣的目的不是提高文件厚度，而是讓低風險改動更快收尾、讓高風險契約更早升級、讓觀察紀錄可複製但不被誤讀。
2. 核心主張必須同時保留限制：不得宣稱改善，不得替代 pytest 或人工 review。
3. 若沒有明確論點，維護導覽會變成另一層形式流程，而不是幫助操作者做正確取捨。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪維護導覽新增 `論點` 與 `核心主張`。
2. 核心主張明確寫出低風險更快收尾、高風險更早升級、觀察紀錄可複製但不被誤讀。
3. `docs/hcs-plus-optimization-state.md` 將 `#組織結構/#專業性/#論點` 標記完成，並把下一批推進到 `#溝通設計/#表達/#媒介/#多媒體`。

優化說明

1. 論點讓第 3 輪溝通思考第二批有一個可引用的判斷核心。
2. 它把文件加厚的風險拉回維護效率與風險升級，而不是追求更多規則。
3. 完整 HCS Plus 仍未完成；後續仍需第 3 輪溝通思考第三批、互動思考與最終綜合優化。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少核心主張會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪溝通思考第三批

### 第 3 輪 / 溝通思考 / #溝通設計

狀態：完成

本次使用：把維護導覽與核心論點壓成可直接貼進回報的一頁摘要，讓操作者不用重寫完整矩陣也能保留改動層級、命令與限制。

核心判斷

1. 第二批已建立章節導覽與核心主張，但日常回報仍需要更短的溝通設計。
2. 一頁摘要必須先說本次改動層級、再列已跑命令與未跑命令、最後寫不得解讀為。
3. 短版回報只降低溝通摩擦，不改變 pytest、人工 review 或高風險契約升級條件。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪短版回報與媒介取捨`。
2. 該章節新增 `溝通設計` 與 `一頁摘要`，固定先說改動層級、再列命令、最後寫不得解讀為。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪溝通思考契約矩陣短版回報與媒介取捨`。
4. 歷史 checkpoint：下一步：第 3 輪 / 溝通思考 / #溝通設計。

優化說明

1. 溝通設計把維護導覽轉成可複製的一頁摘要。
2. 代價是仍要維護一段短版契約；收益是低風險回報不必重述完整矩陣。
3. 本批不新增 runtime、不新增圖像流程、不新增自動選測工具。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少第 3 輪短版回報會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 3 輪 / 溝通思考 / #表達

狀態：完成

本次使用：把完成回報收斂成固定句型，避免每次靠臨場表述而漏掉通道、命令或限制。

核心判斷

1. 句型要先固定責任邊界，再允許操作者填入具體內容。
2. 最小表達單位是「我選擇的通道是」、「我已執行的命令是」、「本次不得解讀為」。
3. 表達句型必須同時要求未跑命令原因，避免把未驗證證據層藏在綠燈後面。

落地修改

1. `docs/pipeline-mode-contract.md` 的短版回報章節新增 `表達` 與 `建議句型` 表格。
2. 表格固定通道、命令與限制三類句型。
3. `docs/hcs-plus-optimization-state.md` 把表達對應到同章節，並記錄下一批需檢查責任轉嫁風險。

優化說明

1. 建議句型讓完成回報可搜尋、可複製、可被測試鎖住。
2. 它避免回報只寫「測試通過」，卻沒有說明未跑命令或不得解讀為。
3. 句型仍不是證據本身，後續互動思考需要檢查倫理與責任邊界。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_short_report_media_choice`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_communication_short_report_media_choice_is_recorded`

### 第 3 輪 / 溝通思考 / #媒介

狀態：完成

本次使用：決定短版回報應使用文字與表格，而不是新增圖像流程或媒介切換。

核心判斷

1. 本契約需要被搜尋、複製、貼入 PR 與 HCS 狀態表，因此文字與表格優先。
2. 不要新增圖像流程，避免圖片讓操作者跳過已跑命令、未跑命令與不得解讀為。
3. 不要用多媒體替代限制句；任何示意只能輔助，不能取代文字限制。

落地修改

1. `docs/pipeline-mode-contract.md` 的短版回報章節新增 `媒介`。
2. 媒介規則寫入文字與表格優先、不要新增圖像流程、不要用多媒體替代限制句。
3. `docs/hcs-plus-optimization-state.md` 把媒介取捨記錄為第 3 輪溝通思考的落地決策。

優化說明

1. 媒介取捨把「容易引用」放在視覺表現之前。
2. 這避免為了讓矩陣更漂亮而削弱可測試、可搜尋與可審查性。
3. 若未來真的要加截圖或錄影，仍需保留文字版限制。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_short_report_media_choice`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_communication_short_report_media_choice_is_recorded`

### 第 3 輪 / 溝通思考 / #多媒體

狀態：完成

本次使用：明確暫不新增圖像或多媒體，避免把媒介升級誤當成系統驗證升級。

核心判斷

1. 多媒體會讓文件看起來更完整，但也可能讓操作者跳過文字限制與未跑命令。
2. 本階段應保留可搜尋文字，讓 pytest、review 與 HCS 狀態能直接鎖住關鍵語句。
3. 完成證據仍是 pytest 與人工 review；多媒體不得替代測試、lint、build 或 reviewer 判斷。

落地修改

1. `docs/pipeline-mode-contract.md` 的短版回報章節新增 `多媒體`。
2. 多媒體規則寫入暫不新增圖像或多媒體、保留可搜尋文字、保留 pytest 與人工 review。
3. `docs/hcs-plus-optimization-state.md` 將 `#溝通設計/#表達/#媒介/#多媒體` 標記完成，並把下一批推進到 `#倫理考量/#倫理勇氣/#倫理判斷`。

優化說明

1. 多媒體取捨完成第 3 輪溝通思考 10/10 收尾。
2. 溝通層已收斂成讀者入口、維護導覽、短版回報、句型與媒介限制。
3. 完整 HCS Plus 仍未完成；後續仍需第 3 輪互動思考與最終綜合優化。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少多媒體邊界與收尾會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪溝通思考收尾

- 已完成：10/10。
- 收尾結論：第 3 輪溝通思考已把契約矩陣整理成讀者語意入口、維護導覽、核心論點、一頁摘要、建議句型、文字表格媒介與多媒體限制。
- 邊界：不得宣稱 HCS Plus 完成、不得宣稱 runtime 安全、不得宣稱使用者理解改善、不得用多媒體替代 pytest 或人工 review。
- 下一步：第 3 輪 / 互動思考 / #倫理考量。

## 第 3 輪互動思考第一批

### 第 3 輪 / 互動思考 / #倫理考量

狀態：完成

本次使用：檢查短版回報是否可能被誤用成安全背書、責任轉嫁或高風險契約降級。

核心判斷

1. 第 3 輪溝通思考已把回報壓短，但越短的回報越容易被誤讀為安全保證。
2. 倫理底線需要明確禁止三件事：不得把短版回報寫成安全背書、不得把責任轉嫁給文件、工具或測試、不得用快速通道淡化高風險契約。
3. 倫理考量的作用是阻止錯誤宣稱，不是擴張流程或新增 runtime 行為。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪倫理阻擋與責任判斷`。
2. 該章節新增 `倫理考量` 與 `短版回報倫理底線`，寫入三條不得誤用規則。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪互動思考契約矩陣倫理阻擋與責任判斷`。
4. 歷史 checkpoint：下一步：第 3 輪 / 互動思考 / #倫理考量。

優化說明

1. 這讓短版回報從溝通工具變成有倫理邊界的維護契約。
2. 代價是回報時必須明確說出不能推論的範圍；收益是避免測試綠燈、文件完整或快速通道被誇大。
3. 本批仍不新增 runtime、不新增遙測、不新增自動選測工具。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少第 3 輪倫理阻擋會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 3 輪 / 互動思考 / #倫理勇氣

狀態：完成

本次使用：把必要時要說不寫成停止條件，避免高風險契約被短版回報包裝成可合併。

核心判斷

1. 倫理勇氣不是語氣強硬，而是在證據不足時停止合併、要求補證據或回到人工複檢。
2. 缺少 parser/prompt/template 證據時停止合併；報告文案像交易指令時先補責任邊界；高風險契約被降級時回到人工複檢。
3. 這些停止條件保護使用者與維護者，不是把所有低風險改動都升級成重流程。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪倫理章節新增 `倫理勇氣` 與 `必要時要說不`。
2. 必要時要說不寫入缺少 parser/prompt/template 證據時停止合併、報告文案像交易指令時先補責任邊界、高風險契約被降級時回到人工複檢。
3. `docs/hcs-plus-optimization-state.md` 將倫理勇氣對應到同章節，並把停止條件寫入系統應用方式。

優化說明

1. 說不規則把紅色訊號從提醒升級為實際阻擋。
2. 它避免短版回報被用來繞過高風險契約檢查。
3. 下一批需檢查這些停止條件在複雜因果裡是否仍可能被稀釋。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_ethics_stop_and_responsibility_judgment`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_ethics_courage_judgment_is_recorded`

### 第 3 輪 / 互動思考 / #倫理判斷

狀態：完成

本次使用：把允許回報、禁止回報與升級判斷分開，讓 reviewer 能判斷一句回報是否越界。

核心判斷

1. 道德判斷需要可操作的表格，而不是只說「保持謹慎」。
2. 允許回報是通道、命令、未跑命令與限制句；禁止回報是宣稱系統安全、使用者已理解或文件可以替代測試。
3. 升級判斷必須涵蓋低風險使用者行動暗示、混合層核心契約詞、文件或觀察宣稱 runtime 行為。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪倫理章節新增 `倫理判斷` 表格與 `升級判斷`。
2. 倫理判斷分成允許回報、禁止回報與三條升級規則。
3. `docs/hcs-plus-optimization-state.md` 將 `#倫理考量/#倫理勇氣/#倫理判斷` 標記完成，並把下一批推進到 `#複雜因果/#湧現特性/#分析層次`。

優化說明

1. 倫理判斷讓短版回報有可 review 的界線。
2. 它把「不能誇大」轉成具體禁止回報與升級判斷。
3. 完整 HCS Plus 仍未完成；後續仍需第 3 輪互動思考剩餘批次與最終綜合優化。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少允許/禁止/升級判斷會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪互動思考第二批

### 第 3 輪 / 互動思考 / #複雜因果

狀態：完成

本次使用：檢查局部綠燈如何造成系統性誤讀，避免把文件、前端測試或倫理阻擋規則外推成全系統安全。

核心判斷

1. 文件契約通過可能造成流程已安全的錯誤推論，但它只證明章節與狀態紀錄存在。
2. 前端測試通過可能造成 parser/prompt 已安全的錯誤推論，但它只保護前端顯示層。
3. 倫理阻擋存在可能造成高風險已被完全阻擋的錯誤推論，但規則仍需要 reviewer 啟用與補證據行動。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪系統因果與證據層次`。
2. 該章節新增 `複雜因果` 與 `局部綠燈因果圖`，列出三種局部訊號、錯誤推論與必要修正。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪互動思考契約矩陣系統因果與證據層次`。
4. 歷史 checkpoint：下一步：第 3 輪 / 互動思考 / #複雜因果。

優化說明

1. 複雜因果把第 3 輪倫理阻擋規則放回實際系統推論裡檢查。
2. 代價是回報時要更清楚區分證據來源；收益是降低單一綠燈被誇大成全局安全的機率。
3. 本批仍不新增 runtime、不新增遙測、不新增自動選測工具。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少第 3 輪系統因果與證據層次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

### 第 3 輪 / 互動思考 / #湧現特性

狀態：完成

本次使用：找出單次看似低風險的維護行為如何累積成新的系統風險。

核心判斷

1. 低風險快速通道累積成高風險語氣漂移：單次文案安全，不代表整體責任感不會變。
2. 案例卡增加但實際驗證減少：文件越完整，越可能讓操作者誤以為不必重跑測試。
3. 阻擋規則存在但 reviewer 不敢啟用：規則完整不代表壓力下真的會被使用。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪系統因果章節新增 `湧現特性`。
2. 湧現特性寫入快速通道累積、案例卡增加但驗證減少、阻擋規則不敢啟用三種風險。
3. `docs/hcs-plus-optimization-state.md` 把湧現特性對應到同章節，並記錄下一批需檢查放大或抑制回路。

優化說明

1. 湧現風險提醒我們不要只看單次 patch 的證據層。
2. 它避免把文件完整度誤當成實際驗證密度。
3. 下一批需把這些風險轉成維護網絡與系統動力學回路。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_system_causality_evidence_layers`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_causality_emergent_layers_is_recorded`

### 第 3 輪 / 互動思考 / #分析層次

狀態：完成

本次使用：把文件、測試、runtime 與使用者行為分層，要求每個宣稱都回到對應證據層。

核心判斷

1. 文件層只能證明章節、限制句、案例卡與狀態紀錄存在，不得用文件完整替代 runtime 驗證。
2. 測試層只能證明指定 pytest、lint 或靜態契約未被已知案例打破，不得用測試通過宣稱使用者理解。
3. runtime 層與使用者行為層需要自己的證據，不能被文件層或測試層反向替代。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪系統因果章節新增 `分析層次` 表格與層次規則。
2. 分析層次表區分文件層、測試層、runtime 層與使用者行為層。
3. `docs/hcs-plus-optimization-state.md` 將 `#複雜因果/#湧現特性/#分析層次` 標記完成，並把下一批推進到 `#網絡/#系統動力學/#系統圖像`。

優化說明

1. 分析層次讓完成回報先問「這句話屬於哪一層證據」。
2. 它把跨層宣稱改成明確升級驗證，而不是靠語氣克制。
3. 完整 HCS Plus 仍未完成；後續仍需第 3 輪互動思考剩餘批次與最終綜合優化。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少證據層次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪互動思考第三批

### 第 3 輪 / 互動思考 / #網絡

狀態：完成

本次使用：把前一批的證據層次接成維護網絡，讓完成回報能看見文件、測試、runtime、使用者行為與 reviewer 阻擋節點彼此牽動。

核心判斷

1. 文件層節點能降低記憶負擔，但也可能讓文件完整被誤讀成流程安全。
2. 測試層節點能防回退，但若跨層宣稱未升級驗證，仍可能被誤讀成 runtime 或使用者行為安全。
3. reviewer 阻擋節點是維護網絡的關鍵煞車；若阻擋沒有被啟用，前面的倫理與證據規則會留在紙面上。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪維護網絡與動態圖像`。
2. 該章節新增 `維護網絡` 表格，連接文件層節點、測試層節點、runtime 層節點、使用者行為層節點與 reviewer 阻擋節點。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪互動思考契約矩陣維護網絡與動態圖像`。
4. 歷史 checkpoint：下一步：第 3 輪 / 互動思考 / #網絡。

優化說明

1. 網絡視角讓「這句完成回報牽動哪個節點」變得可檢查。
2. 代價是回報需多做一層定位；收益是降低文件、測試與 runtime 證據彼此替代的風險。
3. 本批仍不新增 runtime、不新增遙測、不新增自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_maintenance_network_dynamics_image`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_network_dynamics_image_is_recorded`

### 第 3 輪 / 互動思考 / #系統動力學

狀態：完成

本次使用：檢查維護網絡裡哪些行為會互相放大或抑制，避免只列節點而不看回路。

核心判斷

1. 快速通道摩擦降低回路有助於低風險 UI 收尾，但累積語氣漂移時必須回到混合層或高風險檢查。
2. 案例卡形式化回路讓改動更可追溯，但若實際驗證減少，就會把形式完整誤當成安全。
3. 阻擋勇氣回路與跨層宣稱升級回路決定 reviewer 能否把「需要補證據」說出口。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪維護網絡章節新增 `系統動力學`。
2. 動態回路記錄快速通道摩擦降低回路、案例卡形式化回路、阻擋勇氣回路與跨層宣稱升級回路。
3. `docs/hcs-plus-optimization-state.md` 將這四個回路寫入系統應用方式與下一批缺口。

優化說明

1. 系統動力學讓回報不只問「有沒有規則」，也問「這個規則會不會在壓力下失效」。
2. 它把下一批的談判、說服與形塑行為焦點收斂到降低說不成本。
3. 本批仍維持文件與測試契約優先，不把回路做成自動審核器。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_maintenance_network_dynamics_image`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_network_dynamics_image_is_recorded`

### 第 3 輪 / 互動思考 / #系統圖像

狀態：完成

本次使用：把網絡與回路轉成維護者可照著走的操作圖像，避免系統圖只停在概念。

核心判斷

1. 系統圖像必須從證據層開始，否則很容易直接跳到「看起來已完成」。
2. 圖像要先連到網絡節點，再判斷動態回路，才能看出是否需要升級驗證。
3. 最後的決策不是「通過或不通過」，而是維持同層宣稱，或補 pytest、人工驗收、使用者行為證據後再跨層宣稱。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪維護網絡章節新增 `系統圖像` 四步路徑。
2. 四步路徑固定為先定位證據層、再連到網絡節點、接著判斷動態回路、最後決定維持同層宣稱或升級驗證。
3. `docs/hcs-plus-optimization-state.md` 將 `#網絡/#系統動力學/#系統圖像` 標記完成，並把下一批推進到 `#談判/#說服/#形塑行為`。

優化說明

1. 系統圖像讓修改如何應用到系統變成可重複流程：定位、連節點、看回路、決定是否升級。
2. 它明確限制不得把網絡圖像當成自動審核器，也不得替代 pytest 或人工 review。
3. 完整 HCS Plus 仍未完成；後續仍需第 3 輪互動思考剩餘批次與最終綜合優化。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少維護網絡、動態回路與系統圖像會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪互動思考第四批

### 第 3 輪 / 互動思考 / #談判

狀態：完成

本次使用：把 reviewer 阻擋節點轉成補證據協商，讓 reviewer 能接受同層成果，但不被迫放寬跨層證據標準。

核心判斷

1. 談判不是降低標準，而是把「不能合併」拆成可接受的選項：補跑命令、補限制句、拆分 patch 或降級宣稱。
2. 同層宣稱可以保留，跨層宣稱必須補證據或撤回。
3. review 對話需要可直接複製的句型，否則阻擋勇氣回路仍會卡在抽象規則。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪 review 對話與預設行為`。
2. 該章節新增 `談判` 與 `補證據協商` 表格，列出三種情境、可說句型與不可說法。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪互動思考契約矩陣 review 對話與預設行為`。
4. 歷史 checkpoint：下一步：第 3 輪 / 互動思考 / #談判。

優化說明

1. 補證據協商把「說不」轉成「怎樣可以同層合併或升級驗證」。
2. 代價是完成回報需更明確標示宣稱層級；收益是降低合併壓力下的標準滑坡。
3. 本批仍不新增 runtime、不新增遙測、不新增自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_review_dialogue_default_behavior`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_review_dialogue_default_behavior_is_recorded`

### 第 3 輪 / 互動思考 / #說服

狀態：完成

本次使用：把補證據要求說成共同完成工作，而不是否定改動者，降低 reviewer 說不成本。

核心判斷

1. 說服不是美化風險；它應該讓風險更容易被接受與處理。
2. 先承認已完成的證據，可以降低防衛反應；再指出缺口，才能避免把提醒說成抽象否定。
3. 最小可接受補證據讓 reviewer 的要求可執行，限制句則防止綠燈被誇大。

落地修改

1. `docs/pipeline-mode-contract.md` 的 review 對話章節新增 `說服`。
2. 說服路徑固定為先承認已完成的證據、再指出缺口、接著提出最小可接受補證據、最後寫不得解讀為。
3. `docs/hcs-plus-optimization-state.md` 將說服路徑寫入系統應用方式。

優化說明

1. 說服路徑讓 reviewer 不必在「放行」與「否定」之間二選一。
2. 它降低說不成本，但仍保留不得外推到 runtime、parser/prompt、使用者理解或投資判斷安全的限制。
3. 下一批需檢查多數壓力與高壓語氣是否會讓說服路徑失效。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_review_dialogue_default_behavior`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_review_dialogue_default_behavior_is_recorded`

### 第 3 輪 / 互動思考 / #形塑行為

狀態：完成

本次使用：把 review 對話轉成預設行為，讓完成回報自然填上宣稱層級、證據與限制，而不是靠臨場記憶。

核心判斷

1. 若沒有預設欄位，維護者很容易只回報「測試通過」，漏掉不得解讀為的限制。
2. 黃色與紅色訊號需要預設處理路徑，否則會被當成主觀感覺。
3. 跨層宣稱預設升級，可以把補證據變成常規流程，而不是 reviewer 個人對抗。

落地修改

1. `docs/pipeline-mode-contract.md` 的 review 對話章節新增 `形塑行為` 與 `預設行為` 表格。
2. 完成回報預設三欄固定為本次宣稱層級、已補證據、仍不得解讀為。
3. `docs/hcs-plus-optimization-state.md` 將 `#談判/#說服/#形塑行為` 標記完成，並把下一批推進到 `#從眾/#差異/#情緒智商`。

優化說明

1. 形塑行為讓好的 review 對話變成可重複格式，而不是只依賴 reviewer 當下的勇氣。
2. 它明確限制不得把好聽句型當成證據，也不得替代 pytest 或人工 review。
3. 完整 HCS Plus 仍未完成；後續仍需第 3 輪互動思考剩餘批次與最終綜合優化。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少 review 對話、預設行為與狀態推進會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪互動思考第五批

### 第 3 輪 / 互動思考 / #從眾

狀態：完成

本次使用：檢查 review 預設行為是否會被多數同意、前例綠燈、測試全綠或合併壓力推著走。

核心判斷

1. 多數同意不是證據；它最多表示團隊傾向，不能替代本次證據層。
2. 前例綠燈不是本次綠燈；每次改動仍要重新定位改動層級與網絡節點。
3. 測試全綠不是限制句；pytest 結果仍需說明不得解讀為什麼。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪防從眾、差異訊號與情緒調節`。
2. 該章節新增 `防從眾檢查` 表格，列出多數同意、前例綠燈、測試全綠與合併壓力的不可取代項與必要回應。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪互動思考契約矩陣防從眾、差異訊號與情緒調節`。
4. 歷史 checkpoint：下一步：第 3 輪 / 互動思考 / #從眾。

優化說明

1. 防從眾讓上一批的 review 對話不被團隊壓力稀釋。
2. 代價是完成回報需明確反駁常見捷徑；收益是降低綠燈與多數同意被誇大的風險。
3. 本批仍不新增 runtime、不新增遙測、不新增自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_conformity_difference_emotion_guard`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_conformity_difference_emotion_is_recorded`

### 第 3 輪 / 互動思考 / #差異

狀態：完成

本次使用：保留不同改動、證據、pipeline 模式與風險顏色之間的差異，避免為了快合併而壓平風險。

核心判斷

1. 高顯著性、混合層與低顯著性改動不能被寫成同一種安全程度。
2. 文件層、測試層、runtime 層與使用者行為層必須分開回報。
3. 黃色與紅色訊號若被寫成綠色，review 預設行為就會失去阻擋效果。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪防從眾章節新增 `差異訊號`。
2. 差異訊號列出改動層級差異、證據層差異、pipeline 模式差異與風險顏色差異。
3. `docs/hcs-plus-optimization-state.md` 將差異訊號寫入系統應用方式。

優化說明

1. 差異訊號讓完成回報保留重要不一致，而不是追求表面一致。
2. 它防止黃色與紅色訊號被語氣包裝成綠色。
3. 下一批需檢查誰有權力與責任維持這些差異。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_conformity_difference_emotion_guard`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_conformity_difference_emotion_is_recorded`

### 第 3 輪 / 互動思考 / #情緒智商

狀態：完成

本次使用：處理高壓 review 語氣，避免時程、回歸失敗、疲勞或權威催促讓限制句與補證據被省略。

核心判斷

1. 高壓情境下，人容易把「先過」當成解法；因此要先命名壓力來源。
2. 命名壓力後仍要回到預設三欄，而不是只做情緒安撫。
3. 最小補證據路徑能降低緊張感，但不能降低證據要求。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 輪防從眾章節新增 `高壓語氣處理`。
2. 高壓語氣處理固定為先命名壓力來源、再回到預設三欄、接著保留最小補證據路徑、最後用冷靜限制句收尾。
3. `docs/hcs-plus-optimization-state.md` 將 `#從眾/#差異/#情緒智商` 標記完成，並把下一批推進到 `#領導原則/#權力動態/#責任`。

優化說明

1. 情緒智商讓 review 在壓力下仍能維持證據層與限制句。
2. 它明確限制不得用趕時間取代證據層，也不得用情緒安撫取代 pytest 或人工 review。
3. 完整 HCS Plus 仍未完成；後續仍需第 3 輪互動思考剩餘批次與最終綜合優化。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少防從眾、差異訊號、情緒調節與狀態推進會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪互動思考第六批

### 第 3 輪 / 互動思考 / #領導原則

狀態：完成

本次使用：把防從眾與高壓語氣護欄轉成證據領導，避免 review 只由速度、資深度或合併窗口帶節奏。

核心判斷

1. 領導原則應該先保護證據層，而不是先保護合併速度。
2. 主責若不先宣告本次宣稱層級，review 會把分類責任推到最晚發現問題的人。
3. review 主導者需要保留升級權，合併者需要確認紅色與黃色訊號已處理。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪角色責任與權力護欄`。
2. 該章節新增 `證據領導`，要求主責先宣告本次宣稱層級、review 主導者維持升級權、合併者確認紅色與黃色訊號已處理。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪互動思考契約矩陣角色責任與權力護欄`。
4. 歷史 checkpoint：下一步：第 3 輪 / 互動思考 / #領導原則。

優化說明

1. 證據領導讓 review 領導權服務宣稱層級與補證據，而不是服務快合併。
2. 代價是完成回報要多說明角色責任；收益是錯放責任時能追溯到具體角色。
3. 本批仍維持文件與測試契約，不新增 runtime、遙測、圖像流程或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_role_responsibility_power_guard`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_role_responsibility_power_is_recorded`

### 第 3 輪 / 互動思考 / #權力動態

狀態：完成

本次使用：檢查合併權限、資深度與權威催促如何影響證據層，並把權力壓力轉成可引用的護欄。

核心判斷

1. 合併權限不能覆蓋紅色訊號；紅色訊號仍要停止合併、補證據或拆分 patch。
2. 資深度不能把前例綠燈變成本次通行證。
3. 低權限操作者需要能引用契約要求補證據，否則防從眾規則會被權力差距稀釋。

落地修改

1. `docs/pipeline-mode-contract.md` 的角色責任章節新增 `權力動態`。
2. 權力動態寫入合併權限不能覆蓋紅色訊號、資深度不能把前例綠燈變成通行證。
3. 權力動態允許低權限操作者引用契約要求補證據，並要求權威催促回到預設三欄。

優化說明

1. 權力護欄讓證據層有明確優先級，避免權限、資深度或催促取代補證據。
2. 這不新增正式權限模型；它只定義 review 對話中的最低證據邊界。
3. 下一批需檢查這套權力護欄是否過度官僚。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_role_responsibility_power_guard`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_role_responsibility_power_is_recorded`

### 第 3 輪 / 互動思考 / #責任

狀態：完成

本次使用：把改動者、reviewer 與合併者的完成責任拆開，避免責任被轉嫁給文件、工具或測試。

核心判斷

1. 改動者負責本次宣稱層級與已補證據。
2. reviewer 負責仍不得解讀為，並核對黃色、紅色與跨層宣稱。
3. 合併者負責未跑命令與剩餘風險，不能把風險留給文件或工具代背。

落地修改

1. `docs/pipeline-mode-contract.md` 的角色責任章節新增 `責任` 表格。
2. 責任表格拆分改動者、reviewer 與合併者的責任與完成回報必留內容。
3. `docs/hcs-plus-optimization-state.md` 將第 3 輪 `#領導原則/#權力動態/#責任` 標記完成，並把下一批推進到 `#自我覺察/#制定策略`。

優化說明

1. 角色責任讓問題可追溯到具體環節，而不是籠統說文件沒有寫清楚。
2. 它明確限制不得把責任轉嫁給文件、工具或測試，也不得替代 pytest 或人工 review。
3. 完整 HCS Plus 仍未完成；後續需用自我覺察與制定策略檢查是否過度官僚，並收尾第 3 輪互動思考。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少角色責任、權力護欄與狀態推進會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪互動思考第七批

### 第 3 輪 / 互動思考 / #自我覺察

狀態：完成

本次使用：檢查角色責任與權力護欄是否會反過來增加官僚成本，並限制契約矩陣自身的副作用。

核心判斷

1. 角色責任不是流程越多越好；它應該只在風險、跨層宣稱與證據不足時增加摩擦。
2. 低風險同層改動若也被拖進完整責任審核，會讓契約矩陣變成形式簽核。
3. 文件完整不等於自動審核；完整矩陣仍不能替代 pytest 或人工 review。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣第 3 輪自我稽核與收尾策略`。
2. 該章節新增 `輕量使用邊界`，把低風險同層改動、黃色訊號與紅色訊號分成不同摩擦等級。
3. `docs/hcs-plus-optimization-state.md` 新增 `第 3 輪互動思考契約矩陣自我稽核與收尾策略`。
4. 歷史 checkpoint：下一步：第 3 輪 / 互動思考 / #自我覺察。

優化說明

1. 自我稽核讓角色責任保持輕量，不把低風險同層改動拖成重流程。
2. 代價是仍需人工判斷風險顏色；收益是避免契約矩陣變成假自動化或形式簽核。
3. 本批仍不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_round3_self_audit_and_closing_strategy`
- `tests/test_hcs_plus_state.py::test_hcs_plus_round3_interaction_self_audit_strategy_is_recorded`

### 第 3 輪 / 互動思考 / #制定策略

狀態：完成

本次使用：定義第 3 輪互動思考的收尾條件，並把下一步從單項輪巡推進到三習慣綜合優化。

核心判斷

1. 第 3 輪互動思考已補齊倫理、系統因果、維護網絡、review 對話、防從眾、角色責任與自我稽核。
2. 最合理的下一步不是繼續堆疊互動規則，而是用高影響三習慣整合整個專案契約。
3. 綜合優化候選先採用 #可驗證性、#溝通設計、#系統圖像，因為它們分別對應證據、使用者理解與系統關係。

落地修改

1. `docs/pipeline-mode-contract.md` 的自我稽核章節新增 `第 3 輪互動思考收尾條件`。
2. `docs/hcs-plus-optimization-state.md` 將第 3 輪 `#自我覺察/#制定策略` 標記完成，並新增 `綜合 / 三習慣綜合優化 / #可驗證性、#溝通設計、#系統圖像` 下一批。
3. 本嚴格輪巡附件新增第 3 輪互動思考收尾 checkpoint，明確保留 HCS Plus 尚未完成。

優化說明

1. 制定策略讓第 3 輪互動思考以 20/20 單項完成收尾。
2. 它把下一步轉為整體收斂，而不是繼續擴張局部規則。
3. 不得宣稱 HCS Plus 完成；完整流程仍需後續綜合優化。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少自我稽核、收尾策略與狀態推進會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 第 3 輪互動思考收尾

已完成：20/20

已改善內容：

1. 把短版回報倫理、系統因果、維護網絡、review 對話、防從眾、角色責任與自我稽核串成可追溯的契約矩陣。
2. 把證據層、角色責任、限制句、風險顏色與完成回報三欄寫成可測試文件契約。
3. 把互動思考最後缺口收斂到三習慣綜合優化。

剩餘風險：

1. 契約矩陣仍是文件與測試契約，不是自動審核器。
2. 未新增 runtime、遙測或自動選測工具；高風險改動仍需人工 review 與對應 pytest。
3. HCS Plus 尚未完成，仍需三習慣綜合優化。

下一步：三習慣綜合優化 / #可驗證性

## 三習慣綜合優化第 1 次

### 綜合 / 三習慣綜合優化第 1 次 / #可驗證性

狀態：完成

本次使用：把三輪累積的契約矩陣收斂成驗證閘門，避免完成宣稱只靠文件存在或測試綠燈外推。

核心判斷

1. 完成宣稱必須回到同層證據；文件契約只支持文件層宣稱。
2. 高顯著性機器契約改動仍要跑 parser、prompt、template 與 audit 回歸。
3. 不跑命令不能宣稱通過；只能明列未跑命令與剩餘風險。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣綜合優化第 1 次：驗證、溝通與系統圖像收斂`。
2. 該章節新增 `驗證閘門`，分出低風險同層改動、報告呈現層、高顯著性機器契約與維運決策層。
3. `docs/hcs-plus-optimization-state.md` 新增 `三習慣綜合優化第 1 次：驗證、溝通與系統圖像收斂`。
4. 歷史 checkpoint：下一步：三習慣綜合優化 / #可驗證性。

優化說明

1. 可驗證性把「已完成」收斂成命令、證據層與限制句。
2. 代價是完成回報需要更明確列出未跑命令；收益是避免跨層安全宣稱。
3. 本批不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_verification_communication_system_view`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_verification_communication_system_view_is_recorded`

### 綜合 / 三習慣綜合優化第 1 次 / #溝通設計

狀態：完成

本次使用：把完成回報設計成維護者能快速判斷證據範圍、限制與下一步的格式。

核心判斷

1. 完成回報若先講結果，容易讓讀者忽略證據層。
2. 最小可用格式應先說本次宣稱層級，再列已補證據與仍不得解讀為。
3. 下一個可執行行動能避免綜合優化停在抽象原則。

落地修改

1. `docs/pipeline-mode-contract.md` 的綜合優化章節新增 `完成回報格式`。
2. 格式固定為本次宣稱層級、已補證據、仍不得解讀為、下一個可執行行動。
3. `docs/hcs-plus-optimization-state.md` 將溝通設計對應到同章節的完成回報格式。

優化說明

1. 溝通設計讓回報先限制宣稱範圍，再呈現成果。
2. 它保留低風險同層改動的輕量三欄，不把所有改動拖進完整矩陣。
3. 下一批需用受眾視角再檢查不同維護者是否能快速找到自己該讀的段落。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_verification_communication_system_view`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_verification_communication_system_view_is_recorded`

### 綜合 / 三習慣綜合優化第 1 次 / #系統圖像

狀態：完成

本次使用：把前端、報告、機器契約與維運決策分成不同系統層，避免局部證據被外推成全系統安全。

核心判斷

1. 前端顯示層、報告呈現層、機器契約層與維運決策層需要不同證據入口。
2. 同層證據只能支持同層宣稱；跨層宣稱必須升級驗證。
3. 系統圖像應幫助維護者選證據，不應變成另一張形式圖表。

落地修改

1. `docs/pipeline-mode-contract.md` 的綜合優化章節新增 `系統圖像收斂`。
2. 系統圖像收斂列出四層：前端顯示層、報告呈現層、機器契約層、維運決策層。
3. `docs/hcs-plus-optimization-state.md` 將第一個綜合批次標記完成，並把下一批推進到 `#證據基礎/#受眾/#責任`。

優化說明

1. 系統圖像收斂讓證據入口與改動層一致。
2. 它保留人工 review 與 pytest 的位置，不把文件圖像當成自動審核。
3. 不得把綜合優化第 1 次解讀為 HCS Plus 完成；完成定義仍要求後續綜合優化。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少綜合優化第 1 次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 三習慣綜合優化第 2 次

### 綜合 / 三習慣綜合優化第 2 次 / #證據基礎

狀態：完成

本次使用：把第一批的驗證閘門往前補證據來源分級，避免文件、測試、人工 review 與未跑命令被混成同一種綠燈。

核心判斷

1. 直接證據只能支持它實際覆蓋的同層行為。
2. 間接證據只能支持流程或文件存在，不能外推到 runtime 或使用者理解。
3. 缺口證據與未跑命令如果不被明列，就會被完成敘述吞掉。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣綜合優化第 2 次：證據來源、讀者角色與責任承接`。
2. 該章節新增 `證據來源分級`，區分直接證據、間接證據、缺口證據與未跑命令。
3. `docs/hcs-plus-optimization-state.md` 新增 `三習慣綜合優化第 2 次：證據來源、讀者角色與責任承接`。
4. 歷史 checkpoint：下一步：三習慣綜合優化第 2 次 / #證據基礎。

優化說明

1. 證據基礎讓第一批的驗證閘門不只列命令，也說清楚證據等級。
2. 代價是完成回報需明列缺口；收益是未跑命令不能消失。
3. 本批仍不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_evidence_audience_responsibility`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_evidence_audience_responsibility_is_recorded`

### 綜合 / 三習慣綜合優化第 2 次 / #受眾

狀態：完成

本次使用：把第 1 批的完成回報格式轉成讀者入口，避免低風險 UI 維護者被迫讀完整機器契約，也避免高風險維護者只看短版結論。

核心判斷

1. 低風險 UI 維護者需要輕量三欄與前端顯示層證據。
2. 報告呈現維護者與機器契約維護者需要保留不同證據入口。
3. 合併者需要同時看到證據來源、讀者角色、未跑命令與剩餘風險。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 2 次綜合優化章節新增 `讀者角色分流`。
2. 分流列出低風險 UI 維護者、報告呈現維護者、機器契約維護者、維運決策維護者與合併者。
3. `docs/hcs-plus-optimization-state.md` 將受眾對應到同章節的讀者角色分流。

優化說明

1. 受眾分流降低閱讀成本，但不降低證據要求。
2. 不同讀者先讀不同入口，仍需保留不得外推到 runtime、安全或投資判斷的限制。
3. 下一批需用學習科學檢查入口是否真的容易學會。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_evidence_audience_responsibility`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_evidence_audience_responsibility_is_recorded`

### 綜合 / 三習慣綜合優化第 2 次 / #責任

狀態：完成

本次使用：把證據來源與讀者角色轉成責任承接，避免未跑命令、剩餘風險或讀者誤讀在交接時消失。

核心判斷

1. 改動者負責證據來源與宣稱層級。
2. reviewer 負責讀者是否會誤讀，尤其是低風險入口被外推到高風險層。
3. 合併者負責未跑命令與剩餘風險是否可接受。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 2 次綜合優化章節新增 `責任承接`。
2. 責任承接寫入改動者、reviewer、合併者三方責任。
3. `docs/hcs-plus-optimization-state.md` 將下一批推進到三習慣綜合優化第 3 次 / `#偏誤降低`、`#學習科學`、`#制定策略`。

優化說明

1. 責任承接讓未跑命令不能消失，剩餘風險必須留到下一步。
2. 不得把使用者理解、安全或投資判斷外推。
3. 不得把綜合優化第 2 次解讀為 HCS Plus 完成；下一批需要控制責任規則繼續膨脹的風險。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少綜合優化第 2 次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 三習慣綜合優化第 3 次

### 綜合 / 三習慣綜合優化第 3 次 / #偏誤降低

狀態：完成

本次使用：把第 2 次的證據、讀者與責任矩陣加上誤用偵測，避免矩陣被拿來打勾、漂白證據、逃避升級或繼續膨脹。

核心判斷

1. 表格打勾偏誤會讓每欄都有文字，卻沒有任何同層證據支持宣稱。
2. 證據漂白偏誤會把文件契約、案例卡或觀察紀錄寫成直接證據。
3. 升級逃避與流程膨脹會同時出現：一邊不補高風險命令，一邊新增更多低價值欄位。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣綜合優化第 3 次：偏誤防線、速學入口與策略收斂`。
2. 該章節新增 `偏誤防線`，列出表格打勾偏誤、證據漂白偏誤、升級逃避偏誤與流程膨脹偏誤。
3. `docs/hcs-plus-optimization-state.md` 新增 `三習慣綜合優化第 3 次：偏誤防線、速學入口與策略收斂`。
4. 歷史 checkpoint：下一步：三習慣綜合優化第 3 次 / #偏誤降低。

優化說明

1. 偏誤降低讓第 2 次矩陣不只要求證據，也能辨識矩陣本身被誤用。
2. 代價是 reviewer 多一個偏誤掃描步驟；收益是避免空表格被當成完成證據。
3. 本批仍不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_bias_learning_strategy`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_bias_learning_strategy_is_recorded`

### 綜合 / 三習慣綜合優化第 3 次 / #學習科學

狀態：完成

本次使用：把完整契約矩陣轉成可快速啟動的速學入口，降低新維護者第一次使用時的記憶負擔。

核心判斷

1. 維護者一開始不需要背完整矩陣，只需要知道先定位改動層級。
2. 90 秒內應能分清證據來源與讀者角色，否則矩陣會變成阻力。
3. 5 分鐘復盤應產出限制句、未跑命令與下一個可執行行動，而不是新的抽象原則。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 次綜合優化章節新增 `速學入口`。
2. 速學入口分成 10 秒定位、90 秒分流、5 分鐘復盤。
3. `docs/hcs-plus-optimization-state.md` 將學習科學對應到同章節的速學入口。

優化說明

1. 學習科學把契約矩陣從完整規則書降成可先用的三段入口。
2. 速學入口不得替代完整契約；遇到高顯著性或跨層宣稱仍要回到完整矩陣。
3. 下一批需用效用檢查速學入口是否真的比完整矩陣更省成本。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_bias_learning_strategy`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_bias_learning_strategy_is_recorded`

### 綜合 / 三習慣綜合優化第 3 次 / #制定策略

狀態：完成

本次使用：把偏誤防線與速學入口收斂成策略規則，決定哪些情境保持輕量、哪些必須升級、哪些規則必須刪減。

核心判斷

1. 低風險維持輕量，才能避免契約矩陣拖慢同層小改。
2. 高顯著性必須升級，才能避免速學入口被拿來逃避 parser、prompt、template 或 audit 回歸。
3. 策略膨脹必須刪減，否則綜合優化會服務文件本身而不是服務專案。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 3 次綜合優化章節新增 `策略收斂`。
2. 策略收斂固定低風險維持輕量、高顯著性必須升級、未跑命令留到下一步、策略膨脹必須刪減。
3. `docs/hcs-plus-optimization-state.md` 將進度推進到三習慣綜合優化第 4 次 / `#目的`、`#效用`、`#合理性`。

優化說明

1. 制定策略讓第 3 次綜合優化以規則刪減與升級判斷收尾。
2. 不得把矩陣完成誤讀為證據充分，也不得把速學入口替代完整契約。
3. 不得把綜合優化第 3 次解讀為 HCS Plus 完成；下一批需要回到目的、效用與合理性。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少綜合優化第 3 次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 三習慣綜合優化第 4 次

### 綜合 / 三習慣綜合優化第 4 次 / #目的

狀態：完成

本次使用：把前 3 次綜合優化重新綁回股票研究系統的核心目標，避免契約矩陣服務文件本身。

核心判斷

1. 契約矩陣的目的不是增加文件厚度，而是讓操作者選對分析模式並理解報告層級。
2. 使用者決策用途、維護者合併判斷與契約安全邊界需要同時保留。
3. 目的不明的規則會讓矩陣膨脹，並削弱低風險通道的效率。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣綜合優化第 4 次：目標校準、效用門檻與合理性審核`。
2. 該章節新增 `目標校準`，把矩陣規則連回股票研究系統核心目標、使用者決策用途、維護者合併判斷與契約安全邊界。
3. `docs/hcs-plus-optimization-state.md` 新增 `三習慣綜合優化第 4 次：目標校準、效用門檻與合理性審核`。
4. 歷史 checkpoint：下一步：三習慣綜合優化第 4 次 / #目的。

優化說明

1. 目的校準讓每條規則先說明服務哪個系統目標。
2. 代價是新增規則需要說清楚目的；收益是目的不明不能加入矩陣。
3. 本批仍不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_goal_utility_reasonability`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_goal_utility_reasonability_is_recorded`

### 綜合 / 三習慣綜合優化第 4 次 / #效用

狀態：完成

本次使用：把矩陣規則的保留條件改成效用門檻，只有能降低錯選模式、漏跑命令、跨層外推或維護成本的規則才保留。

核心判斷

1. 規則若不能降低錯選模式，就只是重複模式名稱。
2. 規則若不能降低漏跑命令或跨層外推，就不能支撐完成宣稱。
3. 規則若不能降低維護成本，就必須有更強的風險降低證據。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 4 次綜合優化章節新增 `效用門檻`。
2. 效用門檻固定四項：降低錯選模式、降低漏跑命令、降低跨層外推、降低維護成本。
3. `docs/hcs-plus-optimization-state.md` 將效用對應到同章節的效用門檻。

優化說明

1. 效用門檻讓矩陣規則有保留理由，而不是只因為看起來完整就留下。
2. 不得把效用推論寫成已證明改善；目前只作為文件契約與 review 判斷。
3. 下一批需用決策樹把效用門檻轉成實際分流。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_goal_utility_reasonability`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_goal_utility_reasonability_is_recorded`

### 綜合 / 三習慣綜合優化第 4 次 / #合理性

狀態：完成

本次使用：把目的與效用轉成合理性審核，要求高成本規則通過必要性、比例性、可驗證性與可逆性。

核心判斷

1. 高成本規則必須有證據，不能只用「更安全」當理由。
2. 低風險同層改動需要比例性，不能被完整矩陣拖慢。
3. 可逆性讓流程膨脹能被刪減，而不是一路累積。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 4 次綜合優化章節新增 `合理性審核`。
2. 合理性審核固定必要性、比例性、可驗證性與可逆性。
3. `docs/hcs-plus-optimization-state.md` 將進度推進到三習慣綜合優化第 5 次 / `#限制條件`、`#決策樹`、`#最佳化`。

優化說明

1. 合理性讓低效用規則必須刪減，高成本規則必須有證據，目的不明不能加入矩陣。
2. 不得讓契約矩陣服務文件本身，也不得把效用推論寫成已證明改善。
3. 不得把綜合優化第 4 次解讀為 HCS Plus 完成；下一批需把限制、決策與最佳化落成分流。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少綜合優化第 4 次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 三習慣綜合優化第 5 次

### 綜合 / 三習慣綜合優化第 5 次 / #限制條件

狀態：完成

本次使用：把目的、效用與合理性轉成限制邊界，清楚分出哪些情境不能做、哪些能輕量、哪些必須升級、哪些要停用。

核心判斷

1. 硬限制要阻止新增 runtime、遙測、自動選測工具，以及文件替代 pytest 或人工 review。
2. 軟限制保留低風險輕量通道，但仍要留宣稱層級、證據與限制句。
3. 升級限制與停用限制能避免高顯著性改動被降級，或低效用規則繼續膨脹。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣綜合優化第 5 次：限制邊界、分流決策與成本最佳化`。
2. 該章節新增 `限制邊界`，列出硬限制、軟限制、升級限制與停用限制。
3. `docs/hcs-plus-optimization-state.md` 新增 `三習慣綜合優化第 5 次：限制邊界、分流決策與成本最佳化`。
4. 歷史 checkpoint：下一步：三習慣綜合優化第 5 次 / #限制條件。

優化說明

1. 限制條件把「不得」類規則變成可操作邊界，而不是散落在各章的提醒。
2. 代價是規則前置判斷變多；收益是硬限制不再被輕量通道稀釋。
3. 本批仍不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_constraints_decision_optimization`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_constraints_decision_optimization_is_recorded`

### 綜合 / 三習慣綜合優化第 5 次 / #決策樹

狀態：完成

本次使用：把限制邊界排成四步分流決策，讓 reviewer 不需要靠記憶整份矩陣來決定下一步。

核心判斷

1. 分流必須先判斷改動層級，否則低風險與高顯著性改動會混在一起。
2. 顯著性與證據缺口決定是否升級、拆分或刪減。
3. 決策樹只能輔助人工判斷，不是自動選測工具。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 5 次綜合優化章節新增 `分流決策`。
2. 分流決策固定四步：判斷改動層級、判斷顯著性、判斷證據缺口、選擇輕量/升級/拆分/刪減。
3. `docs/hcs-plus-optimization-state.md` 將決策樹對應到同章節的分流決策。

優化說明

1. 決策樹把目的、效用與合理性落成順序，降低 reviewer 的臨場判斷負擔。
2. 不得把決策樹當成自動選測工具；命令與人工 review 仍由改動層級與證據缺口決定。
3. 下一批需用情境脈絡檢查同一決策在不同維護情境下是否仍適用。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_constraints_decision_optimization`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_constraints_decision_optimization_is_recorded`

### 綜合 / 三習慣綜合優化第 5 次 / #最佳化

狀態：完成

本次使用：把矩陣成本最佳化明文化，保留能降低風險的規則，刪除或延後低效用、重複或無證據規則。

核心判斷

1. 最佳化不是降低標準，而是刪掉不降低風險的成本。
2. 保留低風險輕量通道與高顯著性升級，是同一套成本最佳化的一體兩面。
3. 無證據規則應延後，不應寫成已完成或已證明有效。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 5 次綜合優化章節新增 `成本最佳化`。
2. 成本最佳化固定四種動作：保留低風險輕量通道、合併重複規則、刪除低效用規則、延後無證據規則。
3. `docs/hcs-plus-optimization-state.md` 將進度推進到三習慣綜合優化第 6 次 / `#來源品質`、`#情境脈絡`、`#批判`。

優化說明

1. 最佳化讓矩陣能縮短而不是一路增厚。
2. 不得為了最佳化而降低高顯著性驗證，也不得把決策樹當成自動選測工具。
3. 不得把綜合優化第 5 次解讀為 HCS Plus 完成；下一批需檢查來源品質、情境脈絡與批判反證。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少綜合優化第 5 次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 三習慣綜合優化第 6 次

### 綜合 / 三習慣綜合優化第 6 次 / #來源品質

狀態：完成

本次使用：把矩陣可引用的來源分級，避免歷史紀錄、文件契約或模型自信語氣被誤寫成完成證據。

核心判斷

1. 高可信來源只能支持它實際覆蓋的同層行為。
2. 可用但有限來源可以支持流程存在，不能替代 pytest 或人工 review。
3. 不得作為完成證據與缺口來源必須限制宣稱，而不是被改寫成綠燈。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣綜合優化第 6 次：來源分級、適用情境與批判反證`。
2. 該章節新增 `來源分級`，分出高可信來源、可用但有限來源、不得作為完成證據與缺口來源。
3. `docs/hcs-plus-optimization-state.md` 新增 `三習慣綜合優化第 6 次：來源分級、適用情境與批判反證`。
4. 歷史 checkpoint：下一步：三習慣綜合優化第 6 次 / #來源品質。

優化說明

1. 來源品質讓第 5 次分流決策有證據等級依據。
2. 代價是完成回報需更精確標明來源；收益是歷史紀錄不能被當成新證據。
3. 本批仍不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_source_context_critique`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_source_context_critique_is_recorded`

### 綜合 / 三習慣綜合優化第 6 次 / #情境脈絡

狀態：完成

本次使用：把同一條矩陣規則放回具體維護情境，避免低風險文件規則被外推成 runtime、parser 或使用者理解保證。

核心判斷

1. 低風險同層文件改動可以走輕量入口，但不能支持 runtime 或使用者理解。
2. 報告呈現或使用者語意改動要檢查交易指令、安全背書與投資判斷保證。
3. 機器契約、高顯著性與維運決策情境必須有對應回歸、review 或排程風險紀錄。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 6 次綜合優化章節新增 `適用情境`。
2. 適用情境分成低風險同層文件改動、報告呈現或使用者語意改動、機器契約或高顯著性改動、維運決策或排程風險改動。
3. `docs/hcs-plus-optimization-state.md` 的第 6 次狀態章節新增系統應用方式，要求先標明來源品質，再確認適用情境。

優化說明

1. 情境脈絡把第 5 次的分流決策從抽象層級拉回實際維護入口。
2. 情境不符必須升級或拆分，不能把文件同層規則擴張到高顯著性改動。
3. 下一批需用信賴區間描述不同情境下的信心邊界。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_source_context_critique`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_source_context_critique_is_recorded`

### 綜合 / 三習慣綜合優化第 6 次 / #批判

狀態：完成

本次使用：每次新增、保留或合併規則前，先用反證問題檢查它在哪裡可能失效、證據是否只支持文件存在，以及是否有更小的限制句。

核心判斷

1. 失效情境若碰到高顯著性或跨層宣稱，必須改走升級或拆分。
2. 證據若只支持文件存在，來源品質不足必須降級宣稱。
3. 若有更小限制句或刪減方式，優先縮小規則而不是擴張矩陣。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 6 次綜合優化章節新增 `批判反證`。
2. 批判反證固定三個反問，並明訂情境不符、來源品質不足與反證未處理時的處理方式。
3. `docs/hcs-plus-optimization-state.md` 將三習慣綜合優化第 6 次標為完成，並把下一批推進到 `#估算`、`#信賴區間`、`#詮釋框架`。

優化說明

1. 批判反證防止契約矩陣只因形式完整就繼續膨脹。
2. 反證未處理不得合併高顯著性規則，也不得把歷史紀錄當成新證據。
3. 不得把綜合優化第 6 次解讀為 HCS Plus 完成；下一批需校準把握程度與解讀框架。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少綜合優化第 6 次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 三習慣綜合優化第 7 次

### 綜合 / 三習慣綜合優化第 7 次 / #估算

狀態：完成

本次使用：把完成宣稱先估成高把握、中把握、低把握或不得宣稱，避免有限證據被寫成確定結論。

核心判斷

1. 高把握只能來自覆蓋同層行為的高可信來源。
2. 中把握必須列出缺口與未跑命令，不能寫成完全完成。
3. 低把握不得升格為完成，不得宣稱等級只能改成限制句或下一步。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣綜合優化第 7 次：把握校準、信心邊界與解讀框架`。
2. 該章節新增 `把握估算`，分出高把握、中把握、低把握與不得宣稱。
3. `docs/hcs-plus-optimization-state.md` 新增 `三習慣綜合優化第 7 次：把握校準、信心邊界與解讀框架`。
4. 歷史 checkpoint：下一步：三習慣綜合優化第 7 次 / #估算。

優化說明

1. 估算把第 6 次的來源品質轉成回報語氣，降低過度宣稱。
2. 代價是完成回報多一步把握標記；收益是弱證據不能被包裝成完成。
3. 本批仍不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_estimation_confidence_interpretation`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_estimation_confidence_interpretation_is_recorded`

### 綜合 / 三習慣綜合優化第 7 次 / #信賴區間

狀態：完成

本次使用：把每個完成宣稱的信心邊界寫清楚，避免文件層、測試層、runtime 層與使用者行為層互相外推。

核心判斷

1. 適用層級必須標示是文件層、測試層、runtime 層、使用者行為層或維運決策層。
2. 證據覆蓋必須標示已跑命令、已檢 diff、已 review、已渲染、已抽樣或仍未驗證。
3. 剩餘不確定必須明列，信心邊界不得跨過未測層。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 7 次綜合優化章節新增 `信心邊界`。
2. 信心邊界要求同時列出適用層級、證據覆蓋與剩餘不確定。
3. `docs/hcs-plus-optimization-state.md` 的第 7 次狀態章節新增系統應用方式，要求完成宣稱先填把握估算，再填信心邊界。

優化說明

1. 信賴區間讓完成宣稱不再只有單點結論，而有可檢查的邊界。
2. 這會限制文件層結果被推成 runtime 或使用者理解證明。
3. 下一批需用描述統計整理完成與缺口分布。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_estimation_confidence_interpretation`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_estimation_confidence_interpretation_is_recorded`

### 綜合 / 三習慣綜合優化第 7 次 / #詮釋框架

狀態：完成

本次使用：把宣稱結果解讀成已驗證、有限支持、暫定假設或未證明，避免讀者把同一段證據自行放大成更高層級結論。

核心判斷

1. 已驗證只代表同層證據已覆蓋該宣稱。
2. 有限支持與暫定假設不能替代 pytest、人工 review 或 runtime 驗證。
3. 未證明不能被包裝成低風險，也不能待補後自動通過。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 7 次綜合優化章節新增 `解讀框架`。
2. 解讀框架分成已驗證、有限支持、暫定假設與未證明。
3. `docs/hcs-plus-optimization-state.md` 將三習慣綜合優化第 7 次標為完成，並把下一批推進到 `#相關性`、`#描述統計`、`#顯著性`。

優化說明

1. 詮釋框架把估算與信心邊界轉成讀者能理解的結果標籤。
2. 解讀框架不得替代 pytest、人工 review 或 runtime 驗證。
3. 不得把綜合優化第 7 次解讀為 HCS Plus 完成；下一批需檢查關聯、摘要分布與顯著性門檻。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少綜合優化第 7 次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 三習慣綜合優化第 8 次

### 綜合 / 三習慣綜合優化第 8 次 / #相關性

狀態：完成

本次使用：檢查矩陣規則之間是否真的互相支撐，避免只因文字相近就合併或升級。

核心判斷

1. 強支撐必須同時有共同目標、來源層級、適用情境、把握等級與信心邊界。
2. 弱支撐只能保留為有限支持，不能合併成高顯著性規則。
3. 衝突支撐與無關規則必須拆分、降級或刪減。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣綜合優化第 8 次：關聯檢核、分布摘要與顯著性門檻`。
2. 該章節新增 `關聯檢核`，分出強支撐、弱支撐、衝突支撐與無關。
3. `docs/hcs-plus-optimization-state.md` 新增 `三習慣綜合優化第 8 次：關聯檢核、分布摘要與顯著性門檻`。
4. 歷史 checkpoint：下一步：三習慣綜合優化第 8 次 / #相關性。

優化說明

1. 相關性讓第 7 次的把握與信心邊界不只停在單條宣稱，而能檢查規則之間是否真的互相支持。
2. 代價是合併規則前多一層關聯判斷；收益是文字相似不再等於可合併。
3. 本批仍不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_correlation_summary_significance`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_correlation_summary_significance_is_recorded`

### 綜合 / 三習慣綜合優化第 8 次 / #描述統計

狀態：完成

本次使用：把目前文件與測試覆蓋整理成分布摘要，避免把零散觀察寫成改善證明。

核心判斷

1. 完成分布用來檢查完成是否過度集中在文件層或低風險通道。
2. 缺口分布與驗證分布用來找下一批該補哪一種證據。
3. 風險分布只能標出風險出現的位置，不能宣稱風險已被消除。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 8 次綜合優化章節新增 `分布摘要`。
2. 分布摘要分成完成分布、缺口分布、驗證分布與風險分布。
3. `docs/hcs-plus-optimization-state.md` 的第 8 次狀態章節新增系統應用方式，要求新增或合併規則前先做關聯檢核，再做分布摘要。

優化說明

1. 描述統計讓矩陣維護者看見完成與缺口集中在哪裡。
2. 分布摘要只能描述目前文件與測試覆蓋，不得解讀為改善證明。
3. 下一批需用迴歸檢查局部改善是否可能回到舊問題。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_correlation_summary_significance`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_correlation_summary_significance_is_recorded`

### 綜合 / 三習慣綜合優化第 8 次 / #顯著性

狀態：完成

本次使用：設定哪些訊號值得升級成規則，哪些只能保留、降級或刪減。

核心判斷

1. 升級訊號必須跨多個章節、來源層級與測試缺口重複出現，且影響高顯著性改動。
2. 保留訊號可以降低風險但證據仍有限，因此不能擴張宣稱。
3. 降級訊號與刪減訊號防止弱支撐、無關或高成本低效用規則繼續膨脹。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 8 次綜合優化章節新增 `顯著性門檻`。
2. 顯著性門檻分成升級訊號、保留訊號、降級訊號與刪減訊號。
3. `docs/hcs-plus-optimization-state.md` 將三習慣綜合優化第 8 次標為完成，並把下一批推進到 `#機率`、`#迴歸`、`#謬誤`。

優化說明

1. 顯著性門檻讓矩陣只升級反覆出現且影響高顯著性改動的訊號。
2. 顯著性門檻不得替代 pytest、人工 review 或 runtime 驗證。
3. 不得把綜合優化第 8 次解讀為 HCS Plus 完成；下一批需檢查概率語言、回歸風險與推論謬誤。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少綜合優化第 8 次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 三習慣綜合優化第 9 次

### 綜合 / 三習慣綜合優化第 9 次 / #機率

狀態：完成

本次使用：把概率語言分成高可能、中可能、低可能與未知或不得推定，避免「可能」被寫成保證或精確承諾。

核心判斷

1. 高可能需要多個高可信來源在同層證據、關聯檢核與顯著性門檻上互相支持。
2. 中可能與低可能必須保留剩餘不確定，不能寫成完成。
3. 未知或不得推定不得使用精確百分比，也不得宣稱改善、安全、通過或使用者已理解。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣綜合優化第 9 次：概率語言、迴歸風險與謬誤防線`。
2. 該章節新增 `概率語言`，分出高可能、中可能、低可能與未知或不得推定。
3. `docs/hcs-plus-optimization-state.md` 新增 `三習慣綜合優化第 9 次：概率語言、迴歸風險與謬誤防線`。
4. 歷史 checkpoint：下一步：三習慣綜合優化第 9 次 / #機率。

優化說明

1. 機率讓第 8 次的顯著性門檻不會被回報語氣放大。
2. 代價是回報需避免精確百分比；收益是弱證據不能被包裝成高概率保證。
3. 本批仍不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_probability_regression_fallacy`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_probability_regression_fallacy_is_recorded`

### 綜合 / 三習慣綜合優化第 9 次 / #迴歸

狀態：完成

本次使用：檢查新規則是否回到過度宣稱、跨層外推、流程膨脹或弱證據升級等舊問題。

核心判斷

1. 回到過度宣稱時，必須降級宣稱並補限制句與未跑命令。
2. 回到跨層外推時，必須拆回同層宣稱，必要時升級驗證。
3. 回到流程膨脹或弱證據升級時，必須刪減、延後或回到關聯檢核與顯著性門檻。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 9 次綜合優化章節新增 `迴歸風險`。
2. 迴歸風險列出回到過度宣稱、回到跨層外推、回到流程膨脹與回到弱證據升級。
3. `docs/hcs-plus-optimization-state.md` 的第 9 次狀態章節新增系統應用方式，要求回報概率後檢查迴歸風險。

優化說明

1. 迴歸檢查讓矩陣不只新增規則，也檢查是否回到舊錯誤。
2. 迴歸風險不得寫成已修復，只能列出回歸訊號與必須動作。
3. 下一批需用可驗證性固定最終完成證據與測試門檻。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_probability_regression_fallacy`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_probability_regression_fallacy_is_recorded`

### 綜合 / 三習慣綜合優化第 9 次 / #謬誤

狀態：完成

本次使用：建立謬誤防線，阻止相關當因果、測試當 runtime 安全、文件完整當使用者理解、歷史紀錄當新證據。

核心判斷

1. 相關不等於因果；規則同時出現只能寫關聯，不能宣稱造成改善。
2. 通過測試不等於 runtime 安全，文件完整不等於使用者理解。
3. 歷史紀錄不等於新證據，只能當脈絡，不能替代新驗證。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 9 次綜合優化章節新增 `謬誤防線`。
2. 謬誤防線列出相關不等於因果、通過測試不等於 runtime 安全、文件完整不等於使用者理解、歷史紀錄不等於新證據。
3. `docs/hcs-plus-optimization-state.md` 將三習慣綜合優化第 9 次標為完成，並把下一批推進到 `#合理性`、`#可驗證性`、`#制定策略`。

優化說明

1. 謬誤防線讓第 9 次的概率與迴歸規則不被誤讀成完成證據。
2. 謬誤清單不得替代 pytest、人工 review 或 runtime 驗證。
3. 不得把綜合優化第 9 次解讀為 HCS Plus 完成；下一批需收尾完成定義、驗收標準與下一步策略。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少綜合優化第 9 次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 三習慣綜合優化第 10 次

### 綜合 / 三習慣綜合優化第 10 次 / #合理性

狀態：完成

本次使用：確認十次綜合優化仍服務股票研究系統的核心目標、使用者決策用途、維護者合併判斷與契約安全邊界。

核心判斷

1. 十次綜合優化只完成文件與測試契約收斂。
2. 完成不代表 runtime 安全、投資結果改善或使用者理解已驗證。
3. 合理性收尾必須把核心目標、使用者決策用途、維護者合併判斷與契約安全邊界同時列出。

落地修改

1. `docs/pipeline-mode-contract.md` 新增 `契約矩陣綜合優化第 10 次：合理性收尾、驗證門檻與維護策略`。
2. 該章節新增 `合理性收尾` 與 `完成定義`。
3. `docs/hcs-plus-optimization-state.md` 新增 `三習慣綜合優化第 10 次：合理性收尾、驗證門檻與維護策略`。
4. 歷史 checkpoint：下一步：三習慣綜合優化第 10 次 / #合理性。

優化說明

1. 合理性把十次綜合優化從不斷加規則收回完成定義。
2. 代價是完成宣稱受限；收益是完成只代表 HCS Plus 自主優化流程完成。
3. 本批仍不新增 runtime、遙測或自動選測工具。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_final_reasonability_verification_strategy`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_final_reasonability_verification_strategy_is_recorded`

### 綜合 / 三習慣綜合優化第 10 次 / #可驗證性

狀態：完成

本次使用：把完成定義轉成聚焦測試、回歸集合、diff check、strict log、狀態表與契約章節共同支持的驗證門檻。

核心判斷

1. 完成宣稱需要聚焦測試與回歸集合共同支持。
2. diff check 只支持格式乾淨，不能替代測試。
3. strict log、狀態表與契約章節必須同時存在，才支持 HCS Plus 流程完成。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 10 次綜合優化章節新增 `驗證門檻`。
2. `docs/hcs-plus-optimization-state.md` 新增 `HCS Plus 自主優化完成摘要`。
3. 完成摘要列出最終專案內容、決策紀錄、風險與驗收標準、下一步可執行行動。

優化說明

1. 可驗證性把完成定義從口頭宣稱變成可跑命令與可查文件。
2. 完成摘要不得外推為 runtime 安全或使用者理解。
3. 後續若新增契約章節或完成宣稱，必須補對應測試。

驗證方式

- `tests/test_docs_contract.py::test_pipeline_mode_contract_has_integrated_final_reasonability_verification_strategy`
- `tests/test_hcs_plus_state.py::test_hcs_plus_integrated_final_reasonability_verification_strategy_is_recorded`

### 綜合 / 三習慣綜合優化第 10 次 / #制定策略

狀態：完成

本次使用：把完成後維護策略寫成文件與測試契約優先、例外升級與定期複檢。

核心判斷

1. 完成後不是停止維護，而是改成定期複檢契約矩陣。
2. 涉及 parser、prompt、template、audit、runtime、交易語氣或使用者理解宣稱時必須例外升級。
3. 下一步可執行行動必須能被維護者照著做。

落地修改

1. `docs/pipeline-mode-contract.md` 的第 10 次綜合優化章節新增 `維護策略`。
2. `docs/hcs-plus-optimization-state.md` 將三習慣綜合優化第 10 次標為完成。
3. `docs/hcs-plus-optimization-state.md` 將 HCS Plus 自主優化完成狀態標為完成。

優化說明

1. 制定策略讓 HCS Plus 完成後仍有清楚維護入口。
2. 例外升級防止高風險變更被文件完成狀態掩蓋。
3. 完成只代表本次 HCS Plus 自主優化流程完成，不代表後續工作不需要驗證。

驗證方式

- RED：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q` 先確認缺少綜合優化第 10 次會失敗。
- GREEN：`.venv/bin/python -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`。

## 下一步

- 完成後維護 / 定期複檢契約矩陣：後續新增 pipeline、模式語意、報告模板或完成回報規則時，先更新契約章節與測試。
- 例外升級：碰到 parser、prompt、template、audit、runtime、交易語氣或使用者理解宣稱時，先補對應測試與人工 review。
- 下一步：完成後維護 / 定期複檢契約矩陣。

### 完成後維護 / D3369 / #可驗證性

狀態：完成

本次使用：檢查完成後維護是否讓測試名稱、實際收集範圍與報告品質宣稱保持一致。

核心判斷

1. 五個報告品質入口各有重複的 `time_to_payment_operations` 測試定義，後定義會覆蓋前定義，造成測試契約不透明。
2. order case 曾附著在重複 payment 函式內；雖然 focused run 仍可能執行案例，但函式責任與收集名稱不一致。
3. 去重不代表新增 production 覆蓋；因此只整理測試結構，並以 payment/order focused regression 驗證案例仍存在。

落地修改

1. 清理 `tests/test_price_parser.py`、`tests/test_recommendation_calibration.py`、`tests/test_content_credibility_inputs.py`、`tests/test_structured_output_parser.py` 與 `tests/test_report_target_price_detection.py` 的重複定義。
2. 每個入口保留單一 payment 測試與單一 order 測試，避免 Python 後定義覆蓋前定義。
3. 在 `docs/hcs-plus-optimization-state.md` 記錄 D3369 完成後維護證據。

優化說明

1. 測試名稱與收集範圍重新一致，後續 failure triage 可直接定位到責任案例。
2. 代價是刪除重複測試文字；實際 payment/order 行為案例數維持不變。
3. 下一輪仍需擴大非金融 residual 語料，不能把測試去重解讀成 parser coverage 完成。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_payment_operations or time_to_order_fulfillment'`
- `$(scripts/project_python.sh) -m pytest tests/test_docs_contract.py tests/test_hcs_plus_state.py -q`
- `git diff --check`

### 完成後維護 / D3370 / #差距分析 #偏誤降低 #可驗證性 #來源品質

狀態：完成

本次使用：從 D3368 後的非金融候選語料重新取樣，將 people/admin 作業詞根與仍需保留的金融語意邊界分開處理。

核心判斷

1. `recruit employee`、`retain employee`、`promote employee`、`transfer employee`、`reassign employee`、`terminate employee`、`schedule meeting`、`facilitate meeting` 是明確的行政或人員作業語意，可安全納入既有 time-to quality metric guard。
2. fresh pre-fix matrix 為 960 cases，680 個會漏入 target-price 路徑，384 個有效 metric values 會被漏判；因此這是可量測且可局部修正的 residual。
3. case/document、knowledge-records 與 `time to price`、`time to quote`、`time to bill`、`time to invoice`、`time to charge` 仍分開保留，避免把非金融修正外推成金融語意修正。

落地修改

1. 在 `backend/price_parser.py` 既有 `QUALITY_SERVICE_METRIC_PATTERN` time-to branch 加入 8 個 people/admin roots。
2. 五個報告品質入口各新增一個同一語料矩陣的 regression，覆蓋 target/forecast/actual/baseline/current 狀態。
3. 在狀態表保留 pre-fix、final、focused、adjacent 與 import evidence，讓下一輪可從 case/document 或 knowledge-records residual 接續。

優化說明

1. RED→GREEN：五入口先得到 5 failed，production guard 完成後為 5 passed。
2. final matrix 為 960 cases，leaks=0、valid_misses=0；D3349-D3370 相鄰 regression 為 97 passed in 1,545.34s。
3. import boundary 為 503 passed in 9.63s，`backend/price_parser.py` 與 `backend/report_target_price_detection.py` 維持 349/189 行；production scope 沒有擴大到金融價格語意。

驗證方式

- 五入口 D3370 focused regression：`5 passed in 48.98s`。
- 五入口 D3349-D3370 adjacent regression：`97 passed in 1,545.34s`。
- D3370 post-fix matrix：`960 cases / leaks=0 / valid_misses=0`。
- `$(scripts/project_python.sh) -m pytest tests/test_import_boundaries.py -q`：`503 passed in 9.63s`。
- `git diff --check` 與指定 modules `py_compile` 通過。

### 完成後維護 / D3371 / #差距分析 #偏誤降低 #可驗證性 #來源品質

狀態：完成

本次使用：從 D3370 後的非金融候選語料重新取樣，先用 case/document 對照矩陣驗證 residual，再以既有 time-to guard 做局部修正。

核心判斷

1. `create case`、`update case`、`archive case`、`reopen case`、`draft document`、`sign document`、`upload document`、`retrieve document` 是案件或文件作業語意，不應把其 KPI 數值當成股票目標價。
2. fresh pre-fix matrix 為 960 cases，800 個會漏入 target-price 路徑，384 個有效 metric values 會被漏判；因此具備明確的 RED 與可量測修正邊界。
3. knowledge-records 與 `time to price`、`time to quote`、`time to bill`、`time to invoice`、`time to charge` 保留為獨立 residual，不能由本批非金融修正推論已完成。

落地修改

1. 在 `backend/price_parser.py` 的既有 `QUALITY_SERVICE_METRIC_PATTERN` time-to branch 加入 8 個 case/document roots。
2. 五個報告品質入口各新增同一語料矩陣的 regression，覆蓋 target/forecast/actual/baseline/current 狀態，並保留同句真實 `target price NT$205/160` 對照。
3. 在狀態表記錄 D3371 的 pre-fix、final、focused、adjacent 與 import evidence，下一批明確指向 knowledge-records。

優化說明

1. RED→GREEN：五入口先得到 5 failed，production guard 完成後為 5 passed。
2. final matrix 為 960 cases，leaks=0、valid_misses=0；D3349-D3371 相鄰 regression 為 102 passed in 1,590.31s。
3. import boundary 為 503 passed in 10.12s，`backend/price_parser.py` 與 `backend/report_target_price_detection.py` 維持 349/189 行；production scope 沒有擴大到金融價格語意。

驗證方式

- 五入口 D3371 focused regression：`5 passed in 47.00s`。
- 五入口 D3349-D3371 adjacent regression：`102 passed in 1,590.31s`。
- D3371 post-fix matrix：`960 cases / leaks=0 / valid_misses=0`。
- `$(scripts/project_python.sh) -m pytest tests/test_import_boundaries.py -q`：`503 passed in 10.12s`。
- `py_compile`、`git diff --check` 與行數 guard 通過。

### 完成後維護 / D3372 / #差距分析 #偏誤降低 #可驗證性 #來源品質

狀態：完成

本次使用：從 D3371 後的非金融候選語料逐 root 取樣，將 knowledge-records 與股票價格語意分離，再以同一組五入口對照矩陣驗證修正。

核心判斷

1. `create record`、`update record`、`archive record`、`retrieve record`、`publish knowledge`、`review knowledge`、`answer question`、`verify record` 是知識或紀錄作業語意，不應把其 KPI 數值當成股票目標價。
2. fresh pre-fix matrix 為 960 cases，800 個會漏入 target-price 路徑，384 個有效 metric values 會被漏判；因此具備明確的 RED 與可量測修正邊界。
3. `time to price`、`time to quote`、`time to bill`、`time to invoice`、`time to charge` 仍是金融語意 residual，本批只擴展非金融 vocabulary，沒有改變金融邊界。

落地修改

1. 在 `backend/price_parser.py` 的既有 `QUALITY_SERVICE_METRIC_PATTERN` time-to branch 加入 8 個 knowledge-records roots。
2. 五個報告品質入口各新增同一語料矩陣的 regression，覆蓋 target/forecast/actual/baseline/current 狀態，並保留同句真實 `target price NT$205/160` 對照。
3. 在狀態表記錄 D3372 的 pre-fix、final、focused、adjacent 與 import evidence，完成目前已盤點的非金融 residual 批次。

優化說明

1. RED→GREEN：五入口先得到 5 failed，production guard 完成後為 5 passed。
2. final matrix 為 960 cases，leaks=0、valid_misses=0；D3349-D3372 相鄰 regression 為 107 passed in 1,631.11s。
3. import boundary 為 503 passed in 10.24s，`backend/price_parser.py` 與 `backend/report_target_price_detection.py` 維持 349/189 行；production scope 沒有擴大到金融價格語意。

驗證方式

- 五入口 D3372 focused regression：`5 passed in 47.29s`。
- 五入口 D3349-D3372 adjacent regression：`107 passed in 1,631.11s`。
- D3372 post-fix matrix：`960 cases / leaks=0 / valid_misses=0`。
- `$(scripts/project_python.sh) -m pytest tests/test_import_boundaries.py -q`：`503 passed in 10.24s`。
- `py_compile`、`git diff --check` 與行數 guard 通過。

### 完成後維護 / D3373 / #差距分析 #風險意識 #證據基礎 #制定策略

狀態：完成

本次使用：把尚未安全收斂的 financial time-to 語料單獨取樣，確認它不是非金融 vocabulary guard 可以直接吸收的普通 residual。

核心判斷

1. `time to price`、`time to quote`、`time to bill`、`time to invoice`、`time to charge` 可能同時表達金融作業週期與價格、報價、帳單、發票、收費語意。
2. boundary matrix 為 600 cases，現況為 504 個候選數值抽出與 258 個真實 target-price 對照未完整保留；這證明仍需獨立規格與案例分類，不能把它誤判成單純 non-price metric 漏網詞。
3. 本輪沒有 production patch，避免以非金融修正覆蓋真正的價格語意；下一次若要處理，必須先拆分 financial cycle-time 與 explicit target-price context。

落地修改

1. 在 `docs/hcs-plus-optimization-state.md` 記錄 financial boundary 的取樣範圍、現況數字與延後理由。
2. 在本 strict log 建立獨立的 financial semantics 維護入口，讓後續規格、測試與人工 review 有可追蹤位置。
3. 保留目前 `backend/price_parser.py` 與五入口非金融回歸結果，不把本輪 audit 誤報為 production behavior change。

驗證方式

- Financial boundary matrix：`600 cases / leaks=504 / valid_misses=258`，作為延後與拆分規格的證據。
- D3372 focused、adjacent、import、docs、runtime 與 compile guards 已在前一批完成，未因本輪 audit 改變。
- `git diff --check` 與 runtime canonical path 檢查維持通過。

### 完成後維護 / D3374 / #拆解問題 #差距分析 #偏誤降低 #證據基礎 #可驗證性 #來源品質

狀態：完成

本次使用：把 D3373 的 financial boundary audit 轉成可執行的 semantics 規格，先建立五入口 RED，再用最小 scoped branch 修正並以相鄰回歸驗證。

核心判斷

1. 五個 financial roots 只有在明確 `time to <root>` cycle-time 結構中才進入本批；一般 `price`、`quote`、`bill`、`invoice`、`charge` 欄位不受影響。
2. 純 KPI value 應被移除，不應建立 target-price candidate；同句明確 `target price NT$205` 或 `target price NT$160` 必須保留。
3. path-level detector 也要遵守相同規則，避免欄位名稱含 `target_price` 就把 cycle-time value 誤判為股票價格。

落地修改

1. 新增 `docs/financial-time-to-semantics.md`，記錄規則、600-case matrix、排除範圍與完成門檻。
2. 五個報告品質入口各新增 financial cycle-time regression，覆蓋 5 roots × 4 phases × 5 states × 6 prefixes 及明確 target-price 對照。
3. 在 `backend/price_parser.py` 既有 time-to quality metric branch 加入 5 roots，沒有新增 parser 層或改變 runtime/storage。

優化說明

1. RED→GREEN：五入口 `5 failed` 後，production guard 使其成為 `5 passed in 28.03s`。
2. final matrix 為 `600 cases / leaks=0 / valid_misses=0`；D3349-D3374 adjacent regression 為 `112 passed in 1,669.41s`。
3. import boundary 為 `503 passed in 10.02s`，parser/detector 維持 `349/189` 行；金融一般欄位與既有非金融 roots 均由相鄰回歸保護。

驗證方式

- `PYTHONPATH=backend $(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'financial_time_to_cycle'`：`5 passed in 28.03s`。
- D3374 post-fix financial matrix：`600 cases / leaks=0 / valid_misses=0`。
- D3349-D3374 adjacent regression：`112 passed in 1,669.41s`。
- `$(scripts/project_python.sh) -m pytest tests/test_import_boundaries.py -q`：`503 passed in 10.02s`。
- 規格 docs、`py_compile`、`git diff --check` 與行數 guard 通過。

### 完成後維護 / D3375 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

狀態：完成

本次使用：把 fresh residual scan 中的 incident lifecycle family 拆成八個可比較 roots，先用既有 `resolve incident` 作為 control root，再以最小 production 變更收斂其餘七個 roots。

核心判斷

1. `time to open/create/update/assign/close/reopen/escalate incident` 在明確 cycle-time 結構中是事件作業 KPI，純 KPI 數值不應成為 target-price candidate。
2. `time to resolve incident` 已由既有 guard 覆蓋，本輪只把它放進比較組，不重複加入 production pattern。
3. 一般 incident 欄位與明確 `target price` 語意不在本輪修改範圍，避免把作業 KPI guard 擴成廣泛的 incident 或價格排除規則。

落地修改

1. 五個報告品質入口各新增 incident lifecycle regression，覆蓋 8 roots × 4 phases × 5 states × 6 prefixes，並保留明確 target-price 對照。
2. 在 `backend/price_parser.py` 既有 time-to quality metric branch 加入 7 個未覆蓋 roots，沒有新增 parser 層或改變 runtime/storage。

優化說明

1. RED→GREEN：五入口 `5 failed` 後，production guard 使其成為 `5 passed in 47.89s`。
2. pre-fix matrix 為 `960 cases / leaks=700 / valid_misses=336`；post-fix matrix 為 `960 cases / leaks=0 / valid_misses=0`。
3. D3349-D3375 adjacent regression 為 `117 passed in 1,715.59s`；import boundary 為 `503 passed in 10.27s`；parser/detector 維持 `349/189` 行。

驗證方式

- `PYTHONPATH=backend $(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'incident_lifecycle'`：`5 passed in 47.89s`。
- D3375 post-fix incident lifecycle matrix：`960 cases / leaks=0 / valid_misses=0`。
- D3349-D3375 adjacent regression：`117 passed in 1,715.59s`。
- `$(scripts/project_python.sh) -m pytest tests/test_import_boundaries.py -q`：`503 passed in 10.27s`。
- 規格 docs、`py_compile`、`git diff --check` 與行數 guard 通過。

### 完成後維護 / D3376 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

狀態：完成

本次使用：在 D3375 後重新掃描 forms、appointments、support、approvals residual，先以四個 family 的同構矩陣比較，再選擇語意最清楚的 forms workflow 進行局部修正。

核心判斷

1. `time to create/submit/review/approve/process/complete/update/archive form` 是表單作業週期 KPI，純 KPI 數值不應成為股票 target-price candidate。
2. fresh residual scan 顯示 forms 與 appointments 各 `800 leaks / 384 valid_misses`，support 為 `640 / 384`，approvals 為 `600 / 288`；本輪先處理 forms，其他 family 保留為下一輪候選。
3. detector 的 path-level `score` boundary 是既有非價格欄位保護；D3376 detector regression 延續既有五-prefix boundary，不放寬一般 `score` path。

落地修改

1. 五個報告品質入口各新增 forms workflow regression，parser 等入口覆蓋 8 roots × 4 phases × 5 states × 6 prefixes，並保留明確 target-price 對照；detector 依既有 path boundary 使用五個安全 prefixes。
2. 在 `backend/price_parser.py` 既有 time-to quality metric branch 加入 8 個 forms roots，沒有新增 parser 層或改變 runtime/storage。

優化說明

1. RED→GREEN：五入口先得到 `5 failed, 3740 deselected in 36.88s`，production guard 後為 `5 passed, 3740 deselected in 46.82s`。
2. post-fix forms matrix 為 `960 cases / leaks=0 / valid_misses=0`；explicit target price control 仍為 `[205.0]`，ordinary form control 仍保留 `[12.0]`。
3. D3349-D3376 adjacent regression 為 `122 passed, 3623 deselected in 1,758.93s`；import boundary 為 `503 passed in 9.69s`；parser/detector 維持 `349/189` 行。

驗證方式

- `PYTHONPATH=backend $(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'form_workflow'`：`5 passed, 3740 deselected in 46.82s`。
- D3376 post-fix forms matrix：`960 cases / leaks=0 / valid_misses=0`。
- D3349-D3376 adjacent regression：`122 passed, 3623 deselected in 1,758.93s`。
- `$(scripts/project_python.sh) -m pytest tests/test_import_boundaries.py -q`：`503 passed in 9.69s`。
- 規格 docs、`py_compile`、`git diff --check` 與行數 guard 通過。

### 完成後維護 / D3377 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

狀態：完成

本次使用：在 D3376 後重新量測 appointments、support、approvals residual，依同構矩陣選出 appointments lifecycle，並以 forms 已收斂結果作為相鄰比較組。

核心判斷

1. `time to schedule/book/confirm/attend/reschedule/cancel/check in/close appointment` 是預約作業週期 KPI，純 KPI 數值不應成為股票 target-price candidate。
2. fresh residual scan 顯示 appointments 為 `800 leaks / 384 valid_misses`，support 為 `640 / 384`，approvals 為 `600 / 288`；本輪先處理 appointments，其他 family 保留為下一輪候選。
3. detector 的 path-level `score` boundary 是既有非價格欄位保護；D3377 detector regression 延續既有五-prefix boundary，不放寬一般 `score` path。

落地修改

1. 五個報告品質入口各新增 appointments lifecycle regression，parser 等入口覆蓋 8 roots × 4 phases × 5 states × 6 prefixes，並保留明確 target-price 對照；detector 依既有 path boundary 使用五個安全 prefixes。
2. 在 `backend/price_parser.py` 既有 time-to quality metric branch 加入 8 個 appointments roots，沒有新增 parser 層或改變 runtime/storage。

優化說明

1. RED→GREEN：五入口先得到 `5 failed, 3745 deselected in 40.00s`，production guard 後為 `5 passed, 3745 deselected in 48.82s`。
2. post-fix appointments matrix 為 `960 cases / leaks=0 / valid_misses=0`；explicit target price control 仍為 `[205.0]`，ordinary appointment control 仍保留 `[12.0]`。
3. D3349-D3377 adjacent regression 為 `127 passed, 3623 deselected in 1,804.78s`；import boundary 為 `503 passed in 9.56s`；parser/detector 維持 `349/189` 行。

驗證方式

- `PYTHONPATH=backend $(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'appointment_lifecycle'`：`5 passed, 3745 deselected in 48.82s`。
- D3377 post-fix appointments matrix：`960 cases / leaks=0 / valid_misses=0`。
- D3349-D3377 adjacent regression：`127 passed, 3623 deselected in 1,804.78s`。
- `$(scripts/project_python.sh) -m pytest tests/test_import_boundaries.py -q`：`503 passed in 9.56s`。
- 規格 docs、`py_compile`、`git diff --check` 與行數 guard 通過。

### 完成後維護 / D3378 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

狀態：完成

本次使用：在 D3377 後重新量測四個已盤點 family，將 support ticket lifecycle 與已收斂的 forms/appointments 做比較，並以 approvals 與 financial semantics 作為保留邊界。

核心判斷

1. `time to open/create/assign/update/resolve/close/escalate/respond support ticket` 是客服工單作業週期 KPI，純 KPI 數值不應成為股票 target-price candidate。
2. fresh residual scan 顯示 forms、appointments 已為 `0/0`，support 為 `640 leaks / 384 valid_misses`，approvals 為 `600 / 288`；本輪先處理 support，approvals 保留為下一輪候選。
3. 一般 `support ticket` 已是既有 non-price guard，control `support ticket target 12 個` 維持空結果；本輪只處理 `time to <support ticket lifecycle>`，不擴大一般欄位。

落地修改

1. 五個報告品質入口各新增 support ticket lifecycle regression，parser 等入口覆蓋 8 roots × 4 phases × 5 states × 6 prefixes，並保留明確 target-price 對照；detector 依既有 path boundary 使用五個安全 prefixes。
2. 在 `backend/price_parser.py` 既有 time-to quality metric branch 加入 8 個 support ticket roots，沒有新增 parser 層或改變 runtime/storage。

優化說明

1. RED→GREEN：五入口先得到 `5 failed, 3750 deselected in 38.40s`，production guard 後為 `5 passed, 3750 deselected in 50.05s`。
2. post-fix support matrix 為 `960 cases / leaks=0 / valid_misses=0`；explicit target price control 為 `[205.0]`，financial control 為 `[]`，既有 support ticket control 也維持 `[]`。
3. D3349-D3378 adjacent regression 為 `132 passed, 3623 deselected in 1,853.94s`；import boundary 為 `503 passed in 9.51s`；parser/detector 維持 `349/189` 行。

驗證方式

- `PYTHONPATH=backend $(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'support_ticket_lifecycle'`：`5 passed, 3750 deselected in 50.05s`。
- D3378 post-fix support matrix：`960 cases / leaks=0 / valid_misses=0`。
- D3349-D3378 adjacent regression：`132 passed, 3623 deselected in 1,853.94s`。
- `$(scripts/project_python.sh) -m pytest tests/test_import_boundaries.py -q`：`503 passed in 9.51s`。
- 規格 docs、`py_compile`、`git diff --check` 與行數 guard 通過。

### 完成後維護 / D3379 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

狀態：完成

本次使用：在 D3378 後重新量測四個已盤點 family，先以 root-level control 分離既有 `approve/reject request` guard，再收斂未覆蓋的 approvals workflow roots。

核心判斷

1. `time to request/submit/review/escalate/record/close approval` 是審批作業週期 KPI，純 KPI 數值不應成為股票 target-price candidate。
2. `time to approve request` 與 `time to reject request` 已由既有 guard 覆蓋，本輪作為比較組，不重複加入 production pattern。
3. approvals family 的 pre-fix `600 leaks / 288 valid_misses` 可由六個未覆蓋 roots 完整解釋；financial semantics 仍維持獨立邊界，不因本批 approval 語意而放寬。

落地修改

1. 五個報告品質入口各新增 approvals workflow regression，parser 等入口覆蓋 8 roots × 4 phases × 5 states × 6 prefixes，並保留明確 target-price 對照；detector 依既有 path boundary 使用五個安全 prefixes。
2. 在 `backend/price_parser.py` 既有 time-to quality metric branch 加入 6 個未覆蓋 approval roots，沒有新增 parser 層或改變 runtime/storage。

優化說明

1. RED→GREEN：五入口先得到 `5 failed, 3755 deselected in 35.04s`，production guard 後為 `5 passed, 3755 deselected in 47.89s`。
2. post-fix approvals matrix 為 `960 cases / leaks=0 / valid_misses=0`；explicit target price control 為 `[205.0]`，approve/reject request controls 均為 `[]`。
3. D3349-D3379 adjacent regression 為 `137 passed, 3623 deselected in 1,943.19s`；import boundary 為 `503 passed in 10.66s`；parser/detector 維持 `349/189` 行。

驗證方式

- `PYTHONPATH=backend $(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'approval_workflow'`：`5 passed, 3755 deselected in 47.89s`。
- D3379 post-fix approvals matrix：`960 cases / leaks=0 / valid_misses=0`。
- D3349-D3379 adjacent regression：`137 passed, 3623 deselected in 1,943.19s`。
- `$(scripts/project_python.sh) -m pytest tests/test_import_boundaries.py -q`：`503 passed in 10.66s`。
- 規格 docs、`py_compile`、`git diff --check` 與行數 guard 通過。

### 完成後維護 / D3380 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

狀態：完成

本次使用：在 D3379 後擴大 fresh candidate probe，從既有 service queue 語料中分離 project/task workflow 的 time-to residual，並以既有 `time to complete task` 與 financial time-to semantics 作為比較組。

核心判斷

1. `time to create/update/complete/close task`、`time to create/update/fulfill requirement` 與 `time to create project milestone` 是專案執行週期 KPI，純 KPI 數值不應成為股票 target-price candidate。
2. pre-fix `960 cases / 660 leaks / 336 valid-misses` 中，`time to complete task` 已由既有 guard 覆蓋；本輪只新增 7 個未覆蓋 roots，避免重複 pattern。
3. `time to price` 仍是金融語意控制，不因 project/task workflow 修正而擴大非價格 guard。

落地修改

1. 五個報告品質入口各新增 project/task workflow regression，parser 等入口覆蓋 8 roots × 4 phases × 5 states × 6 prefixes，並保留明確 target-price 對照；detector 依既有 path boundary 使用五個安全 prefixes。
2. 在 `backend/price_parser.py` 既有 time-to quality metric branch 加入 7 個未覆蓋 roots，沒有新增 parser 層或改變 runtime/storage。

優化說明

1. RED→GREEN：五入口 focused regression 先各自取得 failure，production guard 後五個入口均 `1 passed`；合併相鄰 selector 為 `25 passed, 3740 deselected in 249.05s`。
2. post-fix project/task matrix 為 `960 cases / leaks=0 / valid_misses=0`；explicit target price control 為 `[205.0]`，financial `time to price` control 為 `[]`，既有 `time to complete task` control 也為 `[]`。
3. parser/detector 維持 `349/189` 行；完整 import、文件契約、runtime doctor 與 diff guards 於 completion gate 重新驗證。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_form or time_to_appointment or time_to_support_ticket or time_to_approval or time_to_project_task'`：`25 passed, 3740 deselected in 249.05s`。
- D3380 post-fix project-task matrix：`960 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing `time to complete task`：`[]`。
- `$(scripts/project_python.sh) -m pytest tests/test_import_boundaries.py -q`、文件契約、`py_compile`、`git diff --check` 與 runtime doctor 為本輪 completion gate。

### 完成後維護 / D3381 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

狀態：完成

本次使用：在 D3380 後重新掃描非金融 time-to workflow 語料，先用 knowledge article、proposal、user story、feature、hotfix、build、release candidate 與 training 比較，再把最接近既有 knowledge-records coverage 的 knowledge article lifecycle 收斂到共享 parser pattern。

核心判斷

1. `time to create/update/publish/review/archive/approve knowledge article` 是知識管理文章生命週期 KPI；其 `12 個` 不能成為股票 target-price candidate。
2. pre-fix 六個 roots 各有 `80/120 leaks` 與 `30/120 valid-misses`，合計 `720 cases / 480 leaks / 180 valid-misses`；這證明問題同時影響純 KPI 與帶明確目標價的複合句。
3. 最小正確修正是把六個 roots 加入既有 `QUALITY_SERVICE_METRIC_PATTERN` time-to branch；`time to price`、`time to quote`、`time to bill`、`time to invoice`、`time to charge` 仍保留金融語意比較組。

落地修改

1. 五個報告品質入口各新增 knowledge article lifecycle regression；parser、calibration、credibility、structured output 覆蓋 720 組語料，detector 依既有 path boundary 覆蓋 600 組語料，並保留明確 target-price 對照。
2. `backend/price_parser.py` 共享 time-to quality branch 加入六個 knowledge article roots；沒有新增 parser/detector 層、runtime/storage 或 route 變更，parser/detector 維持 `349/189` 行。

優化說明

1. 五入口 RED 後收斂回共享 pattern，focused GREEN 通過 `5 passed in 43.23s`；避免留下 parser 與 detector 各自維護的暫時 cleanup。
2. D3381 post-fix matrix 為 `720 cases / leaks=0 / valid_misses=0`；explicit target price control 為 `[205.0]`，financial `time to price` 與 existing `time to publish knowledge` controls 均為 `[]`。
3. D3376-D3381 相鄰 regression 通過 `30 passed, 3740 deselected in 298.43s`；下一輪仍以 fresh residual scan 決定語料，不把 proposal/user story 等未驗證 root 偷渡進本輪 production guard。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_knowledge_article_lifecycle'`：`5 passed in 43.23s`。
- D3381 post-fix knowledge-article matrix：`720 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing `time to publish knowledge`：`[]`。
- D3376-D3381 adjacent regression：`30 passed, 3740 deselected in 298.43s`。
- import boundary：`503 passed in 10.93s`；HCS state + docs contract：`135 passed in 3.29s`；指定模組 `py_compile` exit 0；`git diff --check` exit 0；trailing-whitespace 掃描無命中；runtime doctor exit 0，canonical operational/report index DB 仍為 `operational.sqlite3` / `stock_agent_cache.sqlite3`，Redis `redis://localhost:6379/0`、RQ queue `stock-analysis`。

### 完成後維護 / D3382 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

狀態：完成

本次使用：在 D3381 後依 fresh residual scan 的排序，從 proposal、user story、feature、hotfix、build、release candidate 與 training 中選取 proposal lifecycle，並以同一組五入口 target-price boundary 驗證。

核心判斷

1. `time to create/draft/submit/review/approve/close proposal` 是提案流程 KPI；純流程數字不應進入股票目標價候選。
2. pre-fix matrix 為 `720 cases / 600 leaks / 180 valid-misses`，五個 consumer 都能重現污染，且合法 `target price NT$160` 對照也需要被保留。
3. production 只追加六個 proposal roots 到既有 `QUALITY_SERVICE_METRIC_PATTERN` time-to branch；金融 `time to quote` 不納入本輪 guard。

落地修改

1. 五個報告品質入口新增 proposal lifecycle regression；parser、calibration、credibility、structured output 覆蓋 720 組語料，detector 依既有 path boundary 覆蓋 600 組語料。
2. `backend/price_parser.py` 共享 branch 加入六個 proposal roots，維持 parser/detector `349/189` 行與既有 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 40.15s`，沒有新增第二套 parser cleanup。
2. D3382 post-fix proposal matrix 為 `720 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`，financial `time to quote` 與 existing `time to publish knowledge` controls 均為 `[]`。
3. D3376-D3382 相鄰 regression 為 `35 passed, 3740 deselected in 348.60s`；下一輪依 fresh scan 選 root，不提前擴大到 user story 或 feature。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_proposal_lifecycle'`：`5 passed in 40.15s`。
- D3382 post-fix proposal matrix：`720 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to quote`：`[]`；existing `time to publish knowledge`：`[]`。
- D3376-D3382 adjacent regression：`35 passed, 3740 deselected in 348.60s`。
- import boundary：`503 passed in 11.13s`；HCS state + docs contract：`135 passed in 3.49s`；指定模組 `py_compile` exit 0；`git diff --check` exit 0；trailing-whitespace 掃描無命中；runtime doctor exit 0，canonical operational/report index DB 仍為 `operational.sqlite3` / `stock_agent_cache.sqlite3`，Redis `redis://localhost:6379/0`、RQ queue `stock-analysis`。

### 完成後維護 / D3383 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

狀態：完成

本次使用：在 D3382 後對 user story、feature、hotfix、build 做 fresh residual scan，選取第一個 user story lifecycle residual，並以五個報告品質入口與金融 time-to comparison controls 驗證。

核心判斷

1. `time to create/update/complete/close user story` 是產品開發流程 KPI；純 KPI 數字不應污染股票目標價候選。
2. pre-fix matrix 為 `480 cases / 400 leaks / 120 valid-misses`，表示 user story root 尚未被既有 proposal/knowledge/time-to guards 覆蓋。
3. production 只追加四個 user story roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；金融 `time to price` 仍保持獨立比較組。

落地修改

1. 五個報告品質入口新增 user story lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 roots，維持 parser/detector `349/189` 行與 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 27.74s`，沒有建立另一套 consumer-specific parser logic。
2. D3383 post-fix user-story matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`，financial `time to price` 與 existing `time to create proposal` controls 均為 `[]`。
3. D3376-D3383 相鄰 regression 為 `40 passed, 3740 deselected in 373.69s`；下一輪仍先 fresh scan，再決定 feature/hotfix/build 的收斂順序。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_user_story_lifecycle'`：`5 passed in 27.74s`。
- D3383 post-fix user-story matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing `time to create proposal`：`[]`。
- D3376-D3383 adjacent regression：`40 passed, 3740 deselected in 373.69s`。
- import boundary：`503 passed in 11.25s`；HCS state + docs contract：`135 passed in 3.46s`；指定模組 `py_compile` exit 0；`git diff --check` exit 0；trailing-whitespace 掃描無命中；runtime doctor exit 0，canonical operational/report index DB 仍為 `operational.sqlite3` / `stock_agent_cache.sqlite3`，Redis `redis://localhost:6379/0`、RQ queue `stock-analysis`。

### 完成後維護 / D3384 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

狀態：完成

本次使用：在 D3383 後 fresh scan feature、hotfix、build 與 release candidate，選取第一個 feature lifecycle residual，並以五個報告品質入口及金融比較組驗證。

核心判斷

1. `time to create/develop/release/retire feature` 是產品開發流程 KPI；其數字不應被當成股票目標價。
2. pre-fix matrix 為 `480 cases / 400 leaks / 120 valid-misses`，四個 feature roots 均在既有 time-to guard 外。
3. production 只追加四個 feature roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`，金融 `time to price` 仍保持獨立。

落地修改

1. 五個報告品質入口新增 feature lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 27.44s`，沒有增加 consumer-specific cleanup。
2. D3384 post-fix feature matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`，financial `time to price` 與 existing `time to create user story` controls 均為 `[]`。
3. D3376-D3384 相鄰 regression 為 `45 passed, 3740 deselected in 367.17s`；下一輪仍先 fresh scan，再決定 hotfix/build/release candidate 順序。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_feature_lifecycle'`：`5 passed in 27.44s`。
- D3384 post-fix feature matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing `time to create user story`：`[]`。
- D3376-D3384 adjacent regression：`45 passed, 3740 deselected in 367.17s`。
- import boundary：`503 passed in 10.16s`；HCS state + docs contract：`135 passed in 3.20s`；指定模組 `py_compile` exit 0；`git diff --check` exit 0；trailing-whitespace 掃描無命中；runtime doctor exit 0，canonical operational/report index DB 仍為 `operational.sqlite3` / `stock_agent_cache.sqlite3`，Redis `redis://localhost:6379/0`、RQ queue `stock-analysis`。

### 完成後維護 / D3385 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

狀態：完成

本次使用：在 D3384 後 fresh scan hotfix、build、release candidate 與 training，選取第一個 hotfix lifecycle residual，並以五個報告品質入口和金融比較組完成收斂。

核心判斷

1. `time to create/deploy/rollback/resolve hotfix` 是事件修復流程 KPI；其數值不應成為股票目標價。
2. pre-fix matrix 為 `480 cases / 320 leaks / 120 valid-misses`，四個 hotfix roots 尚未被既有 feature guard 覆蓋。
3. production 只追加四個 hotfix roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`，金融 `time to price` 保持獨立比較組。

落地修改

1. 五個報告品質入口新增 hotfix lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 hotfix roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 24.21s`，沒有新增 consumer-specific cleanup。
2. D3385 post-fix hotfix matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`，financial `time to price` 與 existing `time to create feature` controls 均為 `[]`。
3. D3376-D3385 相鄰 regression 為 `50 passed, 3740 deselected in 392.62s`；下一輪再以 fresh scan 決定 build/release candidate/training 順序。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_hotfix_lifecycle'`：`5 passed in 24.21s`。
- D3385 post-fix hotfix matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing `time to create feature`：`[]`。
- D3376-D3385 adjacent regression：`50 passed, 3740 deselected in 392.62s`。
- import boundary：`503 passed in 10.44s`；HCS state + docs contract：`135 passed in 3.31s`；指定模組 `py_compile` exit 0；`git diff --check` exit 0；trailing-whitespace 掃描無命中；runtime doctor exit 0，canonical operational/report index DB 仍為 `operational.sqlite3` / `stock_agent_cache.sqlite3`，Redis `redis://localhost:6379/0`、RQ queue `stock-analysis`。

### 完成後維護 / D3386 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

狀態：完成

本次使用：在 D3385 後 fresh scan build、release candidate 與 training，選取第一個 build lifecycle residual，並以五個報告品質入口和金融比較組完成收斂。

核心判斷

1. `time to run/fix/complete build` 是建置流程 KPI；其數值不應進入股票 target-price candidates。
2. pre-fix matrix 為 `360 cases / 300 leaks / 90 valid-misses`，三個 build roots 尚未被 hotfix guard 覆蓋。
3. production 只追加三個 build roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`，金融 `time to price` 保持獨立。

落地修改

1. 五個報告品質入口新增 build lifecycle regression；parser、calibration、credibility、structured output 覆蓋 360 組語料，detector 依既有 path boundary 覆蓋 300 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入三個 build roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 18.25s`，沒有新增 consumer-specific cleanup。
2. D3386 post-fix build matrix 為 `360 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`，financial `time to price` 與 existing `time to create hotfix` controls 均為 `[]`。
3. D3376-D3386 相鄰 regression 為 `55 passed, 3740 deselected in 406.07s`；下一輪再以 fresh scan 決定 release candidate/training 順序。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_build_lifecycle'`：`5 passed in 18.25s`。
- D3386 post-fix build matrix：`360 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing `time to create hotfix`：`[]`。
- D3376-D3386 adjacent regression：`55 passed, 3740 deselected in 406.07s`。
- completion gate：import boundary `503 passed in 10.60s`；HCS/文件契約 `135 passed in 2.85s`；`py_compile` exit 0；`git diff --check` exit 0；trailing-whitespace 無命中；runtime doctor exit 0，canonical operational DB 為 `backend/cache/operational.sqlite3`、report index 為 `backend/cache/stock_agent_cache.sqlite3`，Redis 為 `redis://localhost:6379/0`；parser/detector 行數維持 `349/189`。

### 完成後維護 / D3387 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3386 後重新掃描 release candidate 與 training candidate，選擇非金融且可用既有共享 time-to guard 表達的 release-candidate lifecycle；以 build、financial `time to price` 與 explicit target price 作為比較組。

核心判斷

1. `time to create/approve/publish release candidate` 是發布流程 KPI；其數值不應進入股票 target-price candidates。
2. pre-fix matrix 為 `360 cases / 1500 leaks / 594 valid-misses`；每個入口各有 300 leaks，valid-miss 分布為 parser 144、calibration 90、credibility 0、structured output 90、detector 270；三個 release-candidate roots 尚未被 hotfix/build guard 覆蓋。
3. production 只追加三個 release-candidate roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`，金融 `time to price` 保持獨立。

落地修改

1. 五個報告品質入口新增 release-candidate lifecycle regression；parser、calibration、credibility、structured output 覆蓋 360 組語料，detector 依既有 path boundary 覆蓋 300 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入三個 release-candidate roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 20.77s`，沒有新增 consumer-specific cleanup。
2. D3387 post-fix release-candidate matrix 為 `360 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`，financial `time to price` 與 existing `time to run build` controls 均為 `[]`。
3. D3376-D3387 完整相鄰 regression 為 `60 passed, 3740 deselected in 423.61s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_release_candidate_lifecycle'`：`5 passed in 20.77s`。
- D3387 post-fix release-candidate matrix：`360 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing `time to run build`：`[]`。
- D3376-D3387 adjacent regression：`60 passed, 3740 deselected in 423.61s`。
- completion gate：import boundary `503 passed in 11.00s`；HCS/文件契約 `135 passed in 3.50s`；`py_compile` exit 0；`git diff --check` exit 0；trailing-whitespace 無命中；runtime doctor exit 0，canonical operational DB 為 `backend/cache/operational.sqlite3`、report index 為 `backend/cache/stock_agent_cache.sqlite3`，Redis 為 `redis://localhost:6379/0`；parser/detector 行數維持 `349/189`。

### 完成後維護 / D3515 / #拆解問題 #問對問題 #差距分析 #變數分析 #偏誤降低 #決策樹 #目的 #效用 #證據基礎 #來源品質 #可驗證性

本次使用：live canonical `analysis_events` 顯示三個 Gemini route 持續產生 429 quota error；錯誤內容是專案/模型目前 quota，沒有可辨識的 `RequestsPerDay` 明細，因此既有 key+model RPD disable 只標記少量 key，無法阻止跨 job 重複輪詢 16 個 key。Redis/RQ 是目前正式 runtime 的共享邊界。

核心判斷

1. generic project/model quota 不應被誤當成單一 API key RPD；但同一模型的所有 key 都失敗時，繼續輪換只會增加 provider 壓力與報告延遲。
2. circuit 必須只對受影響模型生效，不能把 429 或 5xx 轉成所有模型停用；5xx 維持既有 retry 與 job-local circuit。
3. 跨 job 狀態必須放在 Redis TTL，KeyRotator 送出 provider request 前先檢查，Redis key 只保存模型 hash 與 TTL，不保存 secret 或原始模型名。

落地修改

1. `backend/shared_runtime_guards.py` 與 local fallback 新增 model circuit wait/open/check；`backend/llm_rate_limits.py` 新增 `ModelCircuitOpenError` 與 shared model circuit API。
2. `backend/agent_runtime/model_policy.py` 只有 `AgentRateLimitError.all_keys_exhausted` 才發布跨 job circuit；`retry_policy.py` 將 open circuit 轉為 fast-fail quota error，保留既有 fallback。
3. 新增 Redis hash/TTL、KeyRotator provider-request boundary、quota-only publication 與 error conversion regression。

驗證方式

- RED：新增 circuit 測試初始因缺少 model circuit API 與錯誤類別而無法收集。
- GREEN：shared guard、KeyRotator、model policy focused regression `32 passed`。
- live pre-fix evidence：canonical `analysis_events` 500 筆 recent error 中，gemma 304 筆、gemini preview 154 筆、gemini 3.6 33 筆為 quota；Redis 只有 1 個 `rpd-disabled` key，不能把 generic project quota 當作 RPD。
- post-fix gate：Worker 重啟後 `/healthz` 與 `/readyz` 通過；synthetic quota exhaustion 走正式 `record_model_failure -> publish_shared_model_circuit -> KeyRotator.get_key` 路徑，第二個 job 收到 `ModelCircuitOpenError` 且 provider request 未建立，其他模型仍可取 key，Redis synthetic key 已清除。

狀態：完成

### 完成後維護 / D3514 / #拆解問題 #問對問題 #差距分析 #變數分析 #偏誤降低 #決策樹 #目的 #效用 #證據基礎 #來源品質 #可驗證性

本次使用：live `/api/observability/dashboard` 的 `6ccedf...` 顯示 SQLite `waiting_retry` 且超過 900 秒，但同一 task identity `analysis:6ccedf...` 仍在 RQ `watchlist` queue，RQ status 為 `queued`。根因是 dashboard stuck query 只讀 canonical SQLite，沒有使用同一 API request 已取得的 queue state。

核心判斷

1. `waiting_retry` 仍是 active status，但若 RQ 明確為 `queued/deferred/scheduled`，它代表等待 Worker 接續，不應升格為 stuck execution。
2. `started` 仍可能是長時間執行中的真正卡住候選；RQ status unknown 或檢查失敗時不能樂觀排除告警。
3. queue-aware filter 必須使用與 worker 相同的 `analysis:` / `report-rerun:` task identity，且只改 dashboard projection，不改 SQLite status、RQ job 或 retry lifecycle。

落地修改

1. `backend/analysis_job_queue_state.py` 新增 `task_queue_job_state`，保留既有 queue lookup 的 unknown 三態語意。
2. `backend/job_ops_dashboard.py` 接收 API 的 task queue，只排除明確 queue-wait 的 `waiting_retry`；`backend/api_observability_service.py` 傳入同一 queue instance。
3. `tests/test_runtime_observability.py` 新增老化 SQLite `waiting_retry` 對應 RQ `queued` 時不得列入 stuck 的回歸測試，並保留既有真正 stuck 與 RQ lookup failure 覆蓋。

驗證方式

- RED：新測試初始因 `build_ops_dashboard_snapshot()` 不接受 `task_queue` 而失敗。
- GREEN：queue-backed waiting-retry focused regression `4 passed`；observability + worker regression `167 passed`；task queue boundary regression `14 passed`；compileall 與 `git diff --check` 通過。
- live pre-fix evidence：job `6ccedf...` 的 RQ `watchlist` status 為 `queued`、SQLite status 為 `waiting_retry`；post-fix API restart 與同一 job predicate verify 尚待完成，不把 source regression 當成 live 完成證據。

### 完成後維護 / D3513 / #拆解問題 #問對問題 #差距分析 #變數分析 #偏誤降低 #決策樹 #目的 #效用 #證據基礎 #來源品質 #可驗證性

本次使用：新 Worker `3e336d8d` 的 v4 `3443.TW` live baseline 顯示 Agent 22/23 都遭遇 gemma quota failure，但兩個 `model_failed` 都是 `circuit_open=false`。追查 retry reducer 後確認，當 provider 反覆選到相同 key slot 時，`key_slots` 集合未達 configured key count；雖然 retry 已達 `key_count*2` ceiling，仍沒有設定 `all_keys_exhausted`。

核心判斷

1. `key_count*2` 是明確的 quota retry 上限；到達上限就代表本 job 不應再繼續同模型，不應依賴 slot 去重結果才能開 circuit。
2. unique slot evidence 仍優先保留，slot 重複只改用 ceiling evidence 補足，不改第一輪 key rotation 順序。
3. D3512 的 peer fail-fast 必須建立在可靠的 exhausted marker 上，否則 repeated-slot storm 會繞過共享 circuit。

落地修改

1. `backend/agent_runtime/model_policy.py` 在 quota attempt ceiling 與無 slot evidence 的 stop path 設定 `AgentRateLimitError.all_keys_exhausted`。
2. `tests/test_llm_model_policy.py` 新增 repeated key-slot ceiling regression，並保留原有 unique-slot 與 peer-circuit tests。
3. 不改跨 job rotator scope、provider key 實際輪換或 fallback model route。

驗證方式

- RED：repeated-slot ceiling test 初始在 stop 後仍得到 `all_keys_exhausted=False`。
- GREEN：D3513 focused policy tests `3 passed`；完整 model/rotator、workflow、import/HCS/docs、runtime/architecture gate 待本批推送前重跑。
- live baseline：`3443.TW` 兩個 branch 的 `model_failed.circuit_open=false` 已被 canonical event ledger 證實；尚未把修正後結果宣稱為 live 命中。

### 完成後維護 / D3512 / #拆解問題 #問對問題 #差距分析 #變數分析 #偏誤降低 #決策樹 #目的 #效用 #證據基礎 #來源品質 #可驗證性

本次使用：live v4 `2344.TW` 的 canonical event ledger 顯示平行 Agent 22/23 都以 gemma 為 primary；Agent 22 先完成 quota sweep 並記錄 `circuit_open=true`，但 Agent 23 仍持續 provider retry，造成同一 job 對同一模型重複消耗 quota。這是 D3511 只能在 graph join 後合併 state、無法中止已在 retry loop 中的 peer branch 的邊界。

核心判斷

1. 第一個 branch 完整 sweep 後開啟 circuit，其他同 job branch 的 tenacity retry 應在下一次 retry 判斷時停止。
2. 共享 circuit 必須放在每個 job 專用的 `KeyRotator`，不能使用 process-global state，避免不同股票或不同任務互相停用模型。
3. 只有真正已開啟的 circuit 才發布到共享 rotator；普通 transient/server failure 仍依原本 threshold 重試。

落地修改

1. `backend/llm_rate_limits.py` 新增 job-scoped `open_model_circuit` / `is_model_circuit_open`。
2. `backend/agent_runtime/model_policy.py` 讓 retry stop 接收 peer circuit probe，並標記 `parallel_circuit_open`。
3. `backend/agent_runtime/single_agent.py` 在 sync/async agent retry 與 failure publish 接上共享 circuit，事件補 `shared_circuit_open` metadata。
4. `tests/test_llm_model_policy.py`、`tests/test_reviewed_bug_fixes.py` 新增 fail-fast 與跨 rotator isolation regression。

驗證方式

- RED：新增 peer-circuit test 初始因 `make_model_retry_stop()` 不接受 probe 而失敗。
- GREEN：model policy + reviewed bug fixes `48 passed`；workflow/state/checkpoint `37 passed`；runtime/architecture `154 passed`；compileall/diff check 通過。
- live baseline：`2344.TW` 在舊 Worker 上記錄 Agent 22/23 約 `21/32` 次 gemma calls；D3512 尚未載入該 job，因此待新 Worker 的後續 quota failure 事件確認 call 數縮短。

### 完成後維護 / D3511 / #拆解問題 #問對問題 #差距分析 #變數分析 #偏誤降低 #決策樹 #目的 #效用 #證據基礎 #來源品質 #可驗證性

本次使用：live c998 v3 retry 的 canonical event ledger 顯示 Agent 18 的 gemma primary quota sweep 失敗並開啟 model circuit，但平行 Agent 20 成功分支完成後，Agent 21 仍重新呼叫 gemma。根因不是 D3509 的 state 欄位缺失，而是 LangGraph 平行 delta 使用一般 top-level merge，成功分支的空 circuit map 覆蓋了失敗分支的 open state。

核心判斷

1. 平行 Agent 的 model circuit reducer 必須保留任一分支的 open circuit，不能把成功分支的空 map 當成清除訊號。
2. 同一模型多個分支同時失敗時，應保留較大的 failure count 與較晚的 opened-until，讓後續 Agent 直接走 fallback。
3. reducer 只作用於同一 job 的 checkpoint state，不改跨 job quota policy，也不阻止第一輪完整 key sweep。

落地修改

1. `backend/workflow_state.py` 新增 `merge_model_circuits`，替換 `llm_model_circuits` 的一般 `merge_dicts` reducer。
2. `tests/test_workflow_agent_adapter.py` 新增成功/失敗平行分支與較新熔斷窗口 regression。
3. 保留 D3510 context-digest guard；本批只修正平行 graph delta 的 state merge 邊界。

驗證方式

- workflow/state regression：`21 passed`；context-digest/import regression：`3 passed`。
- RED evidence：live c998 Agent 18 開啟 gemma circuit 後，Agent 21 仍有 gemma calls；修正後以 reducer tests 鎖定「空成功分支不得清除 open circuit」。
- completion gate：`compileall` exit 0；`git diff --check` exit 0；新 Worker `24420dde...` 已載入 `09d63b99`，live v4 `1319.TW` 的平行 Agent 22/23 都成功使用 gemma，本輪沒有觸發 failure/success 混合分支；trigger behavior 由 reducer regression 覆蓋，未把未觸發的 live 情境宣稱為已觀察。

### 完成後維護 / D3510 / #拆解問題 #問對問題 #差距分析 #變數分析 #偏誤降低 #決策樹 #目的 #效用 #證據基礎 #來源品質 #可驗證性

本次使用：新版 Worker `51862` 執行 f28 v4 report 已完成，event ledger 顯示 Agent 23 完成 `gemma-4-31b-it` 的 16-key quota sweep 後切換 fallback；同一 job 的後續 Agent 24 只呼叫 fallback。接著觀察新版 a4d9 v2 retry，發現 Agent 14 的 primary quota sweep 後，Agent 21 的前序 context digest 仍準備呼叫 gemma；這是獨立 direct caller 沒有讀取 job model circuit 的邊界。

核心判斷

1. context digest 與主 Agent 呼叫共用同一 job 的 model circuit，不能因為是摘要任務就重新送出已熔斷模型。
2. sync/async direct caller 在送出 key/provider request 前都要檢查 circuit；open 時使用既有 deterministic fallback，保留摘要格式契約。
3. context digest 自身遇到 quota failure 時要回寫 job-model circuit；成功時清除該模型的舊 circuit，不把狀態擴散到其他 job。

落地修改

1. `backend/context_digest_tasks.py` 導入既有 model policy，加入 sync/async open guard、success clear 與 quota failure circuit marker。
2. `tests/test_runtime_observability.py` 新增 open circuit 不得呼叫 key/provider，以及 quota failure 會開啟 circuit 的 regression。
3. 保留 D3509 graph state round-trip；context digest 的 circuit mutation 由 Agent node delta 一併回寫 checkpoint。

驗證方式

- D3510 context-digest/runtime regression：`133 passed`；workflow/model policy regression：`68 passed`；graph/checkpoint regression：`22 passed`。
- live f28 canonical DB：job `done`，Agent 23 `gemma` 16 calls/errors、15 retries，Agent 23 fallback 1 次；Agent 24 只出現 `gemini-3.6-flash` call。
- live a4d9 仍在新版 Worker 中執行，觀察到修正前的 Agent 21 context-digest request，未把該舊事件誤算成修正後失敗；source fix 已由 sync/async regression 鎖定。

### 完成後維護 / D3509 / #拆解問題 #問對問題 #差距分析 #變數分析 #偏誤降低 #決策樹 #目的 #效用 #證據基礎 #來源品質 #可驗證性

本次使用：live `bcad...` 的事件與 stage summary 顯示 Agent 2 對 `gemma-4-31b-it` 有 17 次 call、16 次 quota error、15 次 retry，完成 primary key sweep 後 fallback；Agent 3 卻再次產生 24 次 primary call、24 次 quota error。這證明 D3505 的 circuit policy 在單一 legacy context 內有效，但沒有跨 LangGraph node checkpoint 傳遞。

核心判斷

1. model circuit 是同一份 job 的跨 Agent 運行狀態，不能只放在每次 node 重建的暫存 context。
2. graph state 必須保存可序列化的 model id、failure count、opened-until 與最後錯誤摘要，讓下一個 Agent 讀到同一 circuit。
3. 只同步同一 job 的 graph state，不把 circuit 擴散到其他 job，也不改第一輪完整 key sweep 或 fallback policy。

落地修改

1. `backend/workflow_state.py` 新增 checkpoint-safe `llm_model_circuits` state，使用既有 `merge_dicts` reducer。
2. `backend/workflow_context.py` 在 graph/context round-trip 轉換 `MODEL_CIRCUITS_KEY`，保留舊 checkpoint 缺欄位時的空集合預設。
3. `backend/workflow_services.py` 初始化 circuit state，並讓每個 Agent node delta 回寫最新 circuit；新增單次 round-trip 與兩個連續 Agent 的 regression。

驗證方式

- D3509 adapter/cross-agent regression：`13 passed`。
- RED 先重現：未接 graph state 時 round-trip test 取得 `KeyError: _llm_model_circuits`；接入後 GREEN。
- live 原始證據保留於 `bcad...` job event：Agent 2 與 Agent 3 的 primary quota call 次數顯示跨 node state 遺失；本次修正尚未宣稱已由新 Worker runtime 載入。

### 完成後維護 / D3507 / #拆解問題 #問對問題 #差距分析 #偏誤降低 #決策樹 #目的 #效用 #描述統計 #證據基礎 #來源品質 #可驗證性

本次使用：live `/api/observability/dashboard` 回傳 `active_count=33`、`running=2`、`queued=31`，但 `stuck_jobs` 前 20 筆全是長時間 queued backlog；以 canonical `operational.sqlite3` 重算後，真正未更新超過 15 分鐘的 running job 只有 1 筆。這是卡住警示的分類邊界錯誤，不是 queue backlog 本身的品質失敗。

核心判斷

1. `queued` 是等待壓力，應由 RQ queue depth 與 oldest queued age 觀測，不應直接升格為 stuck execution。
2. `running` 與 `waiting_retry` 長時間未更新才進入 stuck warning，避免操作人員被正常排隊量誤導。
3. 保留 active job count 與 queue lifecycle，不把排隊工作刪除、取消或改寫成終態。

落地修改

1. `backend/job_ops_dashboard.py` 新增 `STUCK_JOB_STATUSES`，將 stuck query 限縮為 `running`、`waiting_retry`。
2. `tests/test_runtime_observability.py` 新增老化 queued backlog 不得進入 stuck list 的回歸案例。
3. `docs/operator-guide.md` 與 `docs/api.md` 補上 stuck 與 queue pressure 的判讀契約。

驗證方式

- observability focused regression：`1 passed`；job-store adjacent：`10 passed`。
- live canonical DB direct audit：`active=33 (queued=31, running=2)`，stuck result 只含 1 筆 running。
- 未修改 job status、RQ payload、queue depth 或報告品質 gate。

### 完成後維護 / D3508 / #拆解問題 #問對問題 #差距分析 #變數分析 #偏誤降低 #決策樹 #目的 #效用 #證據基礎 #來源品質 #可驗證性

本次使用：新 Worker 啟動後以所有 configured queues 檢查，發現 `a4d9...`、`c998...` 的 RQ job 狀態分別為 queued/scheduled retry，但 SQLite 仍是 `running`；這會讓操作員誤以為 Agent 正在執行，也讓 stuck warning 失去狀態語意。

核心判斷

1. RQ queued、deferred、scheduled 是等待重試，不是目前執行；SQLite `running` 必須校正為 `waiting_retry`。
2. RQ started/current claim 保留 `running`；沒有任何 RQ claim 才走既有 abandoned reconciliation。
3. 校正只改 active job 的狀態與可追蹤事件，不刪除 RQ retry、不改報告內容或 retry 次數。

落地修改

1. `backend/worker_rq_reconciliation.py` 新增跨 queue 的 `rq_job_states()`，保留 queued/started/deferred/scheduled 狀態。
2. `backend/worker_main.py` 啟動 reconciliation 將 SQLite running retry 校正為 `waiting_retry`，並寫入 `queue_reconciled` event。
3. `tests/test_worker_main.py` 鎖住 queued retry 的 waiting state 與既有 abandoned 邊界。

驗證方式

- worker reconciliation full regression：`33 passed`；import boundary：`503 passed`；HCS/文件契約：`135 passed`；worker entrypoint `266` 行。
- live RQ evidence：`c998` 在 controlled cold stop 後進入 scheduled retry，剩餘 retry 次數由 RQ 保留。
- 未刪除 queued/scheduled job，也未停止 API。

### 完成後維護 / D3506 / #拆解問題 #問對問題 #差距分析 #偏誤降低 #決策樹 #效用 #證據基礎 #比較組 #介入研究 #可驗證性 #來源品質

本次使用：live Redis/RQ 檢查發現 `SimpleWorker` 有 current job `report-rerun:365f...` 且 worker live，但 `StartedJobRegistry` 暫時為空；SQLite 另有未被 live worker claim 的舊 `running` job `a4d9...`，操作佇列因此多報一筆執行中工作。

核心判斷

1. live worker 的 current job claim 優先於尚未同步的 StartedJobRegistry，否則 reconciliation 可能把真正執行中的報告誤判為 abandoned。
2. 只接受 live worker 且有 current job 的 claim；死 worker、無 current job、deferred/scheduled job 不得被當成 active execution。
3. 本次只修正 RQ 存活辨識與測試，不改 job status、佇列內容或報告品質政策。

落地修改

1. `backend/worker_rq_reconciliation.py` 在 registry 空集合時仍檢查 live worker current job，保留其 RQ claim。
2. `tests/test_worker_main.py` 新增 registry 未同步但 live worker 有 current job 的回歸案例。

驗證方式

- worker reconciliation focused regression：`4 passed, 28 deselected`；import boundary：`503 passed`。
- live Redis/RQ audit：`a4d9...`、`c998...` 分別在 queued/scheduled retry，並由新 reconciliation 校正為 `waiting_retry`；RQ retry payload 與次數保留。
- 未改 queue payload、job status 或跨 job 的報告處理流程。

### 完成後維護 / D3505 / #拆解問題 #問對問題 #差距分析 #偏誤降低 #決策樹 #效用 #證據基礎 #比較組 #介入研究 #可驗證性 #來源品質

本次使用：live Worker trace 觀察到同一份重跑的 `gemma-4-31b-it` 對 16 個 key 逐一回覆 429，完成整輪 key rotation 後才切換 `gemini-3.6-flash`。既有 model circuit threshold 為 2，後續 Agent 仍可能重複 primary quota sweep，形成可避免的延遲與錯誤噪音。

核心判斷

1. 第一個 Agent 仍須完整嘗試每個已載入 key，保留 key-level quota evidence；不能用代表 key 取代完整測試。
2. 同一 job、同一 model 已確認所有 key 都耗盡 quota/rate attempt 後，後續 Agent 應立即使用既有 fallback。
3. circuit 僅寫入目前 job context 的 model id；其他 model、其他 job 與 fallback route 不受影響。

落地修改

1. `backend/agent_runtime/retry_policy.py` 為 `AgentRateLimitError` 增加 `all_keys_exhausted` marker。
2. `backend/agent_runtime/model_policy.py` 在 quota key slots 全部耗盡時設 marker，並讓 model circuit 立即開啟。
3. `tests/test_llm_model_policy.py` 與 `tests/test_architecture_services.py` 鎖住第一輪完整 key sweep 及後續 Agent fail-fast fallback。

驗證方式

- model-policy focused regression：`17 passed`；architecture quota/circuit regression：`3 passed`。
- 第一個 Agent calls：primary 4 次後 fallback；第二個 Agent：只呼叫 fallback 1 次。
- 未修改 key rotation 的第一輪完整嘗試邊界，也未把 model circuit 擴成全域 key/model 停用。

### 完成後維護 / D3504 / #拆解問題 #問對問題 #差距分析 #偏誤降低 #決策樹 #效用 #證據基礎 #比較組 #介入研究 #可驗證性 #來源品質

本次使用：live dashboard 的 3017 v1/v2 repair item 只顯示泛化 report-conformance summary；對照 data snapshot 的 `blocking_issues[].details`，實際原因是「持有」建議與 12 個月目標報酬 39.1%/64.0% 矛盾。這是可觀測的操作資訊損失，不是品質門檻本身判定錯誤。

核心判斷

1. 人工審核 action、priority `960` 與 `blocks_auto_rerun=true` 必須保留，因為內容矛盾仍需人工判斷。
2. queue detail 應優先呈現 blocking issue 的具體細節，泛化 summary/message 只在沒有細節時 fallback。
3. 修正範圍限於共用 gate summary，避免複製一套 conformance-specific formatter 或放寬自動重跑政策。

落地修改

1. `backend/report_quality_repair_items.py` 的共用 `_summary` 優先讀取 `blocking_issues[].details`。
2. `tests/test_report_quality_repair_queue.py` 鎖住 report conformance 仍人工審核但 detail 具體化。
3. `tests/test_daily_decision_dashboard.py` 鎖住操作員 action 直接收到 blocking detail。

驗證方式

- queue/dashboard regression：`75 passed`。
- 3017 v1 snapshot：detail 由「報告未符合輸出契約，需修正後再採用。」變為完整「建議/報酬矛盾」訊息，action 仍為 `manual_review`。

### 完成後維護 / D3503 / #拆解問題 #問對問題 #差距分析 #偏誤降低 #決策樹 #效用 #證據基礎 #比較組 #介入研究 #可驗證性 #來源品質

本次使用：live artifact scan 顯示 1334 份 data snapshot 中有 21 份 `final_audit` blocked；最近 dashboard sample 20 份有 13 份需修復、8 份 blocked。主要阻斷細節是 Agent 輸出失敗，但 repair queue 原本一律導向人工審核並阻擋自動重跑，與 final audit 的「重新執行本 Agent」修復指示不一致。

核心判斷

1. `輸出為失敗訊息`、`缺少 Agent 輸出`、`仍含佔位文字` 是可重試的執行失敗訊號，應導向完整重跑。
2. 公司身分污染、價格/資料可信度衝突等非可重試內容風險仍須人工審核，不能由 marker 擴張誤判。
3. retry priority 設為 `840`，低於 provider critical `900`，確保來源不可用時仍先等待恢復，不會盲目重跑。

落地修改

1. `backend/report_quality_repair_items.py` 新增 final-audit retry marker 分流，產生 `rerun_analysis`、`完整重跑`、`final_audit_agent_retry`，且 `blocks_auto_rerun=false`。
2. `tests/test_report_quality_repair_queue.py` 鎖住可重試、不可重試與 provider critical precedence 三種邊界。
3. `tests/test_daily_decision_dashboard.py` 鎖住 dashboard action 會轉成 `rerun_report`，而不是 `manual_review`。

驗證方式

- repair queue focused regression：`10 passed, 32 deselected`；queue/dashboard adjacent regression：`12 passed, 61 deselected`。
- provider critical control：仍為 `wait_provider_recovery` 且 `blocks_auto_rerun=true`；company identity control：仍為 `manual_review` 且 `blocks_auto_rerun=true`。
- live runtime evidence：API `healthz` 正常；修改後需重載 API process 才能讓既有長駐 process 讀到新 module。

### 完成後維護 / D3502 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：廣域 parser audit 將五入口測試語料的非明確價格命中縮小到 4 個候選；核對後 3 個是合法價格區間或 AST 組合片段，唯一可修正的通用行政量是 `queue items target 160`，因此以 queue 表達與 state 的小矩陣補強 shared guard。

核心判斷

1. `queue items/work queue` 後接 target state 與數字是行政佇列量，不是股票價格；應與既有具體 queue 名稱使用同一個報告品質邊界。
2. guard 僅涵蓋 `queue items`、`queue item`、`queue reviews`、`work queue` 四種表達及五種 state，共 20 cases；不改變 `time to price` 或明確 target price 的金融語意。
3. 混合句 `target price NT$205 with queue items target 160` 必須保留 `[205.0]`，用來防止非價格清理誤刪合法價格。

落地修改

1. `backend/price_parser.py` 新增 `QUALITY_SERVICE_QUEUE_METRIC_PATTERN` 與 value pattern，接入 parser early return 與 value stripping；維持 349 行。
2. `backend/report_target_price_detection.py` 共用 queue pattern/value pattern，讓 explicit detector 與 parser 的非價格邊界一致；維持 189 行。
3. 五個報告品質入口新增 queue metric regression，並將 20 組 bad cases 與 20 組 mixed-valid cases 綁在同一組測試契約。

優化說明

1. 五入口 RED 為 `5 failed, 4370 deselected in 7.56s`；shared queue guard GREEN 為 `5 passed, 4370 deselected in 1.54s`。
2. queue matrix 為 `20 cases / parser_leaks=0 / parser_valid_misses=0`；detector 只保留 mixed-valid explicit field。
3. controls 為 financial `time to price=[]`、explicit target price `[205.0]`、mixed queue target price `[205.0]`；D3501 lifecycle adjacent regression `10 passed, 4365 deselected in 47.07s`。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'generic_queue_metric'`：`5 passed, 4370 deselected in 1.54s`。
- queue matrix：20 cases、parser leaks/valid-misses 皆為 0；detector fields 僅為 mixed-valid explicit field。
- adjacent regression：`10 passed, 4365 deselected in 47.07s`。

### 完成後維護 / D3501 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #來源品質

本次使用：D3500 後 live scan 顯示八組動詞 × lifecycle 五詞排列仍有 `592` 個 residual；先以候選 generic regex 做 960/960 離線 permutation proof，再以五入口廣域 RED/GREEN 與 controls 驗證共享 guard 的安全邊界。

核心判斷

1. 這批 residual 不是新的商業語義，而是同一個 service/lifecycle KPI 的詞序排列；逐 root 累積 pattern 已造成 maintenance cost，應改成受限 permutation guard。
2. 新 guard 只有在 time-to 動詞後出現 validation、recertification、attendance、renewal、certification 五個詞各一次，且接著是 target/forecast/actual/baseline/current state 時才生效；因此不把 financial `time to price`、existing `time to complete course` 或明確 `target price` 當成 service KPI。
3. 五個入口各驗證 960 roots，union 為 4800 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`；post-fix residual scan 為 `960 candidates / residual_count=0`。

落地修改

1. `backend/price_parser.py` 新增共享 `QUALITY_SERVICE_TIME_TO_METRIC_PERMUTATION_PATTERN` 與 value pattern；parser early-return 與 value stripping 都使用它。
2. `backend/report_target_price_detection.py` 匯入並共用 permutation/value guard，讓 explicit detector 與 parser 使用相同語義邊界；維持 parser/detector `349/189` 行契約。
3. 五個報告品質入口新增全 lifecycle permutation regression，涵蓋 8 verbs × 120 permutations，並保留有效 target price 與既有非財務 controls。

優化說明

1. generic guard 前 RED 為 `5 failed, 4365 deselected in 58.79s`；shared guard GREEN 為 `5 passed, 4365 deselected in 47.17s`。
2. generic matrix：parser、calibration、credibility、structured output、detector 各 `960 cases / leaks=0 / valid_misses=0`；union `4800 cases / leaks=0 / valid_misses=0`。
3. controls：financial `time to price=[]`；existing `time to complete course=[]`；explicit target price `[205.0]`；post-fix residual `960 candidates / residual_count=0`。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'all_lifecycle_time_to_metric_permutations'`：RED `5 failed, 4365 deselected in 58.79s`；GREEN `5 passed, 4365 deselected in 47.17s`。
- generic matrix：五入口各 960 cases，union 4800 cases，所有 leaks 與 valid-misses 均為 0。
- candidate scan：`960 candidates / residual_count=0`；financial `time to price=[]`；existing `time to complete course=[]`；explicit target price `[205.0]`。

### 完成後維護 / D3500 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3499 後以八組動詞各掃描 validation、recertification、attendance、renewal、certification 五詞的 120 種排列；前四個未收斂 residual roots 都是 issue attendance recertification validation lifecycle KPI，以 D3499 root、D3498 root、D3497 root、D3496 root 與 explicit target price 作為比較組。

核心判斷

1. `time to issue attendance recertification validation renewal certification`、`time to issue attendance recertification renewal validation certification`、`time to issue attendance recertification certification validation renewal` 與 `time to issue attendance recertification certification renewal validation` 都是 issue attendance recertification validation lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，union 為 880 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3500 四個 roots 納入共享 pattern/value stripping assignment；post-fix 廣域掃描為 `960 candidates / residual_count=592`，下一組 attendance permutation 保留為比較組，避免一次擴大 guard 範圍。

落地修改

1. 五個報告品質入口新增 issue attendance recertification validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 初始 shared time-to branch 加入本批四個 roots，由後續累積 recompile assignment 傳遞到五個既有 consumer，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4360 deselected in 38.34s`；shared guard GREEN 為 `5 passed, 4360 deselected in 24.03s`。
2. D3500 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / leaks=0 / valid_misses=0`，detector `400 cases / leaks=0 / valid_misses=0`，union `880 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、D3494-D3500 controls 均為 `[]`。
3. D3499-D3500 adjacent regression 通過 `10 passed, 4355 deselected in 47.15s`；下一組 attendance permutation residual 保留為下一輪的可驗證比較組。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'issue_attendance_recertification_validation_renewal_certification'`：RED `5 failed, 4360 deselected in 38.34s`；GREEN `5 passed, 4360 deselected in 24.03s`。
- D3500 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `880 cases / leaks=0 / valid_misses=0`。
- D3499-D3500 adjacent regression：`10 passed, 4355 deselected in 47.15s`。
- controls：explicit target price `[205.0]`；D3494-D3500 roots 均為 `[]`；廣域 residual scan `960 candidates / residual_count=592`，next residual `time to issue attendance renewal validation recertification certification` 為 `[12.0]`。

### 完成後維護 / D3499 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3498 後以八組動詞各掃描 validation、recertification、attendance、renewal、certification 五詞的 120 種排列；前四個未收斂 residual roots 都是 issue attendance validation lifecycle KPI，以 D3498 root、D3497 root、D3496 root、D3495 root 與 explicit target price 作為比較組。

核心判斷

1. `time to issue attendance validation recertification renewal certification`、`time to issue attendance validation renewal recertification certification`、`time to issue attendance validation renewal certification recertification` 與 `time to issue attendance validation certification renewal recertification` 都是 issue attendance validation lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，union 為 880 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3499 四個 roots 納入共享 pattern/value stripping assignment；post-fix 廣域掃描為 `960 candidates / residual_count=596`，下一組 attendance permutation 保留為比較組，避免一次擴大 guard 範圍。

落地修改

1. 五個報告品質入口新增 issue attendance validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 初始 shared time-to branch 加入本批四個 roots，由後續累積 recompile assignment 傳遞到五個既有 consumer，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4355 deselected in 38.08s`；shared guard GREEN 為 `5 passed, 4355 deselected in 24.76s`。
2. D3499 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / leaks=0 / valid_misses=0`，detector `400 cases / leaks=0 / valid_misses=0`，union `880 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、D3494-D3499 controls 均為 `[]`。
3. D3498-D3499 adjacent regression 通過 `10 passed, 4350 deselected in 47.96s`；下一組 attendance permutation residual 保留為下一輪的可驗證比較組。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'issue_attendance_validation_recertification_renewal_certification'`：RED `5 failed, 4355 deselected in 38.08s`；GREEN `5 passed, 4355 deselected in 24.76s`。
- D3499 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `880 cases / leaks=0 / valid_misses=0`。
- D3498-D3499 adjacent regression：`10 passed, 4350 deselected in 47.96s`。
- controls：explicit target price `[205.0]`；D3494-D3499 roots 均為 `[]`；廣域 residual scan `960 candidates / residual_count=596`，next residual `time to issue attendance recertification validation renewal certification` 為 `[12.0]`。

### 完成後維護 / D3498 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3497 後以八組動詞各掃描 validation、recertification、attendance、renewal、certification 五詞的 120 種排列；前四個未收斂 residual roots 都是 issue validation renewal/certification lifecycle KPI，以 D3497 root、D3496 root、D3495 root、D3494 root 與 explicit target price 作為比較組。

核心判斷

1. `time to issue validation renewal certification recertification attendance`、`time to issue validation renewal certification attendance recertification`、`time to issue validation certification attendance renewal recertification` 與 `time to issue validation certification renewal attendance recertification` 都是 issue validation renewal/certification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，union 為 880 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3498 四個 roots 納入共享 pattern/value stripping assignment；post-fix 廣域掃描為 `960 candidates / residual_count=600`，下一組 issue/attendance permutation 保留為比較組，避免一次擴大 guard 範圍。

落地修改

1. 五個報告品質入口新增 issue validation renewal/certification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 初始 shared time-to branch 加入本批四個 roots，由後續累積 recompile assignment 傳遞到五個既有 consumer，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4350 deselected in 38.10s`；shared guard GREEN 為 `5 passed, 4350 deselected in 24.54s`。
2. D3498 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / leaks=0 / valid_misses=0`，detector `400 cases / leaks=0 / valid_misses=0`，union `880 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、D3494-D3498 controls 均為 `[]`。
3. D3497-D3498 adjacent regression 通過 `10 passed, 4345 deselected in 47.69s`；下一組 issue/attendance permutation residual 保留為下一輪的可驗證比較組。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'issue_validation_renewal_certification_recertification_attendance'`：RED `5 failed, 4350 deselected in 38.10s`；GREEN `5 passed, 4350 deselected in 24.54s`。
- D3498 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `880 cases / leaks=0 / valid_misses=0`。
- D3497-D3498 adjacent regression：`10 passed, 4345 deselected in 47.69s`。
- controls：explicit target price `[205.0]`；D3494-D3498 roots 均為 `[]`；廣域 residual scan `960 candidates / residual_count=600`，next residual `time to issue attendance validation recertification renewal certification` 為 `[12.0]`。

### 完成後維護 / D3497 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3496 後以八組動詞各掃描 validation、recertification、attendance、renewal、certification 五詞的 120 種排列；前四個未收斂 residual roots 都是 issue validation attendance/renewal lifecycle KPI，以 D3496 root、D3495 root、D3494 root 與 explicit target price 作為比較組。

核心判斷

1. `time to issue validation attendance renewal recertification certification`、`time to issue validation renewal recertification attendance certification`、`time to issue validation renewal recertification certification attendance` 與 `time to issue validation renewal attendance recertification certification` 都是 issue validation attendance/renewal lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，union 為 880 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3497 四個 roots 納入共享 pattern/value stripping assignment；post-fix 廣域掃描為 `960 candidates / residual_count=604`，下一組 issue permutation 保留為比較組，避免一次擴大 guard 範圍。

落地修改

1. 五個報告品質入口新增 issue validation attendance/renewal lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 初始 shared time-to branch 加入本批四個 roots，由後續累積 recompile assignment 傳遞到五個既有 consumer，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4345 deselected in 37.86s`；shared guard GREEN 為 `5 passed, 4345 deselected in 24.47s`。
2. D3497 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / leaks=0 / valid_misses=0`，detector `400 cases / leaks=0 / valid_misses=0`，union `880 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、D3494-D3497 controls 均為 `[]`。
3. D3496-D3497 adjacent regression 通過 `10 passed, 4340 deselected in 47.62s`；下一組 issue permutation residual 保留為下一輪的可驗證比較組。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'issue_validation_attendance_renewal_recertification_certification'`：RED `5 failed, 4345 deselected in 37.86s`；GREEN `5 passed, 4345 deselected in 24.47s`。
- D3497 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `880 cases / leaks=0 / valid_misses=0`。
- D3496-D3497 adjacent regression：`10 passed, 4340 deselected in 47.62s`。
- controls：explicit target price `[205.0]`；D3494-D3497 roots 均為 `[]`；廣域 residual scan `960 candidates / residual_count=604`，next residual `time to issue validation renewal certification recertification attendance` 為 `[12.0]`。

### 完成後維護 / D3496 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3495 後以八組動詞各掃描 validation、recertification、attendance、renewal、certification 五詞的 120 種排列；前四個未收斂 residual roots 都是 issue validation recertification renewal/certification lifecycle KPI，以 D3495 root、D3494 root 與 explicit target price 作為比較組。

核心判斷

1. `time to issue validation recertification renewal attendance certification`、`time to issue validation recertification renewal certification attendance`、`time to issue validation recertification certification attendance renewal` 與 `time to issue validation recertification certification renewal attendance` 都是 issue validation recertification renewal/certification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，union 為 880 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3496 四個 roots 納入共享 pattern/value stripping assignment；post-fix 廣域掃描為 `960 candidates / residual_count=608`，下一組 issue permutation 保留為比較組，避免一次擴大 guard 範圍。

落地修改

1. 五個報告品質入口新增 issue validation recertification renewal/certification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 初始 shared time-to branch 加入本批四個 roots，由後續累積 recompile assignment 傳遞到五個既有 consumer，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4340 deselected in 38.09s`；shared guard GREEN 為 `5 passed, 4340 deselected in 24.87s`。
2. D3496 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / leaks=0 / valid_misses=0`，detector `400 cases / leaks=0 / valid_misses=0`，union `880 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、D3494、D3495 與 D3496 controls 均為 `[]`。
3. D3495-D3496 adjacent regression 通過 `10 passed, 4335 deselected in 30.72s`；下一組 issue permutation residual 保留為下一輪的可驗證比較組。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'issue_validation_recertification_renewal_attendance_certification'`：RED `5 failed, 4340 deselected in 38.09s`；GREEN `5 passed, 4340 deselected in 24.87s`。
- D3496 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `880 cases / leaks=0 / valid_misses=0`。
- D3495-D3496 adjacent regression：`10 passed, 4335 deselected in 30.72s`。
- controls：explicit target price `[205.0]`；D3494、D3495 與 D3496 roots 均為 `[]`；廣域 residual scan `960 candidates / residual_count=608`，next residual `time to issue validation attendance renewal recertification certification` 為 `[12.0]`。

### 完成後維護 / D3495 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3494 後以 `renew/issue/verify/schedule/complete/attend/validate/certify` 八組動詞各掃描 validation、recertification、attendance、renewal、certification 五詞的 120 種排列，共 960 candidates；第一個未收斂 residual root 是 issue validation recertification attendance renewal certification lifecycle KPI，以 D3494 root 與 explicit target price 作為比較組。

核心判斷

1. `time to issue validation recertification attendance renewal certification` 是 issue validation recertification attendance renewal certification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 單一 root 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 120 cases，detector 為 100 cases，union 為 220 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3495 root 納入共享 pattern/value stripping assignment；post-fix 廣域掃描為 `960 candidates / residual_count=612`，下一個 residual 保留為比較組，避免一次擴大 guard 範圍。

落地修改

1. 五個報告品質入口新增 issue validation recertification attendance renewal certification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 120 組語料，detector 依既有 path boundary 覆蓋 100 組語料。
2. `backend/price_parser.py` 初始 shared time-to branch 加入本批 root，由後續累積 recompile assignment 傳遞到五個既有 consumer，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4335 deselected in 14.54s`；shared guard GREEN 為 `5 passed, 4335 deselected in 6.75s`。
2. D3495 post-fix matrix 為 parser、calibration、credibility、structured output 各 `120 cases / leaks=0 / valid_misses=0`，detector `100 cases / leaks=0 / valid_misses=0`，union `220 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、D3494 root 與 D3495 root controls 均為 `[]`。
3. D3494-D3495 adjacent regression 通過 `10 passed, 4330 deselected in 12.52s`；下一個 issue permutation residual 保留為下一輪的可驗證比較組。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'issue_validation_recertification_attendance_renewal_certification'`：RED `5 failed, 4335 deselected in 14.54s`；GREEN `5 passed, 4335 deselected in 6.75s`。
- D3495 post-fix matrix：四入口各 `120 cases / leaks=0 / valid_misses=0`；detector `100 cases / leaks=0 / valid_misses=0`；union `220 cases / leaks=0 / valid_misses=0`。
- D3494-D3495 adjacent regression：`10 passed, 4330 deselected in 12.52s`。
- controls：explicit target price `[205.0]`；D3494 與 D3495 root 均為 `[]`；廣域 residual scan `960 candidates / residual_count=612`，next residual `time to issue validation recertification renewal attendance certification` 為 `[12.0]`。

### 完成後維護 / D3494 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3493 後重新掃描 `renew + attendance/validation/recertification/renewal/certification` 的 120 種排列；唯一未收斂 residual root 是 validation certification renewal recertification attendance lifecycle KPI，以 existing course guard、D3493 root 與 explicit target price 作為比較組。

核心判斷

1. `time to renew validation certification renewal recertification attendance` 是 validation certification renewal recertification attendance lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 單一 root 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 120 cases，detector 為 100 cases，union 為 220 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3472、D3473、D3474、D3475、D3476、D3477、D3478、D3479、D3480、D3481、D3482、D3483、D3484、D3485、D3486、D3487、D3488、D3489、D3490、D3491、D3492、D3493 與 D3494 root 一起保留在累積 shared pattern/value stripping assignment；post-fix 120 permutations `residual_count=0`。

落地修改

1. 五個報告品質入口新增最後一個 validation certification renewal recertification attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 120 組語料，detector 依既有 path boundary 覆蓋 100 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批 root，並保留 D3472-D3493 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4330 deselected in 14.68s`；shared guard GREEN 為 `5 passed, 4330 deselected in 6.87s`。
2. D3494 post-fix matrix 為 parser、calibration、credibility、structured output 各 `120 cases / leaks=0 / valid_misses=0`，detector `100 cases / leaks=0 / valid_misses=0`，union `220 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、existing course、D3493 root 與 D3494 root controls 均為 `[]`。
3. D3493-D3494 adjacent regression 通過 `10 passed, 4325 deselected in 30.23s`；post-fix residual scan 已無剩餘 root。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'validation_certification_renewal_recertification_attendance'`：RED `5 failed, 4330 deselected in 14.68s`；GREEN `5 passed, 4330 deselected in 6.87s`。
- D3494 post-fix matrix：四入口各 `120 cases / leaks=0 / valid_misses=0`；detector `100 cases / leaks=0 / valid_misses=0`；union `220 cases / leaks=0 / valid_misses=0`。
- D3493-D3494 adjacent regression：`10 passed, 4325 deselected in 30.23s`。
- controls：explicit target price `[205.0]`；existing course、D3493 root 與 D3494 root 均為 `[]`；post-fix residual scan `120 permutations / residual_count=0`。

### 完成後維護 / D3493 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3492 後重新掃描 `renew + attendance/validation/recertification/renewal/certification` 的 120 種排列；前四個未收斂 residual roots 都是 validation certification attendance/renewal recertification lifecycle KPI 誤判組，以 existing course guard、D3490-D3492 cumulative roots 與 explicit target price 作為比較組。

核心判斷

1. `time to renew validation certification attendance renewal recertification`、`time to renew validation certification recertification attendance renewal`、`time to renew validation certification recertification renewal attendance` 與 `time to renew validation certification renewal attendance recertification` 都是 validation certification attendance/renewal recertification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，union 為 880 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3472、D3473、D3474、D3475、D3476、D3477、D3478、D3479、D3480、D3481、D3482、D3483、D3484、D3485、D3486、D3487、D3488、D3489、D3490、D3491、D3492 與 D3493 roots 一起保留在累積 shared pattern/value stripping assignment；下一輪代表性 residual `planning metric time to renew validation certification renewal recertification attendance target 12 個` 只回傳 `[12.0]`。

落地修改

1. 五個報告品質入口新增 validation certification attendance renewal recertification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批四個 roots，並保留 D3472-D3492 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4325 deselected in 37.93s`；shared guard GREEN 為 `5 passed, 4325 deselected in 24.08s`。
2. D3493 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / leaks=0 / valid_misses=0`，detector `400 cases / leaks=0 / valid_misses=0`，union `880 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、existing course、D3490-D3492 cumulative roots 與 D3493 roots controls 均為 `[]`。
3. D3492-D3493 adjacent regression 通過 `10 passed, 4320 deselected in 47.21s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'validation_certification_attendance_renewal_recertification'`：RED `5 failed, 4325 deselected in 37.93s`；GREEN `5 passed, 4325 deselected in 24.08s`。
- D3493 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `880 cases / leaks=0 / valid_misses=0`。
- D3492-D3493 adjacent regression：`10 passed, 4320 deselected in 47.21s`。
- controls：explicit target price `[205.0]`；existing course、D3490-D3492 cumulative roots 與 D3493 roots 均為 `[]`；next residual `planning metric time to renew validation certification renewal recertification attendance target 12 個` 為 `[12.0]`。

### 完成後維護 / D3492 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3491 後重新掃描 `renew + attendance/validation/recertification/renewal/certification` 的 120 種排列；前四個未收斂 residual roots 都是 validation renewal recertification/certification attendance lifecycle KPI 誤判組，以 existing course guard、D3490-D3491 cumulative roots 與 explicit target price 作為比較組。

核心判斷

1. `time to renew validation renewal recertification attendance certification`、`time to renew validation renewal recertification certification attendance`、`time to renew validation renewal certification attendance recertification` 與 `time to renew validation renewal certification recertification attendance` 都是 validation renewal recertification/certification attendance lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，union 為 880 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3472、D3473、D3474、D3475、D3476、D3477、D3478、D3479、D3480、D3481、D3482、D3483、D3484、D3485、D3486、D3487、D3488、D3489、D3490、D3491 與 D3492 roots 一起保留在累積 shared pattern/value stripping assignment；下一輪代表性 residual `planning metric time to renew validation certification attendance renewal recertification target 12 個` 只回傳 `[12.0]`。

落地修改

1. 五個報告品質入口新增 validation renewal recertification/certification attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批四個 roots，並保留 D3472-D3491 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4320 deselected in 38.04s`；shared guard GREEN 為 `5 passed, 4320 deselected in 24.11s`。
2. D3492 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / leaks=0 / valid_misses=0`，detector `400 cases / leaks=0 / valid_misses=0`，union `880 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、existing course、D3490-D3491 cumulative roots 與 D3492 roots controls 均為 `[]`。
3. D3491-D3492 adjacent regression 通過 `10 passed, 4315 deselected in 47.29s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'validation_renewal_recertification_attendance_certification'`：RED `5 failed, 4320 deselected in 38.04s`；GREEN `5 passed, 4320 deselected in 24.11s`。
- D3492 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `880 cases / leaks=0 / valid_misses=0`。
- D3491-D3492 adjacent regression：`10 passed, 4315 deselected in 47.29s`。
- controls：explicit target price `[205.0]`；existing course、D3490-D3491 cumulative roots 與 D3492 roots 均為 `[]`；next residual `planning metric time to renew validation certification attendance renewal recertification target 12 個` 為 `[12.0]`。

### 完成後維護 / D3491 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3490 後重新掃描 `renew + attendance/validation/recertification/renewal/certification` 的 120 種排列；前四個未收斂 residual roots 都是 validation attendance/recertification renewal certification lifecycle KPI 誤判組，以 existing course guard、D3490 roots 與 explicit target price 作為比較組。

核心判斷

1. `time to renew validation attendance recertification renewal certification`、`time to renew validation attendance renewal recertification certification`、`time to renew validation recertification certification renewal attendance` 與 `time to renew validation renewal attendance recertification certification` 都是 validation attendance/recertification renewal certification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，union 為 880 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3472、D3473、D3474、D3475、D3476、D3477、D3478、D3479、D3480、D3481、D3482、D3483、D3484、D3485、D3486、D3487、D3488、D3489、D3490 與 D3491 roots 一起保留在累積 shared pattern/value stripping assignment；下一輪代表性 residual `planning metric time to renew validation renewal recertification attendance certification target 12 個` 只回傳 `[12.0]`。

落地修改

1. 五個報告品質入口新增 validation attendance/recertification renewal certification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批四個 roots，並保留 D3472-D3490 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4315 deselected in 38.72s`；shared guard GREEN 為 `5 passed, 4315 deselected in 24.16s`。
2. D3491 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / leaks=0 / valid_misses=0`，detector `400 cases / leaks=0 / valid_misses=0`，union `880 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、existing course、D3490 root 與 D3491 roots controls 均為 `[]`。
3. D3490-D3491 adjacent regression 通過 `10 passed, 4310 deselected in 47.58s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'validation_attendance_recertification_renewal_certification'`：RED `5 failed, 4315 deselected in 38.72s`；GREEN `5 passed, 4315 deselected in 24.16s`。
- D3491 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `880 cases / leaks=0 / valid_misses=0`。
- D3490-D3491 adjacent regression：`10 passed, 4310 deselected in 47.58s`。
- controls：explicit target price `[205.0]`；existing course、D3490 root 與 D3491 roots 均為 `[]`；next residual `planning metric time to renew validation renewal recertification attendance certification target 12 個` 為 `[12.0]`。

### 完成後維護 / D3490 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3489 後重新掃描 `renew + attendance/validation/recertification/renewal/certification` 的 120 種排列；前四個未收斂 residual roots 都是 validation recertification attendance/renewal certification lifecycle KPI 誤判組，以 existing course guard、D3489 roots 與 explicit target price 作為比較組。

核心判斷

1. `time to renew validation recertification attendance renewal certification`、`time to renew validation recertification renewal attendance certification`、`time to renew validation recertification renewal certification attendance` 與 `time to renew validation recertification certification attendance renewal` 都是 validation recertification attendance/renewal certification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，union 為 880 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3472、D3473、D3474、D3475、D3476、D3477、D3478、D3479、D3480、D3481、D3482、D3483、D3484、D3485、D3486、D3487、D3488、D3489 與 D3490 roots 一起保留在累積 shared pattern/value stripping assignment；下一輪代表性 residual `planning metric time to renew validation attendance recertification renewal certification target 12 個` 只回傳 `[12.0]`。

落地修改

1. 五個報告品質入口新增 validation recertification attendance renewal certification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批四個 roots，並保留 D3472-D3489 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4310 deselected in 35.66s`；shared guard GREEN 為 `5 passed, 4310 deselected in 22.61s`。
2. D3490 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / leaks=0 / valid_misses=0`，detector `400 cases / leaks=0 / valid_misses=0`，union `880 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、existing course、D3489 root 與 D3490 root controls 均為 `[]`。
3. D3489-D3490 adjacent regression 通過 `10 passed, 4305 deselected in 46.99s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_validation_recertification_attendance_renewal_certification'`：RED `5 failed, 4310 deselected in 35.66s`；GREEN `5 passed, 4310 deselected in 22.61s`。
- D3490 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `880 cases / leaks=0 / valid_misses=0`。
- D3489-D3490 adjacent regression：`10 passed, 4305 deselected in 46.99s`。
- controls：explicit target price `[205.0]`；existing course、D3489 root 與 D3490 root 均為 `[]`；next residual `planning metric time to renew validation attendance recertification renewal certification target 12 個` 為 `[12.0]`。

### 完成後維護 / D3489 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3488 後重新掃描 `renew + attendance/validation/recertification/renewal/certification` 的 120 種排列；前四個未收斂 residual roots 都是 attendance validation/recertification renewal certification lifecycle KPI 誤判組，以 existing course guard、D3488 roots 與 explicit target price 作為比較組。

核心判斷

1. `time to renew attendance validation recertification renewal certification`、`time to renew attendance validation renewal recertification certification`、`time to renew attendance validation renewal certification recertification` 與 `time to renew attendance validation certification renewal recertification` 都是 attendance validation/recertification renewal certification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，union 為 880 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3472、D3473、D3474、D3475、D3476、D3477、D3478、D3479、D3480、D3481、D3482、D3483、D3484、D3485、D3486、D3487、D3488 與 D3489 roots 一起保留在累積 shared pattern/value stripping assignment；下一輪代表性 residual `planning metric time to renew validation recertification attendance renewal certification target 12 個` 只回傳 `[12.0]`。

落地修改

1. 五個報告品質入口新增 attendance validation/recertification renewal certification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批四個 roots，並保留 D3472-D3488 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4305 deselected in 33.22s`；shared guard GREEN 為 `5 passed, 4305 deselected in 23.58s`。
2. D3489 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / leaks=0 / valid_misses=0`，detector `400 cases / leaks=0 / valid_misses=0`，union `880 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、existing course、D3488 root 與 D3489 root controls 均為 `[]`。
3. D3488-D3489 adjacent regression 通過 `10 passed, 4300 deselected in 46.52s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_attendance_validation_recertification_renewal_certification'`：RED `5 failed, 4305 deselected in 33.22s`；GREEN `5 passed, 4305 deselected in 23.58s`。
- D3489 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `880 cases / leaks=0 / valid_misses=0`。
- D3488-D3489 adjacent regression：`10 passed, 4300 deselected in 46.52s`。
- controls：explicit target price `[205.0]`；existing course、D3488 root 與 D3489 root 均為 `[]`；next residual `planning metric time to renew validation recertification attendance renewal certification target 12 個` 為 `[12.0]`。

### 完成後維護 / D3488 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3487 後重新掃描 `renew + attendance/renewal/recertification/certification/validation` 的 120 種排列；前四個未收斂 residual roots 都是 attendance renewal/recertification certification validation lifecycle KPI 誤判組，以 existing course guard、D3487 roots 與 explicit target price 作為比較組。

核心判斷

1. `time to renew attendance renewal recertification certification validation`、`time to renew attendance renewal recertification validation certification`、`time to renew attendance renewal validation recertification certification` 與 `time to renew attendance renewal validation certification recertification` 都是 attendance renewal/recertification certification validation lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，union 為 880 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3472、D3473、D3474、D3475、D3476、D3477、D3478、D3479、D3480、D3481、D3482、D3483、D3484、D3485、D3486、D3487 與 D3488 roots 一起保留在累積 shared pattern/value stripping assignment；下一輪代表性 residual `planning metric time to renew attendance validation recertification renewal certification target 12 個` 只回傳 `[12.0]`。

落地修改

1. 五個報告品質入口新增 attendance renewal/recertification certification validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批四個 roots，並保留 D3472-D3487 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4300 deselected in 33.50s`；shared guard GREEN 為 `5 passed, 4300 deselected in 23.36s`。
2. D3488 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / leaks=0 / valid_misses=0`，detector `400 cases / leaks=0 / valid_misses=0`，union `880 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、existing course、D3487 root 與 D3488 root controls 均為 `[]`。
3. D3487-D3488 adjacent regression 通過 `10 passed, 4295 deselected in 45.99s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_attendance_renewal_recertification_certification_validation'`：RED `5 failed, 4300 deselected in 33.50s`；GREEN `5 passed, 4300 deselected in 23.36s`。
- D3488 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `880 cases / leaks=0 / valid_misses=0`。
- D3487-D3488 adjacent regression：`10 passed, 4295 deselected in 45.99s`。
- controls：explicit target price `[205.0]`；existing course、D3487 root 與 D3488 root 均為 `[]`；next residual `planning metric time to renew attendance validation recertification renewal certification target 12 個` 為 `[12.0]`。

### 完成後維護 / D3487 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3486 後重新掃描 `renew + attendance/recertification/renewal/certification/validation` 的 120 種排列；前四個未收斂 residual roots 都是 attendance recertification/renewal certification validation lifecycle KPI 誤判組，以 existing course guard、D3486 roots 與 explicit target price 作為比較組。

核心判斷

1. `time to renew attendance recertification renewal certification validation`、`time to renew attendance recertification renewal validation certification`、`time to renew attendance recertification certification renewal validation` 與 `time to renew attendance recertification certification validation renewal` 都是 attendance recertification/renewal certification validation lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，union 為 880 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3472、D3473、D3474、D3475、D3476、D3477、D3478、D3479、D3480、D3481、D3482、D3483、D3484、D3485、D3486 與 D3487 roots 一起保留在累積 shared pattern/value stripping assignment；下一輪代表性 residual `planning metric time to renew attendance renewal recertification certification validation target 12 個` 只回傳 `[12.0]`。

落地修改

1. 五個報告品質入口新增 attendance recertification/renewal certification validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批四個 roots，並保留 D3472-D3486 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4295 deselected in 32.79s`；shared guard GREEN 為 `5 passed, 4295 deselected in 22.83s`。
2. D3487 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / leaks=0 / valid_misses=0`，detector `400 cases / leaks=0 / valid_misses=0`，union `880 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、existing course、D3486 root 與 D3487 root controls 均為 `[]`。
3. D3486-D3487 adjacent regression 通過 `10 passed, 4290 deselected in 44.79s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_attendance_recertification_renewal_certification_validation'`：RED `5 failed, 4295 deselected in 32.79s`；GREEN `5 passed, 4295 deselected in 22.83s`。
- D3487 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `880 cases / leaks=0 / valid_misses=0`。
- D3486-D3487 adjacent regression：`10 passed, 4290 deselected in 44.79s`。
- controls：explicit target price `[205.0]`；existing course、D3486 root 與 D3487 root 均為 `[]`；next residual `planning metric time to renew attendance renewal recertification certification validation target 12 個` 為 `[12.0]`。

### 完成後維護 / D3486 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3485 後重新掃描 `renew + attendance/certification/renewal/validation/recertification` 的 120 種排列；前四個未收斂 residual roots 都是 attendance certification/renewal validation recertification lifecycle KPI 誤判組，以 financial time-to、existing course guard、D3485 roots 與 explicit target price 作為比較組。

核心判斷

1. `time to renew attendance certification renewal validation recertification`、`time to renew attendance certification recertification renewal validation`、`time to renew attendance certification validation renewal recertification` 與 `time to renew attendance renewal certification validation recertification` 都是 attendance certification/renewal validation recertification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，union 為 880 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3472、D3473、D3474、D3475、D3476、D3477、D3478、D3479、D3480、D3481、D3482、D3483、D3484、D3485 與 D3486 roots 一起保留在累積 shared pattern/value stripping assignment；下一輪代表性 residual `planning metric time to renew attendance recertification renewal certification validation target 12 個` 只回傳 `[12.0]`。

落地修改

1. 五個報告品質入口新增 attendance certification/renewal validation recertification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批四個 roots，並保留 D3472-D3485 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4290 deselected in 35.60s`；shared guard GREEN 為 `5 passed, 4290 deselected in 22.64s`。
2. D3486 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / leaks=0 / valid_misses=0`，detector `400 cases / leaks=0 / valid_misses=0`，union `880 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、D3485 root 與 D3486 root controls 均為 `[]`。
3. D3485-D3486 adjacent regression 通過 `10 passed, 4285 deselected in 44.78s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_attendance_certification_renewal_validation_recertification'`：RED `5 failed, 4290 deselected in 35.60s`；GREEN `5 passed, 4290 deselected in 22.64s`。
- D3486 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `880 cases / leaks=0 / valid_misses=0`。
- D3485-D3486 adjacent regression：`10 passed, 4285 deselected in 44.78s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、D3485 root 與 D3486 root 均為 `[]`；next residual `planning metric time to renew attendance recertification renewal certification validation target 12 個` 為 `[12.0]`。

### 完成後維護 / D3485 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3484 後重新掃描 `renew + certification/renewal/recertification/attendance/validation` 的 120 種排列；前四個未收斂 residual roots 各為 recertification attendance/validation lifecycle KPI 誤判組，以 financial time-to、existing course guard、D3484 roots 與 explicit target price 作為比較組。

核心判斷

1. `time to renew recertification attendance renewal certification validation`、`time to renew recertification validation certification renewal attendance`、`time to renew recertification validation certification attendance renewal` 與 `time to renew recertification validation renewal certification attendance` 都是 recertification attendance/validation lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，union 為 880 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3472、D3473、D3474、D3475、D3476、D3477、D3478、D3479、D3480、D3481、D3482、D3483、D3484 與 D3485 roots 一起保留在累積 shared pattern/value stripping assignment；下一輪代表性 residual `planning metric time to renew attendance certification renewal validation recertification forecast 12 個` 只回傳 `[12.0]`。

落地修改

1. 五個報告品質入口新增 recertification attendance/validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批四個 roots，並保留 D3472-D3484 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4285 deselected in 35.80s`；shared guard GREEN 為 `5 passed, 4285 deselected in 22.70s`。
2. D3485 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / leaks=0 / valid_misses=0`，detector `400 cases / leaks=0 / valid_misses=0`，union `880 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、D3484 root 與 D3485 root controls 均為 `[]`。
3. D3484-D3485 adjacent regression 通過 `10 passed, 4280 deselected in 44.84s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_recertification_attendance_renewal_certification_validation'`：RED `5 failed, 4285 deselected in 35.80s`；GREEN `5 passed, 4285 deselected in 22.70s`。
- D3485 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `880 cases / leaks=0 / valid_misses=0`。
- D3484-D3485 adjacent regression：`10 passed, 4280 deselected in 44.84s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、D3484 root 與 D3485 root 均為 `[]`；next residual `planning metric time to renew attendance certification renewal validation recertification forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3484 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3483 後重新掃描 `renew + certification/renewal/recertification/attendance/validation` 的 120 種排列；前四個未收斂 residual roots 各為 recertification renewal/attendance certification lifecycle KPI 誤判組，以 financial time-to、existing course guard、D3483 roots 與 explicit target price 作為比較組。

核心判斷

1. `time to renew recertification renewal attendance certification validation`、`time to renew recertification renewal validation certification attendance`、`time to renew recertification attendance certification renewal validation` 與 `time to renew recertification attendance certification validation renewal` 都是 recertification renewal/attendance certification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，union 為 880 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3472、D3473、D3474、D3475、D3476、D3477、D3478、D3479、D3480、D3481、D3482、D3483 與 D3484 roots 一起保留在累積 shared pattern/value stripping assignment；下一輪代表性 residual `planning metric time to renew recertification attendance renewal certification validation forecast 12 個` 只回傳 `[12.0]`。

落地修改

1. 五個報告品質入口新增 recertification renewal attendance certification validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批四個 roots，並保留 D3472-D3483 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4280 deselected in 35.89s`；shared guard GREEN 為 `5 passed, 4280 deselected in 22.59s`。
2. D3484 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / leaks=0 / valid_misses=0`，detector `400 cases / leaks=0 / valid_misses=0`，union `880 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、D3483 root 與 D3484 root controls 均為 `[]`。
3. D3483-D3484 adjacent regression 通過 `10 passed, 4275 deselected in 44.86s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_recertification_renewal_attendance_certification_validation'`：RED `5 failed, 4280 deselected in 35.89s`；GREEN `5 passed, 4280 deselected in 22.59s`。
- D3484 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `880 cases / leaks=0 / valid_misses=0`。
- D3483-D3484 adjacent regression：`10 passed, 4275 deselected in 44.86s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、D3483 root 與 D3484 root 均為 `[]`；next residual `planning metric time to renew recertification attendance renewal certification validation forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3483 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3482 後重新掃描 `renew + certification/renewal/recertification/attendance/validation` 的 120 種排列；前四個未收斂 residual roots 各為 recertification certification validation/renewal lifecycle KPI 誤判組，以 financial time-to、existing course guard、D3482 roots 與 explicit target price 作為比較組。

核心判斷

1. `time to renew recertification certification validation renewal attendance`、`time to renew recertification certification validation attendance renewal`、`time to renew recertification renewal certification attendance validation` 與 `time to renew recertification renewal certification validation attendance` 都是 recertification certification validation/renewal lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，union 為 880 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3472、D3473、D3474、D3475、D3476、D3477、D3478、D3479、D3480、D3481、D3482 與 D3483 roots 一起保留在累積 shared pattern/value stripping assignment；下一輪代表性 residual `planning metric time to renew recertification renewal attendance certification validation forecast 12 個` 只回傳 `[12.0]`。

落地修改

1. 五個報告品質入口新增 recertification certification validation renewal lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批四個 roots，並保留 D3472-D3482 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4275 deselected in 35.91s`；shared guard GREEN 為 `5 passed, 4275 deselected in 22.66s`。
2. D3483 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / leaks=0 / valid_misses=0`，detector `400 cases / leaks=0 / valid_misses=0`，union `880 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、D3482 root 與 D3483 root controls 均為 `[]`。
3. D3482-D3483 adjacent regression 通過 `10 passed, 4270 deselected in 45.02s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_recertification_certification_validation_renewal_attendance'`：RED `5 failed, 4275 deselected in 35.91s`；GREEN `5 passed, 4275 deselected in 22.66s`。
- D3483 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `880 cases / leaks=0 / valid_misses=0`。
- D3482-D3483 adjacent regression：`10 passed, 4270 deselected in 45.02s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、D3482 root 與 D3483 root 均為 `[]`；next residual `planning metric time to renew recertification renewal attendance certification validation forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3482 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3481 後重新掃描 `renew + certification/renewal/recertification/attendance/validation` 的 120 種排列；前四個未收斂 residual roots 各為 recertification certification renewal lifecycle KPI 誤判組，以 financial time-to、existing course guard、D3481 roots 與 explicit target price 作為比較組。

核心判斷

1. `time to renew recertification certification renewal attendance validation`、`time to renew recertification certification renewal validation attendance`、`time to renew recertification certification attendance renewal validation` 與 `time to renew recertification certification attendance validation renewal` 都是 recertification certification renewal lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，union 為 880 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3472、D3473、D3474、D3475、D3476、D3477、D3478、D3479、D3480、D3481 與 D3482 roots 一起保留在累積 shared pattern/value stripping assignment；下一輪代表性 residual `planning metric time to renew recertification certification validation renewal attendance forecast 12 個` 只回傳 `[12.0]`。

落地修改

1. 五個報告品質入口新增 recertification certification renewal attendance validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批四個 roots，並保留 D3472-D3481 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4270 deselected in 36.39s`；shared guard GREEN 為 `5 passed, 4270 deselected in 22.97s`。
2. D3482 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / leaks=0 / valid_misses=0`，detector `400 cases / leaks=0 / valid_misses=0`，union `880 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、D3481 root 與 D3482 root controls 均為 `[]`。
3. D3481-D3482 adjacent regression 通過 `10 passed, 4265 deselected in 44.98s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_recertification_certification_renewal_attendance_validation'`：RED `5 failed, 4270 deselected in 36.39s`；GREEN `5 passed, 4270 deselected in 22.97s`。
- D3482 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `880 cases / leaks=0 / valid_misses=0`。
- D3481-D3482 adjacent regression：`10 passed, 4265 deselected in 44.98s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、D3481 root 與 D3482 root 均為 `[]`；next residual `planning metric time to renew recertification certification validation renewal attendance forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3481 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3480 後重新掃描 `renew + certification/renewal/recertification/attendance/validation` 的 120 種排列；前四個未收斂 residual roots 各為 renewal validation recertification certification lifecycle KPI 誤判組，以 financial time-to、existing course guard、D3480 roots 與 explicit target price 作為比較組。

核心判斷

1. `time to renew renewal validation recertification certification attendance`、`time to renew renewal validation recertification attendance certification`、`time to renew renewal validation attendance certification recertification` 與 `time to renew renewal validation attendance recertification certification` 都是 renewal validation recertification certification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，union 為 880 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3472、D3473、D3474、D3475、D3476、D3477、D3478、D3479、D3480 與 D3481 roots 一起保留在累積 shared pattern/value stripping assignment；下一輪代表性 residual `planning metric time to renew recertification certification renewal attendance validation forecast 12 個` 只回傳 `[12.0]`。

落地修改

1. 五個報告品質入口新增 renewal renewal validation recertification certification attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批四個 roots，並保留 D3472-D3480 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4265 deselected in 35.79s`；shared guard GREEN 為 `5 passed, 4265 deselected in 23.18s`。
2. D3481 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / leaks=0 / valid_misses=0`，detector `400 cases / leaks=0 / valid_misses=0`，union `880 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、D3480 root 與 D3481 root controls 均為 `[]`。
3. D3480-D3481 adjacent regression 通過 `10 passed, 4260 deselected in 46.04s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_renewal_validation_recertification_certification_attendance'`：RED `5 failed, 4265 deselected in 35.79s`；GREEN `5 passed, 4265 deselected in 23.18s`。
- D3481 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `880 cases / leaks=0 / valid_misses=0`。
- D3480-D3481 adjacent regression：`10 passed, 4260 deselected in 46.04s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、D3480 root 與 D3481 root 均為 `[]`；next residual `planning metric time to renew recertification certification renewal attendance validation forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3480 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3479 後重新掃描 `renew + certification/renewal/recertification/attendance/validation` 的 120 種排列；前四個未收斂 residual roots 各為 renewal attendance recertification certification lifecycle KPI 誤判組，以 financial time-to、existing course guard、D3479 roots 與 explicit target price 作為比較組。

核心判斷

1. `time to renew renewal attendance recertification validation certification`、`time to renew renewal attendance validation certification recertification`、`time to renew renewal attendance validation recertification certification` 與 `time to renew renewal validation certification recertification attendance` 都是 renewal attendance recertification certification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，union 為 880 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3472、D3473、D3474、D3475、D3476、D3477、D3478、D3479 與 D3480 roots 一起保留在累積 shared pattern/value stripping assignment；下一輪代表性 residual `planning metric time to renew renewal validation recertification certification attendance forecast 12 個` 只回傳 `[12.0]`。

落地修改

1. 五個報告品質入口新增 renewal renewal attendance validation certification recertification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批四個 roots，並保留 D3472-D3479 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4260 deselected in 38.03s`；shared guard GREEN 為 `5 passed, 4260 deselected in 23.14s`。
2. D3480 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / leaks=0 / valid_misses=0`，detector `400 cases / leaks=0 / valid_misses=0`，union `880 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、D3479 root 與 D3480 root controls 均為 `[]`。
3. D3479-D3480 adjacent regression 通過 `10 passed, 4255 deselected in 45.64s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_renewal_attendance_validation_certification_recertification'`：RED `5 failed, 4260 deselected in 38.03s`；GREEN `5 passed, 4260 deselected in 23.14s`。
- D3480 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `880 cases / leaks=0 / valid_misses=0`。
- D3479-D3480 adjacent regression：`10 passed, 4255 deselected in 45.64s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、D3479 root 與 D3480 root 均為 `[]`；next residual `planning metric time to renew renewal validation recertification certification attendance forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3479 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3478 後重新掃描 `renew + certification/renewal/recertification/attendance/validation` 的 120 種排列；前四個未收斂 residual roots 各為 renewal recertification certification lifecycle KPI 誤判組，以 financial time-to、existing course guard、D3478 roots 與 explicit target price 作為比較組。

核心判斷

1. `time to renew renewal recertification validation certification attendance`、`time to renew renewal recertification validation attendance certification`、`time to renew renewal attendance certification validation recertification` 與 `time to renew renewal attendance recertification certification validation` 都是 renewal recertification certification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3472、D3473、D3474、D3475、D3476、D3477、D3478 與 D3479 roots 一起保留在累積 shared pattern/value stripping assignment；下一輪代表性 residual `planning metric time to renew renewal attendance recertification validation certification forecast 12 個` 只回傳 `[12.0]`。

落地修改

1. 五個報告品質入口新增 renewal renewal recertification validation certification attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批四個 roots，並保留 D3472-D3478 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4255 deselected`；shared guard GREEN 為 `5 passed, 4255 deselected in 23.60s`。
2. D3479 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / leaks=0 / valid_misses=0`，detector `400 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 D3479 root controls 均為 `[]`。
3. D3478-D3479 adjacent regression 通過 `10 passed, 4250 deselected in 45.51s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_renewal_recertification_validation_certification_attendance'`：RED `5 failed, 4255 deselected`；GREEN `5 passed, 4255 deselected in 23.60s`。
- D3479 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- D3478-D3479 adjacent regression：`10 passed, 4250 deselected in 45.51s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course` 與 D3479 root 均為 `[]`；next residual `planning metric time to renew renewal attendance recertification validation certification forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3478 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3477 後重新掃描 `renew + certification/renewal/recertification/attendance/validation` 的排列候選；前四個未收斂 residual roots 各為 lifecycle KPI 誤判組，以 renewal recertification certification attendance validation、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to renew renewal recertification certification attendance validation`、`time to renew renewal recertification certification validation attendance`、`time to renew renewal recertification attendance certification validation` 與 `time to renew renewal recertification attendance validation certification` 都是 renewal recertification certification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3472、D3473、D3474、D3475、D3476、D3477 與 D3478 roots 一起保留在累積 shared pattern/value stripping assignment；下一輪代表性 residual `planning metric time to renew renewal recertification validation certification attendance forecast 12 個` 只回傳 `[12.0]`。

落地修改

1. 五個報告品質入口新增 renewal recertification certification attendance validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批四個 roots，並保留 D3472-D3477 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4250 deselected in 37.04s`；shared guard GREEN 為 `5 passed, 4250 deselected in 22.99s`。
2. D3478 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、D3471 root、D3472 root、D3473 root、D3474 root、D3475 root、D3476 root、D3477 root 與 D3478 roots controls 均為 `[]`。
3. D3477-D3478 adjacent regression 通過 `10 passed, 4245 deselected in 45.61s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_renewal_recertification_certification_attendance_validation'`：RED `5 failed, 4250 deselected in 37.04s`；GREEN `5 passed, 4250 deselected in 22.99s`。
- D3478 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- D3477-D3478 adjacent regression：`10 passed, 4245 deselected in 45.61s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、D3471 root、D3472 root、D3473 root、D3474 root、D3475 root、D3476 root、D3477 root 與 D3478 roots 均為 `[]`；next residual `planning metric time to renew renewal recertification validation certification attendance forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3477 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3476 後重新掃描 `renew + certification/renewal/recertification/attendance/validation` 的排列候選；前四個未收斂 residual roots 各為 lifecycle KPI 誤判組，以 renewal certification attendance recertification validation、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to renew renewal certification attendance recertification validation`、`time to renew renewal certification attendance validation recertification`、`time to renew renewal certification validation recertification attendance` 與 `time to renew renewal certification validation attendance recertification` 都是 renewal certification recertification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3472、D3473、D3474、D3475、D3476 與 D3477 roots 一起保留在累積 shared pattern/value stripping assignment；下一輪代表性 residual `planning metric time to renew renewal recertification certification attendance validation forecast 12 個` 只回傳 `[12.0]`。

落地修改

1. 五個報告品質入口新增 renewal certification attendance recertification validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批四個 roots，並保留 D3472-D3476 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4245 deselected in 35.72s`；shared guard GREEN 為 `5 passed, 4245 deselected in 22.80s`。
2. D3477 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、D3471 root、D3472 root、D3473 root、D3474 root、D3475 root、D3476 root 與 D3477 roots controls 均為 `[]`。
3. D3476-D3477 adjacent regression 通過 `10 passed, 4240 deselected in 45.00s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_renewal_certification_attendance_recertification_validation'`：RED `5 failed, 4245 deselected in 35.72s`；GREEN `5 passed, 4245 deselected in 22.80s`。
- D3477 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- D3476-D3477 adjacent regression：`10 passed, 4240 deselected in 45.00s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、D3471 root、D3472 root、D3473 root、D3474 root、D3475 root、D3476 root 與 D3477 roots 均為 `[]`；next residual `planning metric time to renew renewal recertification certification attendance validation forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3476 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3475 後重新掃描 `renew + certification/renewal/recertification/attendance/validation` 的排列候選；前四個未收斂 residual roots 各為 lifecycle KPI 誤判組，以 certification validation recertification renewal attendance、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to renew certification validation recertification renewal attendance`、`time to renew certification validation attendance renewal recertification`、`time to renew certification validation attendance recertification renewal` 與 `time to renew renewal certification recertification validation attendance` 都是 certification renewal recertification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3472、D3473、D3474、D3475 與 D3476 roots 一起保留在累積 shared pattern/value stripping assignment；下一輪代表性 residual `planning metric time to renew renewal certification attendance recertification validation forecast 12 個` 只回傳 `[12.0]`。

落地修改

1. 五個報告品質入口新增 certification validation recertification renewal attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批四個 roots，並保留 D3472-D3475 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4240 deselected in 35.94s`；shared guard GREEN 為 `5 passed, 4240 deselected in 23.02s`。
2. D3476 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、D3471 root、D3472 root、D3473 root、D3474 root、D3475 root 與 D3476 roots controls 均為 `[]`。
3. D3475-D3476 adjacent regression 通過 `10 passed, 4235 deselected in 45.78s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_certification_validation_recertification_renewal_attendance'`：RED `5 failed, 4240 deselected in 35.94s`；GREEN `5 passed, 4240 deselected in 23.02s`。
- D3476 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- D3475-D3476 adjacent regression：`10 passed, 4235 deselected in 45.78s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、D3471 root、D3472 root、D3473 root、D3474 root、D3475 root 與 D3476 roots 均為 `[]`；next residual `planning metric time to renew renewal certification attendance recertification validation forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3475 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3474 後重新掃描 `renew + certification/renewal/recertification/attendance/validation` 的排列候選；前四個未收斂 residual roots 各為 lifecycle KPI 誤判組，以 certification attendance recertification renewal validation、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to renew certification attendance recertification renewal validation`、`time to renew certification attendance validation renewal recertification`、`time to renew certification validation renewal recertification attendance` 與 `time to renew certification validation renewal attendance recertification` 都是 certification renewal recertification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3472、D3473、D3474 與 D3475 roots 一起保留在累積 shared pattern/value stripping assignment；下一輪代表性 residual `planning metric time to renew certification validation recertification renewal attendance forecast 12 個` 只回傳 `[12.0]`。

落地修改

1. 五個報告品質入口新增 certification attendance recertification renewal validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批四個 roots，並保留 D3472-D3474 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4235 deselected in 35.68s`；shared guard GREEN 為 `5 passed, 4235 deselected in 22.67s`。
2. D3475 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、D3471 root、D3472 root、D3473 root、D3474 root 與 D3475 roots controls 均為 `[]`。
3. D3474-D3475 adjacent regression 通過 `10 passed, 4230 deselected in 44.50s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_certification_attendance_recertification_renewal_validation'`：RED `5 failed, 4235 deselected in 35.68s`；GREEN `5 passed, 4235 deselected in 22.67s`。
- D3475 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- D3474-D3475 adjacent regression：`10 passed, 4230 deselected in 44.50s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、D3471 root、D3472 root、D3473 root、D3474 root 與 D3475 roots 均為 `[]`；next residual `planning metric time to renew certification validation recertification renewal attendance forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3474 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3473 後重新掃描 `renew + certification/renewal/recertification/attendance/validation` 的排列候選；前四個未收斂 residual roots 各為完整 lifecycle KPI 誤判組，以 certification renewal validation attendance recertification、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to renew certification renewal validation attendance recertification`、`time to renew certification recertification renewal validation attendance`、`time to renew certification recertification validation renewal attendance` 與 `time to renew certification attendance renewal validation recertification` 都是 certification renewal recertification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 本批將 D3472、D3473 與 D3474 roots 一起保留在累積 shared pattern/value stripping assignment，避免局部重建遺失先前已收斂的 lifecycle roots；下一輪代表性 residual `planning metric time to renew certification attendance recertification renewal validation forecast 12 個` 只回傳 `[12.0]`。

落地修改

1. 五個報告品質入口新增 certification recertification renewal validation attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批四個 roots，並保留 D3472/D3473 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4230 deselected in 35.44s`；shared guard GREEN 為 `5 passed, 4230 deselected in 22.67s`。
2. D3474 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、D3471 root、D3472 root、D3473 root 與 D3474 roots controls 均為 `[]`。
3. D3473-D3474 adjacent regression 通過 `10 passed, 4225 deselected in 44.55s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_certification_recertification_renewal_validation_attendance'`：RED `5 failed, 4230 deselected in 35.44s`；GREEN `5 passed, 4230 deselected in 22.67s`。
- D3474 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- D3473-D3474 adjacent regression：`10 passed, 4225 deselected in 44.55s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、D3471 root、D3472 root、D3473 root 與 D3474 roots 均為 `[]`；next residual `planning metric time to renew certification attendance recertification renewal validation forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3473 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3472 後重新掃描 `renew + certification/renewal/recertification/attendance/validation` 的排列候選；前四個未收斂 residual roots 各為完整 lifecycle KPI 誤判組，以 certification renewal recertification validation attendance、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to renew certification renewal recertification validation attendance`、`time to renew certification renewal attendance recertification validation`、`time to renew certification renewal attendance validation recertification` 與 `time to renew certification renewal validation recertification attendance` 都是 certification renewal recertification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 以五入口同構矩陣驗證後，parser、calibration、credibility、structured output 各為 480 cases，detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. 相鄰回歸第一次執行發現 packed shared assignment 若只重建本批 roots，會遺失 D3472 roots；production 已改為在同一累積 assignment 保留 D3472 與 D3473 八個 roots。修正後 selected roots 均為 `0/0`，下一輪代表性 residual `planning metric time to renew certification renewal validation attendance recertification forecast 12 個` 只回傳 `[12.0]`。

落地修改

1. 五個報告品質入口新增 certification renewal recertification validation attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入本批四個 roots，並保留 D3472 roots 的累積 pattern/value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4225 deselected in 35.57s`；修正後 focused GREEN 為 `5 passed, 4225 deselected in 22.77s`。
2. D3473 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、D3471 root、D3472 root 與 D3473 roots controls 均為 `[]`。
3. D3472-D3473 adjacent regression 最終通過 `10 passed, 4220 deselected in 44.73s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_certification_renewal_recertification_validation_attendance'`：RED `5 failed, 4225 deselected in 35.57s`；final GREEN `5 passed, 4225 deselected in 22.77s`。
- D3473 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- D3472-D3473 adjacent regression：`10 passed, 4220 deselected in 44.73s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、D3471 root、D3472 root 與 D3473 roots 均為 `[]`；next residual `planning metric time to renew certification renewal validation attendance recertification forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3472 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3471 後重新掃描 `renew + certification/renewal/recertification/attendance/validation` 的排列候選；前四個選定 residual roots 各為完整 `100 leaks / 48 valid-misses`，以 certification renewal recertification validation attendance、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to renew recertification renewal attendance validation certification`、`time to renew recertification renewal validation attendance certification`、`time to renew recertification attendance renewal validation certification` 與 `time to renew recertification attendance validation renewal certification` 都是 recertification renewal attendance validation certification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 各為完整 `100 leaks / 48 valid-misses`；五入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. post-fix selected roots 均為 `0/0`；下一輪代表性 residual 為 `planning metric time to renew certification renewal recertification validation attendance forecast 12 個`，只回傳 `[12.0]`，因此不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 renew recertification renewal attendance validation certification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 roots 及 value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4220 deselected in 32.25s`；shared guard GREEN 為 `5 passed, 4220 deselected in 22.89s`，沒有新增 consumer-specific cleanup。
2. D3472 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、D3471 guarded root 與 D3470 guarded root controls 均為 `[]`。
3. D3471-D3472 adjacent regression 通過 `10 passed, 4215 deselected in 44.92s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_recertification_renewal_attendance_validation_certification'`：RED `5 failed, 4220 deselected in 32.25s`；GREEN `5 passed, 4220 deselected in 22.89s`。
- D3472 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- D3471-D3472 adjacent regression：`10 passed, 4215 deselected in 44.92s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、D3471 guarded root 與 D3470 guarded root 均為 `[]`；next residual `planning metric time to renew certification renewal recertification validation attendance forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3471 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3470 後重新掃描 `renew + certification/renewal/recertification/attendance/validation` 的排列候選；前四個選定 residual roots 各為完整 `100 leaks / 48 valid-misses`，以 recertification renewal attendance validation certification、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to renew certification renewal recertification attendance validation`、`time to renew certification attendance renewal recertification validation`、`time to renew certification recertification renewal attendance validation` 與 `time to renew certification recertification attendance renewal validation` 都是 renew certification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 各為完整 `100 leaks / 48 valid-misses`；五入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. post-fix 八組重掃顯示第 1-4 組各為 `0/0`；第 5-8 組各為完整 residual `100/48`，因此下一輪先處理 `time to renew recertification renewal attendance validation certification`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 renew certification renewal recertification attendance validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 roots 及 value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4215 deselected in 36.46s`；shared guard GREEN 為 `5 passed, 4215 deselected in 23.00s`，沒有新增 consumer-specific cleanup。
2. D3471 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded renew certification renewal recertification attendance validation 與 already-guarded renew validation attendance renewal certification recertification controls 均為 `[]`。
3. D3470-D3471 adjacent regression 通過 `10 passed, 4210 deselected in 45.28s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_certification_renewal_recertification_attendance_validation'`：RED `5 failed, 4215 deselected in 36.46s`；GREEN `5 passed, 4215 deselected in 23.00s`。
- D3471 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- D3470-D3471 adjacent regression：`10 passed, 4210 deselected in 45.28s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to renew certification renewal recertification attendance validation` 與 already-guarded `time to renew validation attendance renewal certification recertification` 均為 `[]`；next residual `planning metric time to renew recertification renewal attendance validation certification forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3470 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3469 後重新掃描 `renew + certification/renewal/recertification/attendance/validation` 的排列候選；前四個選定 residual roots 各為完整 `100 leaks / 48 valid-misses`，以 certification renewal recertification attendance validation、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to renew validation attendance renewal certification recertification`、`time to renew attendance renewal certification recertification validation`、`time to renew renewal attendance certification recertification validation` 與 `time to renew renewal certification recertification attendance validation` 都是 renew validation attendance certification recertification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 各為完整 `100 leaks / 48 valid-misses`；五入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. post-fix 八組重掃顯示第 1-4 組各為 `0/0`；第 5-8 組各為完整 residual `100/48`，因此下一輪先處理 `time to renew certification renewal recertification attendance validation`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 renew validation attendance renewal certification recertification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 roots 及 value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4210 deselected in 47.97s`；shared guard GREEN 為 `5 passed, 4210 deselected in 23.36s`，沒有新增 consumer-specific cleanup。
2. D3470 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded renew validation attendance renewal certification recertification 與 already-guarded renew recertification validation attendance renewal certification controls 均為 `[]`。
3. D3469-D3470 adjacent regression 通過 `10 passed, 4205 deselected in 45.46s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_validation_attendance_renewal_certification_recertification'`：RED `5 failed, 4210 deselected in 47.97s`；GREEN `5 passed, 4210 deselected in 23.36s`。
- D3470 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- D3469-D3470 adjacent regression：`10 passed, 4205 deselected in 45.46s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to renew validation attendance renewal certification recertification` 與 already-guarded `time to renew recertification validation attendance renewal certification` 均為 `[]`；next residual `planning metric time to renew certification renewal recertification attendance validation forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3469 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3468 後重新掃描 `renew + certification/renewal/recertification/attendance/validation` 的排列候選；前四個選定 residual roots 各為完整 `100 leaks / 48 valid-misses`，以 validation attendance renewal certification recertification、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to renew recertification validation attendance renewal certification`、`time to renew attendance certification renewal recertification validation`、`time to renew validation renewal attendance certification recertification` 與 `time to renew validation attendance certification renewal recertification` 都是 renew lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 各為完整 `100 leaks / 48 valid-misses`；五入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. post-fix 八組重掃顯示第 1-4 組各為 `0/0`；第 5-8 組各為完整 residual `100/48`，因此下一輪先處理 `time to renew validation attendance renewal certification recertification`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 renew recertification validation attendance renewal certification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 roots 及 value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4205 deselected in 37.28s`；shared guard GREEN 為 `5 passed, 4205 deselected in 23.44s`，沒有新增 consumer-specific cleanup。
2. D3469 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded renew recertification validation attendance renewal certification 與 already-guarded issue validation renewal attendance certification recertification controls 均為 `[]`。
3. D3468-D3469 adjacent regression 通過 `10 passed, 4200 deselected in 45.27s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renew_recertification_validation_attendance_renewal_certification'`：RED `5 failed, 4205 deselected in 37.28s`；GREEN `5 passed, 4205 deselected in 23.44s`。
- D3469 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- D3468-D3469 adjacent regression：`10 passed, 4200 deselected in 45.27s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to renew recertification validation attendance renewal certification` 與 already-guarded `time to issue validation renewal attendance certification recertification` 均為 `[]`；next residual `planning metric time to renew validation attendance renewal certification recertification forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3468 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3467 後重新掃描 `issue + certification/renewal/recertification/attendance/validation` 的排列候選；representative candidate scan 為 84 組 residual、36 組已有 guard，選擇前四個完整 residual roots，以 validation renewal attendance certification recertification、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue validation renewal attendance certification recertification`、`time to issue validation attendance certification renewal recertification`、`time to issue validation attendance renewal certification recertification` 與 `time to renew recertification validation renewal attendance certification` 都是 validation renewal attendance certification recertification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 各為完整 `100 leaks / 48 valid-misses`；五入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. post-fix 八組重掃顯示第 1-4 組各為 `0/0`；第 5-8 組各為完整 residual `100/48`，因此下一輪先處理 `time to renew recertification validation attendance renewal certification`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 validation renewal attendance certification recertification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 roots 及 value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4200 deselected in 32.11s`；shared guard GREEN 為 `5 passed, 4200 deselected in 23.03s`，沒有新增 consumer-specific cleanup。
2. D3468 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded issue validation renewal attendance certification recertification 與 already-guarded issue recertification validation renewal attendance certification controls 均為 `[]`。
3. D3467-D3468 adjacent regression 通過 `10 passed, 4195 deselected in 45.18s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'issue_validation_renewal_attendance_certification_recertification'`：RED `5 failed, 4200 deselected in 32.11s`；GREEN `5 passed, 4200 deselected in 23.03s`。
- D3468 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- D3467-D3468 adjacent regression：`10 passed, 4195 deselected in 45.18s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to issue validation renewal attendance certification recertification` 與 already-guarded `time to issue recertification validation renewal attendance certification` 均為 `[]`；next residual `planning metric time to renew recertification validation attendance renewal certification forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3467 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3466 後重新掃描 `issue + certification/renewal/recertification/attendance/validation` 的 120 組詞序；representative fresh scan 為 42 組 residual、78 組已有 guard，選擇前四個 residual roots，以 validation renewal attendance certification recertification、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue recertification validation renewal attendance certification`、`time to issue recertification validation attendance certification renewal`、`time to issue recertification validation attendance renewal certification` 與 `time to issue attendance certification renewal recertification validation` 都是 recertification validation renewal attendance certification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 第一、三、四個選定 roots 各為完整 `100 leaks / 48 valid-misses`，第二個 root 為部分命中 `80 leaks / 48 valid-misses`；五入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. post-fix 八組重掃顯示第 1-4 組各為 `0/0`；第 5-7 組各為完整 residual `100/48`，第 8 組為 `0/0`，因此下一輪先處理 `time to issue validation renewal attendance certification recertification`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 recertification validation renewal attendance certification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 roots 及 value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4195 deselected in 37.23s`；shared guard GREEN 為 `5 passed, 4195 deselected in 28.99s`，沒有新增 consumer-specific cleanup。
2. D3467 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded issue recertification validation renewal attendance certification 與 already-guarded issue recertification attendance validation certification renewal controls 均為 `[]`。
3. D3466-D3467 adjacent regression 通過 `10 passed, 4190 deselected in 44.99s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'recertification_validation_renewal_attendance_certification'`：RED `5 failed, 4195 deselected in 37.23s`；GREEN `5 passed, 4195 deselected in 28.99s`。
- D3467 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- D3466-D3467 adjacent regression：`10 passed, 4190 deselected in 44.99s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to issue recertification validation renewal attendance certification` 與 already-guarded `time to issue recertification attendance validation certification renewal` 均為 `[]`；next residual `planning metric time to issue validation renewal attendance certification recertification forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3466 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3465 後重新掃描 `issue + certification/renewal/recertification/attendance/validation` 的 120 組詞序；representative fresh scan 為 42 組 residual、78 組已有 guard，選擇前四個 residual roots，以 recertification validation renewal attendance certification、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue recertification attendance validation certification renewal`、`time to issue recertification attendance validation renewal certification`、`time to issue recertification validation certification renewal attendance` 與 `time to issue recertification validation renewal certification attendance` 都是 recertification attendance validation certification renewal lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 第一個選定 root 為部分命中 `80 leaks / 48 valid-misses`，其餘三個選定 roots 各為完整 `100 leaks / 48 valid-misses`；五入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. post-fix 八組重掃顯示第 1-4 組各為 `0/0`；第 5 組為完整 residual `100/48`，第 6 組為部分 residual `80/48`，第 7-8 組各為完整 residual `100/48`，因此下一輪先處理 `time to issue recertification validation renewal attendance certification`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 recertification attendance validation certification renewal lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 roots 及 value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4190 deselected in 46.84s`；shared guard GREEN 為 `5 passed, 4190 deselected in 22.82s`，沒有新增 consumer-specific cleanup。
2. D3466 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded issue recertification attendance validation certification renewal 與 already-guarded issue recertification renewal attendance validation certification controls 均為 `[]`。
3. D3465-D3466 adjacent regression 通過 `10 passed, 4185 deselected in 45.20s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'recertification_attendance_validation_certification_renewal'`：RED `5 failed, 4190 deselected in 46.84s`；GREEN `5 passed, 4190 deselected in 22.82s`。
- D3466 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- D3465-D3466 adjacent regression：`10 passed, 4185 deselected in 45.20s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to issue recertification attendance validation certification renewal` 與 already-guarded `time to issue recertification renewal attendance validation certification` 均為 `[]`；next residual `planning metric time to issue recertification validation renewal attendance certification forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3465 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3464 後重新掃描 `issue + certification/renewal/recertification/attendance/validation` 的 120 組詞序；representative fresh scan 為 46 組 residual、74 組已有 guard，選擇前四個完整 `100 leaks / 48 valid-misses` roots，以 recertification renewal attendance validation certification、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue recertification renewal attendance validation certification`、`time to issue recertification renewal validation certification attendance`、`time to issue recertification renewal validation attendance certification` 與 `time to issue recertification attendance renewal certification validation` 都是 recertification renewal attendance validation certification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 各為 `100 leaks / 48 valid-misses`；五入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. post-fix 八組重掃顯示第 1-4 組各為 `0/0`；第 5 組為部分 residual `80/48`，第 6-8 組各為完整 residual `100/48`，因此下一輪先處理 `time to issue recertification attendance validation certification renewal`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 recertification renewal attendance validation certification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 roots 及 value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4185 deselected in 35.29s`；shared guard GREEN 為 `5 passed, 4185 deselected in 22.80s`，沒有新增 consumer-specific cleanup。
2. D3465 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded issue recertification renewal attendance validation certification 與 already-guarded issue recertification certification attendance validation renewal controls 均為 `[]`。
3. D3464-D3465 adjacent regression 通過 `10 passed, 4180 deselected in 45.15s`；下一批 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'recertification_renewal_attendance_validation_certification'`：RED `5 failed, 4185 deselected in 35.29s`；GREEN `5 passed, 4185 deselected in 22.80s`。
- D3465 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- D3464-D3465 adjacent regression：`10 passed, 4180 deselected in 45.15s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to issue recertification renewal attendance validation certification` 與 already-guarded `time to issue recertification certification attendance validation renewal` 均為 `[]`；next residual `planning metric time to issue recertification attendance validation certification renewal forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3464 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3463 後重新掃描 `issue + certification/renewal/recertification/attendance/validation` 的 120 組詞序；representative fresh scan 為 50 組 residual、70 組已有 guard，選擇前四個完整 `100 leaks / 48 valid-misses` roots，以 recertification certification attendance validation renewal、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue recertification certification attendance validation renewal`、`time to issue recertification certification validation renewal attendance`、`time to issue recertification certification validation attendance renewal` 與 `time to issue recertification renewal certification attendance validation` 都是 recertification certification attendance validation renewal lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 各為 `100 leaks / 48 valid-misses`；五入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. post-fix 八組重掃顯示第 1-4 組各為 `0/0`；第 5-8 組各為完整 residual `100/48`，因此下一輪先處理 `time to issue recertification renewal attendance validation certification`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 recertification certification attendance validation renewal lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 roots 及 value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4180 deselected in 36.31s`；shared guard GREEN 為 `5 passed, 4180 deselected in 23.26s`，沒有新增 consumer-specific cleanup。
2. D3464 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded issue recertification certification attendance validation renewal 與 already-guarded issue renewal validation recertification attendance certification controls 均為 `[]`。
3. D3463-D3464 adjacent regression 通過 `10 passed, 4175 deselected in 44.86s`；下一批四個完整 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'recertification_certification_attendance_validation_renewal'`：RED `5 failed, 4180 deselected in 36.31s`；GREEN `5 passed, 4180 deselected in 23.26s`。
- D3464 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- D3463-D3464 adjacent regression：`10 passed, 4175 deselected in 44.86s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to issue recertification certification attendance validation renewal` 與 already-guarded `time to issue renewal validation recertification attendance certification` 均為 `[]`；next residual `planning metric time to issue recertification renewal attendance validation certification forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3463 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3462 後重新掃描 `issue + certification/renewal/recertification/attendance/validation` 的 120 組詞序；representative fresh scan 為 54 組 residual、66 組已有 guard，選擇前四個完整 `100 leaks / 48 valid-misses` roots，以 recertification certification attendance validation renewal、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue renewal validation recertification attendance certification`、`time to issue renewal validation attendance certification recertification`、`time to issue renewal validation attendance recertification certification` 與 `time to issue recertification certification renewal validation attendance` 都是 renewal validation recertification attendance certification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 各為 `100 leaks / 48 valid-misses`；五入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. post-fix 八組重掃顯示第 1-4 組各為 `0/0`；第 5-8 組各為完整 residual `100/48`，因此下一輪先處理 `time to issue recertification certification attendance validation renewal`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 renewal validation recertification attendance certification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 roots 及 value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4175 deselected in 35.85s`；shared guard GREEN 為 `5 passed, 4175 deselected in 22.89s`，沒有新增 consumer-specific cleanup。
2. D3463 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded issue renewal validation recertification attendance certification 與 already-guarded issue certification attendance validation recertification renewal controls 均為 `[]`。
3. D3462-D3463 adjacent regression 通過 `10 passed, 4170 deselected in 44.43s`；下一批四個完整 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renewal_validation_recertification_attendance_certification'`：RED `5 failed, 4175 deselected in 35.85s`；GREEN `5 passed, 4175 deselected in 22.89s`。
- D3463 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- D3462-D3463 adjacent regression：`10 passed, 4170 deselected in 44.43s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to issue renewal validation recertification attendance certification` 與 already-guarded `time to issue certification attendance validation recertification renewal` 均為 `[]`；next residual `planning metric time to issue recertification certification attendance validation renewal forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3462 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3461 後重新掃描 `issue + certification/renewal/recertification/attendance/validation` 的 120 組詞序；representative fresh scan 為 58 組 residual、62 組已有 guard，選擇前四個 residual roots，其中前兩組是 `80 leaks / 48 valid-misses` 的部分命中，後兩組是 `100 leaks / 48 valid-misses` 的完整缺口。

核心判斷

1. `time to issue certification attendance validation recertification renewal`、`time to issue certification validation attendance recertification renewal`、`time to issue renewal validation certification attendance recertification` 與 `time to issue renewal validation recertification certification attendance` 都是 certification attendance validation recertification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 本輪同時處理部分命中與完整缺口，四個 roots 合計覆蓋四入口 480 cases、detector 400 cases；final matrix 所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. post-fix 八組重掃顯示第 1-4 組各為 `0/0`；第 5-8 組各為完整 residual `100/48`，因此下一輪先處理 `time to issue renewal validation recertification attendance certification`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 certification attendance validation recertification renewal lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 roots 及 value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4170 deselected in 36.06s`；shared guard GREEN 為 `5 passed, 4170 deselected in 22.71s`，沒有新增 consumer-specific cleanup。
2. D3462 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded issue certification attendance validation recertification renewal 與 already-guarded issue renewal attendance recertification validation certification controls 均為 `[]`。
3. D3461-D3462 adjacent regression 通過 `10 passed, 4165 deselected in 45.12s`；下一批四個完整 residual 保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'certification_attendance_validation_recertification_renewal'`：RED `5 failed, 4170 deselected in 36.06s`；GREEN `5 passed, 4170 deselected in 22.71s`。
- D3462 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- D3461-D3462 adjacent regression：`10 passed, 4165 deselected in 45.12s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to issue certification attendance validation recertification renewal` 與 already-guarded `time to issue renewal attendance recertification validation certification` 均為 `[]`；next residual `planning metric time to issue renewal validation recertification attendance certification forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3461 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3460 後重新掃描 `issue + certification/renewal/recertification/attendance/validation` 的 120 組詞序；實際觀察到 62 組仍有 residual、58 組已有 guard，選擇四個完整 `100 leaks / 48 valid-misses` roots，以 certification attendance validation recertification renewal、course control、financial time-to 與 explicit target price 作為比較組，部分命中 roots 不在本輪擴大。

核心判斷

1. `time to issue renewal attendance recertification validation certification`、`time to issue renewal attendance validation certification recertification`、`time to issue renewal attendance validation recertification certification` 與 `time to issue renewal validation certification recertification attendance` 是 renewal attendance certification validation lifecycle KPI；其數值不應進入股票 target-price candidates。
2. 四個選定 roots 各為 `100 leaks / 48 valid-misses`；五入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. post-fix 八組重掃顯示第 1-4 組各為 `0/0`；第 5-6 組仍為部分 residual `80/48`，第 7-8 組仍為完整 residual `100/48`，因此下一輪先處理 `time to issue certification attendance validation recertification renewal`，不把部分命中或 financial `time to price` 語意外推。

落地修改

1. 五個報告品質入口新增 renewal attendance certification validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個完整 residual roots 及 value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4165 deselected in 35.51s`；shared guard GREEN 為 `5 passed, 4165 deselected in 22.69s`，沒有新增 consumer-specific cleanup。
2. D3461 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded issue renewal attendance recertification validation certification 與 already-guarded issue renewal certification validation attendance recertification controls 均為 `[]`。
3. D3460-D3461 adjacent regression 通過 `10 passed, 4160 deselected in 44.71s`；保留部分命中與完整 residual 作為下一輪比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renewal_attendance_recertification_validation_certification'`：RED `5 failed, 4165 deselected in 35.51s`；GREEN `5 passed, 4165 deselected in 22.69s`。
- D3461 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- D3460-D3461 adjacent regression：`10 passed, 4160 deselected in 44.71s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to issue renewal attendance recertification validation certification` 與 already-guarded `time to issue renewal certification validation attendance recertification` 均為 `[]`；next residual `planning metric time to issue certification attendance validation recertification renewal forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3460 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3459 後重新掃描 `issue + certification/renewal/recertification/attendance/validation` 的 120 組詞序；56 組仍有 parser residual、64 組已有 guard，選擇前四個 residual roots，以 renewal attendance recertification validation certification、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue renewal certification validation attendance recertification`、`time to issue renewal recertification certification validation attendance`、`time to issue renewal recertification validation certification attendance` 與 `time to issue renewal recertification validation attendance certification` 是 renewal certification validation attendance lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh permutation scan 覆蓋全部 120 組五-token 詞序；四個選定 roots 各為 `100 leaks / 48 valid-misses`，四入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. post-fix 重掃顯示第 1-4 組各為 `0 leaks / 0 valid-misses`；第 5-8 組仍是 parser residual `100/48`，因此下一輪先處理 `time to issue renewal attendance recertification validation certification`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 renewal certification validation attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 roots 及 value stripping guard，由五個既有 consumer 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 先以三個既有入口取得 RED：`3 failed, 2480 deselected in 17.69s`；補齊 structured output 與 explicit detector 對稱 coverage 後，五入口 GREEN 為 `5 passed, 4160 deselected in 24.14s`，沒有新增 consumer-specific cleanup。
2. D3460 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded issue renewal certification validation attendance recertification 與 already-guarded issue certification attendance validation renewal recertification controls 均為 `[]`。
3. D3459-D3460 adjacent regression 通過 `15 passed, 4150 deselected in 76.96s`；post-fix 八組重掃中的第 5-8 組仍保留為比較組，避免一次擴大 guard 範圍。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'renewal_certification_validation_attendance_recertification or renewal_recertification_certification_validation_attendance or renewal_recertification_validation_certification_attendance or renewal_recertification_validation_attendance_certification'`：`5 passed, 4160 deselected in 24.14s`。
- D3460 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- D3459-D3460 adjacent regression：`15 passed, 4150 deselected in 76.96s`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to issue renewal certification validation attendance recertification` 與 already-guarded `time to issue certification attendance validation renewal recertification` 均為 `[]`；next residual `planning metric time to issue renewal attendance recertification validation certification forecast 12 個` 為 `[12.0]`。

### 完成後維護 / D3459 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3458 後重新掃描 `issue + certification/renewal/recertification/attendance/validation` 的 120 組詞序；60 組仍有 parser residual、60 組已有 guard，選擇前四個 residual roots，以 issue renewal certification validation attendance recertification、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue certification validation attendance renewal recertification`、`time to issue renewal certification recertification validation attendance`、`time to issue renewal certification attendance validation recertification` 與 `time to issue renewal certification validation recertification attendance` 是 certification validation/renewal lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh permutation scan 覆蓋全部 120 組五-token 詞序；四個選定 roots 各為 `100 leaks / 48 valid-misses`，四入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. post-fix 重掃顯示第 1-4 組各為 `0 leaks / 0 valid-misses`；第 5-8 組仍是 parser residual `100/48`，因此下一輪先處理 `time to issue renewal certification validation attendance recertification`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 certification validation attendance renewal lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 將四個 roots 合併進共享 `QUALITY_SERVICE_TIME_TO_METRIC_PATTERN` 與 value stripping guard，並由 `backend/report_target_price_detection.py` 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4155 deselected in 35.04s`；shared guard GREEN 為 `5 passed, 4155 deselected in 22.61s`，沒有新增 consumer-specific cleanup。
2. D3459 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded issue certification validation attendance renewal recertification 與 already-guarded issue certification attendance validation renewal recertification controls 均為 `[]`。
3. D3458-D3459 adjacent regression 通過 `10 passed, 4150 deselected in 44.90s`。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_issue_certification_validation_attendance_renewal_recertification_lifecycle'`：RED `5 failed, 4155 deselected in 35.04s`；GREEN `5 passed, 4155 deselected in 22.61s`。
- D3459 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to issue certification validation attendance renewal recertification` 與 already-guarded `time to issue certification attendance validation renewal recertification` 均為 `[]`；next residual `planning metric time to issue renewal certification validation attendance recertification forecast 12 個` 為 `[12.0]`。
- D3458-D3459 adjacent regression：`10 passed, 4150 deselected in 44.90s`。

### 完成後維護 / D3458 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3457 後重新掃描 `issue + certification/renewal/recertification/attendance/validation` 的 120 組詞序；64 組仍有 parser residual、56 組已有 guard，選擇前四個 residual roots，以 issue certification validation attendance renewal recertification、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue certification attendance validation renewal recertification`、`time to issue certification validation renewal attendance recertification`、`time to issue certification validation recertification renewal attendance` 與 `time to issue certification validation recertification attendance renewal` 是 certification attendance validation renewal lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh permutation scan 覆蓋全部 120 組五-token 詞序；四個選定 roots 各為 `100 leaks / 48 valid-misses`，四入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. post-fix 重掃顯示第 1-4 組各為 `0 leaks / 0 valid-misses`；第 5-8 組仍是 parser residual `100/48`，因此下一輪先處理 `time to issue certification validation attendance renewal recertification`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 certification attendance validation renewal lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 將四個 roots 合併進共享 `QUALITY_SERVICE_TIME_TO_METRIC_PATTERN` 與 value stripping guard，並由 `backend/report_target_price_detection.py` 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4150 deselected in 31.81s`；shared guard GREEN 為 `5 passed, 4150 deselected in 22.57s`，沒有新增 consumer-specific cleanup。
2. D3458 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded issue certification attendance validation renewal recertification 與 already-guarded issue certification recertification renewal attendance validation controls 均為 `[]`。
3. D3457-D3458 adjacent regression 通過 `10 passed, 4145 deselected in 44.84s`。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_issue_certification_attendance_validation_renewal_recertification_lifecycle'`：RED `5 failed, 4150 deselected in 31.81s`；GREEN `5 passed, 4150 deselected in 22.57s`。
- D3458 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to issue certification attendance validation renewal recertification` 與 already-guarded `time to issue certification recertification renewal attendance validation` 均為 `[]`；next residual `planning metric time to issue certification validation attendance renewal recertification forecast 12 個` 為 `[12.0]`。
- D3457-D3458 adjacent regression：`10 passed, 4145 deselected in 44.84s`。

### 完成後維護 / D3457 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3456 後重新掃描 `issue + certification/renewal/recertification/attendance/validation` 的 120 組詞序；68 組仍有 parser residual、52 組已有 guard，選擇前四個 residual roots，以 issue certification attendance validation renewal recertification、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue certification recertification renewal attendance validation`、`time to issue certification recertification renewal validation attendance`、`time to issue certification recertification validation renewal attendance` 與 `time to issue certification recertification validation attendance renewal` 是 certification recertification renewal lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh permutation scan 覆蓋全部 120 組五-token 詞序；四個選定 roots 各為 `100 leaks / 48 valid-misses`，四入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. post-fix 重掃顯示第 1-4 組各為 `0 leaks / 0 valid-misses`；第 5-8 組仍是 parser residual `100/48`，因此下一輪先處理 `time to issue certification attendance validation renewal recertification`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 certification recertification renewal attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 將四個 roots 合併進共享 `QUALITY_SERVICE_TIME_TO_METRIC_PATTERN` 與 value stripping guard，並由 `backend/report_target_price_detection.py` 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4145 deselected in 37.15s`；shared guard GREEN 為 `5 passed, 4145 deselected in 25.96s`，沒有新增 consumer-specific cleanup。
2. D3457 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded issue certification recertification renewal attendance validation 與 already-guarded issue certification renewal recertification attendance validation controls 均為 `[]`。
3. D3456-D3457 adjacent regression 通過 `10 passed, 4140 deselected in 44.48s`。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_issue_certification_recertification_renewal_attendance_validation_lifecycle'`：RED `5 failed, 4145 deselected in 37.15s`；GREEN `5 passed, 4145 deselected in 25.96s`。
- D3457 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to issue certification recertification renewal attendance validation` 與 already-guarded `time to issue certification renewal recertification attendance validation` 均為 `[]`；next residual `planning metric time to issue certification attendance validation renewal recertification forecast 12 個` 為 `[12.0]`。
- D3456-D3457 adjacent regression：`10 passed, 4140 deselected in 44.48s`。

### 完成後維護 / D3456 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3455 後重新掃描 `issue + certification/renewal/recertification/attendance/validation` 的 120 組詞序；72 組仍有 parser residual、48 組已有 guard，選擇前四個 residual roots，以 issue certification recertification renewal attendance validation、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue certification renewal recertification attendance validation`、`time to issue certification renewal recertification validation attendance`、`time to issue certification renewal validation recertification attendance` 與 `time to issue certification renewal validation attendance recertification` 是 certification renewal recertification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh permutation scan 覆蓋全部 120 組五-token 詞序；四個選定 roots 各為 `100 leaks / 48 valid-misses`，四入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`。
3. post-fix 重掃顯示第 1-4 組各為 `0 leaks / 0 valid-misses`；第 5-8 組仍是 parser residual `100/48`，因此下一輪先處理 `time to issue certification recertification renewal attendance validation`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 certification renewal recertification attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 將四個 roots 合併進共享 `QUALITY_SERVICE_TIME_TO_METRIC_PATTERN` 與 value stripping guard，並由 `backend/report_target_price_detection.py` 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4140 deselected in 37.15s`；shared guard GREEN 為 `5 passed, 4140 deselected in 31.14s`，沒有新增 consumer-specific cleanup。
2. D3456 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded issue certification renewal recertification attendance validation 與 already-guarded issue certification attendance renewal validation recertification controls 均為 `[]`。
3. D3455-D3456 adjacent regression 通過 `10 passed, 4135 deselected in 44.92s`。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_issue_certification_renewal_recertification_attendance_validation_lifecycle'`：RED `5 failed, 4140 deselected in 37.15s`；GREEN `5 passed, 4140 deselected in 31.14s`。
- D3456 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to issue certification renewal recertification attendance validation` 與 already-guarded `time to issue certification attendance renewal validation recertification` 均為 `[]`；next residual `planning metric time to issue certification recertification renewal attendance validation forecast 12 個` 為 `[12.0]`。
- D3455-D3456 adjacent regression：`10 passed, 4135 deselected in 44.92s`。

### 完成後維護 / D3455 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3454 後重新掃描 issue certification attendance renewal validation recertification、issue certification renewal attendance validation recertification、issue attendance renewal certification recertification validation、issue recertification attendance certification renewal validation 與其他 variants；選擇前四個仍有缺口的 roots，以 issue certification attendance recertification renewal validation、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue certification attendance renewal validation recertification`、`time to issue certification renewal attendance validation recertification`、`time to issue attendance renewal certification recertification validation` 與 `time to issue recertification attendance certification renewal validation` 是 issue/certification attendance recertification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；四個選定 roots 各為 `100 leaks / 48 valid-misses`，四入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示第 1-5 組各為 `0 leaks / 0 valid-misses`；第 6-8 組仍是 parser residual `100/48`，因此下一輪先處理 `time to issue certification renewal recertification attendance validation`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 certification attendance renewal recertification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 將四個 roots 合併進共享 `QUALITY_SERVICE_TIME_TO_METRIC_PATTERN` 與 value stripping guard，並由 `backend/report_target_price_detection.py` 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4135 deselected in 32.47s`；shared guard GREEN 為 `5 passed, 4135 deselected in 23.18s`，沒有新增 consumer-specific cleanup。
2. D3455 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded issue certification attendance renewal validation recertification 與 already-guarded issue certification attendance recertification renewal validation controls 均為 `[]`。
3. D3454-D3455 adjacent regression 通過 `10 passed, 4130 deselected in 44.65s`。

驗證方式

- `$(./scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_issue_certification_attendance_renewal_validation_recertification_lifecycle'`：RED `5 failed, 4135 deselected in 32.47s`；GREEN `5 passed, 4135 deselected in 23.18s`。
- D3455 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to issue certification attendance renewal validation recertification` 與 already-guarded `time to issue certification attendance recertification renewal validation` 均為 `[]`；next residual `planning metric time to issue certification renewal recertification attendance validation forecast 12 個` 為 `[12.0]`。
- D3454-D3455 adjacent regression：`10 passed, 4130 deselected in 44.65s`。

### 完成後維護 / D3454 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3453 後重新掃描 issue certification attendance recertification renewal validation、issue certification attendance renewal recertification validation、issue recertification certification attendance renewal validation、issue attendance certification recertification renewal validation 與其他 variants；選擇前四個仍有缺口的 roots，以 issue certification recertification attendance renewal validation、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue certification attendance recertification renewal validation`、`time to issue certification attendance renewal recertification validation`、`time to issue recertification certification attendance renewal validation` 與 `time to issue attendance certification recertification renewal validation` 是 issue/certification attendance recertification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；四個選定 roots 各為 `100 leaks / 48 valid-misses`，四入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示第 1-5 組各為 `0 leaks / 0 valid-misses`；第 6-8 組仍是 parser residual `100/48`，因此下一輪先處理 `time to issue certification attendance renewal validation recertification`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 certification attendance recertification renewal lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 將四個 roots 合併進共享 `QUALITY_SERVICE_TIME_TO_METRIC_PATTERN` 與 value stripping guard，並由 `backend/report_target_price_detection.py` 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4130 deselected in 35.56s`；shared guard GREEN 為 `5 passed, 4130 deselected in 22.85s`，沒有新增 consumer-specific cleanup。
2. D3454 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded issue certification attendance recertification renewal validation 與 already-guarded issue renewal recertification attendance certification validation controls 均為 `[]`。
3. D3453-D3454 adjacent regression 通過 `10 passed, 4125 deselected in 44.44s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_issue_certification_attendance_recertification_renewal_validation_lifecycle'`：RED `5 failed, 4130 deselected in 35.56s`；GREEN `5 passed, 4130 deselected in 22.85s`。
- D3454 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to issue certification attendance recertification renewal validation` 與 already-guarded `time to issue renewal recertification attendance certification validation` 均為 `[]`；next residual `planning metric time to issue certification attendance renewal validation recertification forecast 12 個` 為 `[12.0]`。
- D3453-D3454 adjacent regression：`10 passed, 4125 deselected in 44.44s`。

### 完成後維護 / D3453 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3452 後重新掃描 issue renewal recertification attendance certification validation、issue certification recertification attendance renewal validation、issue attendance recertification renewal certification validation、issue renewal recertification attendance validation certification 與其他 variants；選擇前四個仍有缺口的 roots，以 issue renewal certification attendance recertification validation、issue renewal attendance recertification certification validation、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue renewal recertification attendance certification validation`、`time to issue certification recertification attendance renewal validation`、`time to issue attendance recertification renewal certification validation` 與 `time to issue renewal recertification attendance validation certification` 是 issue/attendance/certification recertification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；四個選定 roots 各為 `100 leaks / 48 valid-misses`，四入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示第 1-7 組各為 `0 leaks / 0 valid-misses`；第 8 組仍是 parser residual `100/48`，因此下一輪先處理 `time to issue certification attendance recertification renewal validation`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 issue recertification attendance renewal lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 將四個 roots 合併進共享 `QUALITY_SERVICE_TIME_TO_METRIC_PATTERN` 與 value stripping guard，並由 `backend/report_target_price_detection.py` 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4125 deselected in 35.22s`；shared guard GREEN 為 `5 passed, 4125 deselected in 22.56s`，沒有新增 consumer-specific cleanup。
2. D3453 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded issue renewal recertification attendance certification validation 與 already-guarded issue renewal attendance recertification certification validation controls 均為 `[]`。
3. D3452-D3453 adjacent regression 通過 `10 passed, 4120 deselected in 44.34s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_issue_renewal_recertification_attendance_certification_validation_lifecycle'`：RED `5 failed, 4125 deselected in 35.22s`；GREEN `5 passed, 4125 deselected in 22.56s`。
- D3453 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to issue renewal recertification attendance certification validation` 與 already-guarded `time to issue renewal attendance recertification certification validation` 均為 `[]`；next residual `planning metric time to issue certification attendance recertification renewal validation forecast 12 個` 為 `[12.0]`。
- D3452-D3453 adjacent regression：`10 passed, 4120 deselected in 44.34s`。

### 完成後維護 / D3452 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3451 後重新掃描 issue renewal attendance recertification certification validation、issue attendance renewal recertification certification validation、issue certification renewal attendance recertification validation、issue renewal attendance certification validation recertification 與其他 variants；選擇前四個仍有缺口的 roots，以 issue renewal certification attendance recertification validation、issue renewal attendance certification recertification validation、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue renewal attendance recertification certification validation`、`time to issue attendance renewal recertification certification validation`、`time to issue certification renewal attendance recertification validation` 與 `time to issue renewal attendance certification validation recertification` 是 issue/attendance/certification recertification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；四個選定 roots 各為 `100 leaks / 48 valid-misses`，四入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示第 1-6 組各為 `0 leaks / 0 valid-misses`；第 7、8 組仍是 parser residual `100/48`，因此下一輪先處理 `time to issue renewal recertification attendance certification validation`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 issue attendance recertification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 將四個 roots 合併進共享 `QUALITY_SERVICE_TIME_TO_METRIC_PATTERN` 與 value stripping guard，並由 `backend/report_target_price_detection.py` 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4120 deselected in 36.17s`；shared guard GREEN 為 `5 passed, 4120 deselected in 24.37s`，沒有新增 consumer-specific cleanup。
2. D3452 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded issue renewal attendance recertification certification validation 與 already-guarded attend renewal attendance recertification certification validation controls 均為 `[]`。
3. D3451-D3452 adjacent regression 通過 `10 passed, 4115 deselected in 44.87s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_issue_renewal_attendance_recertification_certification_validation_lifecycle'`：RED `5 failed, 4120 deselected in 36.17s`；GREEN `5 passed, 4120 deselected in 24.37s`。
- D3452 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to issue renewal attendance recertification certification validation` 與 already-guarded `time to attend renewal attendance recertification certification validation` 均為 `[]`；next residual `planning metric time to issue renewal recertification attendance certification validation forecast 12 個` 為 `[12.0]`。
- D3451-D3452 adjacent regression：`10 passed, 4115 deselected in 44.87s`。

### 完成後維護 / D3451 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3450 後重新掃描 attend renewal attendance recertification certification validation、attend certification renewal attendance recertification validation、attend attendance renewal certification recertification validation、attend renewal recertification attendance certification validation 與其他 variants；選擇前四個仍有缺口的 roots，以 attend renewal certification recertification attendance validation、issue/verify/schedule renewal attendance variants、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to attend renewal attendance recertification certification validation`、`time to attend certification renewal attendance recertification validation`、`time to attend attendance renewal certification recertification validation` 與 `time to attend renewal recertification attendance certification validation` 是 attendance/certification recertification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；四個選定 roots 各為 `100 leaks / 48 valid-misses`，四入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示第 1-5、7 組各為 `0 leaks / 0 valid-misses`；第 6、8 組仍是 parser residual `100/48`，因此下一輪先處理 `time to issue renewal attendance recertification certification validation`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 attendance renewal recertification certification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 將四個 roots 合併進共享 `QUALITY_SERVICE_TIME_TO_METRIC_PATTERN` 與 value stripping guard，並由 `backend/report_target_price_detection.py` 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4115 deselected in 35.38s`；shared guard GREEN 為 `5 passed, 4115 deselected in 22.90s`，沒有新增 consumer-specific cleanup。
2. D3451 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded attend renewal attendance recertification certification validation 與 already-guarded attend renewal certification recertification attendance validation controls 均為 `[]`。
3. D3450-D3451 adjacent regression 通過 `10 passed, 4110 deselected in 44.85s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_attend_renewal_attendance_recertification_certification_validation_lifecycle'`：RED `5 failed, 4115 deselected in 35.38s`；GREEN `5 passed, 4115 deselected in 22.90s`。
- D3451 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to attend renewal attendance recertification certification validation` 與 already-guarded `time to attend renewal certification recertification attendance validation` 均為 `[]`；next residual `planning metric time to issue renewal attendance recertification certification validation forecast 12 個` 為 `[12.0]`。
- D3450-D3451 adjacent regression：`10 passed, 4110 deselected in 44.85s`。

### 完成後維護 / D3450 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3449 後重新掃描 attend renewal attendance certification recertification validation、attend certification attendance renewal recertification validation、attend attendance certification renewal recertification validation、attend renewal certification attendance recertification validation 與其他 variants；選擇前四個仍有缺口的 roots，以 attend renewal attendance recertification certification validation、既有 issue/verify/schedule guard、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to attend renewal attendance certification recertification validation`、`time to attend certification attendance renewal recertification validation`、`time to attend attendance certification renewal recertification validation` 與 `time to attend renewal certification attendance recertification validation` 是 attendance/certification recertification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；前四組 parser pre-fix 各為 `100 leaks / 48 valid-misses`，四入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示第 1-4、6-8 組各為 `0 leaks / 0 valid-misses`；第 5 組仍是 parser residual `100/48`，因此下一輪先處理 `time to attend renewal attendance recertification certification validation`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 attendance renewal certification recertification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 將四個 roots 合併進共享 `QUALITY_SERVICE_TIME_TO_METRIC_PATTERN` 與 value stripping guard，並由 `backend/report_target_price_detection.py` 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4110 deselected in 36.81s`；shared guard GREEN 為 `5 passed, 4110 deselected in 23.77s`，沒有新增 consumer-specific cleanup。
2. D3450 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded attend renewal attendance certification recertification validation 與 already-guarded attend renewal certification recertification attendance validation controls 均為 `[]`。
3. D3449-D3450 adjacent regression 通過 `10 passed, 4105 deselected in 54.09s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_attend_renewal_attendance_certification_recertification_validation_lifecycle'`：RED `5 failed, 4110 deselected in 36.81s`；GREEN `5 passed, 4110 deselected in 23.77s`。
- D3450 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to attend renewal attendance certification recertification validation` 與 already-guarded `time to attend renewal certification recertification attendance validation` 均為 `[]`；next residual `planning metric time to attend renewal attendance recertification certification validation forecast 12 個` 為 `[12.0]`。
- D3449-D3450 adjacent regression：`10 passed, 4105 deselected in 54.09s`。

### 完成後維護 / D3449 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3448 後重新掃描 renew certification attendance recertification validation renewal、verify certification attendance recertification validation renewal、schedule certification attendance recertification validation renewal、renew certification recertification attendance validation renewal 與其他四個 variants；選擇前述四個仍有缺口的 roots，以 issue certification attendance recertification validation renewal、renew attendance certification validation recertification renewal、issue renewal certification attendance recertification validation、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to renew certification attendance recertification validation renewal`、`time to verify certification attendance recertification validation renewal`、`time to schedule certification attendance recertification validation renewal` 與 `time to renew certification recertification attendance validation renewal` 是 certification attendance/recertification renewal lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；四個選定 roots 各為 `100 leaks / 48 valid-misses`，四入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示第 1-7 組各為 `0 leaks / 0 valid-misses`；第 8 組仍是 parser residual `100/48`，因此下一輪先處理 `time to attend renewal attendance certification recertification validation`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 certification attendance recertification renewal lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 將四個 roots 合併進共享 `QUALITY_SERVICE_TIME_TO_METRIC_PATTERN` 與 value stripping guard，並由 `backend/report_target_price_detection.py` 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4105 deselected in 35.67s`；shared guard GREEN 為 `5 passed, 4105 deselected in 22.79s`，沒有新增 consumer-specific cleanup。
2. D3449 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded renew certification attendance recertification validation renewal 與 already-guarded attend renewal certification recertification attendance validation controls 均為 `[]`。
3. D3448-D3449 adjacent regression 通過 `10 passed, 4100 deselected in 44.86s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_renew_certification_attendance_recertification_validation_renewal_lifecycle'`：RED `5 failed, 4105 deselected in 35.67s`；GREEN `5 passed, 4105 deselected in 22.79s`。
- D3449 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to renew certification attendance recertification validation renewal` 與 already-guarded `time to attend renewal certification recertification attendance validation` 均為 `[]`；next residual `planning metric time to attend renewal attendance certification recertification validation forecast 12 個` 為 `[12.0]`。
- D3448-D3449 adjacent regression：`10 passed, 4100 deselected in 44.86s`。

### 完成後維護 / D3448 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3447 後重新掃描 renew attendance certification recertification validation renewal、issue attendance certification recertification validation renewal、verify attendance certification recertification validation renewal、schedule attendance certification recertification validation renewal 與其他四個 variants；選擇前四個仍有缺口的 roots，以 issue renewal certification attendance recertification validation、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to renew attendance certification recertification validation renewal`、`time to issue attendance certification recertification validation renewal`、`time to verify attendance certification recertification validation renewal` 與 `time to schedule attendance certification recertification validation renewal` 是 attendance/certification recertification renewal lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；前四組 parser pre-fix 各為 `100 leaks / 48 valid-misses`，四入口 final matrix 各為 480 cases、detector 為 400 cases，所有入口與 union 均為 `0 leaks / 0 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示第 1-4、7 組各為 `0 leaks / 0 valid-misses`；第 5、6、8 組仍是 parser residual `100/48`，因此下一輪先處理 `time to renew certification attendance recertification validation renewal`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 attendance certification recertification renewal lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 將四個 roots 合併進共享 `QUALITY_SERVICE_TIME_TO_METRIC_PATTERN` 與 value stripping guard，並由 `backend/report_target_price_detection.py` 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4100 deselected in 35.70s`；shared guard GREEN 為 `5 passed, 4100 deselected in 23.63s`，沒有新增 consumer-specific cleanup。
2. D3448 post-fix matrix 為 parser、calibration、credibility、structured output 各 `480 cases / 0 leaks / 0 valid-misses`，detector `400 cases / 0 leaks / 0 valid-misses`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded renew attendance certification recertification validation renewal 與 already-guarded attend renewal certification recertification attendance validation controls 均為 `[]`。
3. D3447-D3448 adjacent regression 通過 `10 passed, 4095 deselected in 45.63s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_renew_attendance_certification_recertification_validation_renewal_lifecycle'`：RED `5 failed, 4100 deselected in 35.70s`；GREEN `5 passed, 4100 deselected in 23.63s`。
- D3448 post-fix matrix：四入口各 `480 cases / leaks=0 / valid_misses=0`；detector `400 cases / leaks=0 / valid_misses=0`；union `leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to renew attendance certification recertification validation renewal` 與 already-guarded `time to attend renewal certification recertification attendance validation` 均為 `[]`；next residual `planning metric time to renew certification attendance recertification validation renewal forecast 12 個` 為 `[12.0]`。
- D3447-D3448 adjacent regression：`10 passed, 4095 deselected in 45.63s`。

### 完成後維護 / D3447 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3446 後重新掃描 issue renewal attendance certification recertification validation、verify renewal attendance certification recertification validation、schedule renewal attendance certification recertification validation、complete renewal attendance certification recertification validation 與 issue/verify/attend variants；選擇前四個仍有缺口的 roots，以既有 attend guard、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue renewal attendance certification recertification validation`、`time to verify renewal attendance certification recertification validation`、`time to schedule renewal attendance certification recertification validation` 與 `time to complete renewal attendance certification recertification validation` 是 renewal attendance/certification recertification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；前四組 parser pre-fix 各為 `100 leaks / 48 valid-misses`，五入口 final matrix 為 `480 cases / 0 leaks / 0 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示第 1-4、6 組各為 `0 leaks / 0 valid-misses`；第 5、7、8 組仍是 parser residual `100/48`，因此下一輪先處理 `time to renew attendance certification recertification validation renewal`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 renewal attendance certification recertification validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 將四個 roots 合併進共享 `QUALITY_SERVICE_TIME_TO_METRIC_PATTERN` 與 value stripping guard，並由 `backend/report_target_price_detection.py` 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4095 deselected in 35.87s`；shared guard GREEN 為 `5 passed, 4095 deselected in 22.97s`，沒有新增 consumer-specific cleanup。
2. D3447 post-fix renewal attendance certification recertification validation matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded renewal attendance certification recertification validation 與 already-guarded attend renewal certification recertification attendance validation controls 均為 `[]`。
3. D3446-D3447 adjacent regression 通過 `10 passed, 4090 deselected in 45.31s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_issue_renewal_attendance_certification_recertification_validation_lifecycle'`：RED `5 failed, 4095 deselected in 35.87s`；GREEN `5 passed, 4095 deselected in 22.97s`。
- D3447 post-fix renewal attendance certification recertification validation matrix：`480 cases / leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to issue renewal attendance certification recertification validation` 與 already-guarded `time to attend renewal certification recertification attendance validation` 均為 `[]`；next residual `planning metric time to renew attendance certification recertification validation renewal forecast 12 個` 為 `[12.0]`。
- D3446-D3447 adjacent regression：`10 passed, 4090 deselected in 45.31s`。

### 完成後維護 / D3446 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3445 後重新掃描 complete recertification validation attendance certification renewal、schedule validation recertification certification attendance renewal、renew recertification validation attendance certification renewal、complete validation certification recertification attendance renewal 與 issue、verify、attend variants；選擇四個仍有缺口的 roots，以既有 issue/verify/attend guard、course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to complete recertification validation attendance certification renewal`、`time to schedule validation recertification certification attendance renewal`、`time to renew recertification validation attendance certification renewal` 與 `time to complete validation certification recertification attendance renewal` 是 recertification/certification renewal lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；選取的四組 parser pre-fix 分別為 `80/48`、`100/48`、`80/48`、`100/48`，五入口 final matrix 為 `480 cases / 0 leaks / 0 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示前七組各為 `0 leaks / 0 valid-misses`；第 8 組仍是 parser residual `100/48`，因此下一輪先處理 `time to issue renewal attendance certification recertification validation`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 recertification validation attendance certification renewal lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 將四個 roots 合併進共享 `QUALITY_SERVICE_TIME_TO_METRIC_PATTERN` 與 value stripping guard，並由 `backend/report_target_price_detection.py` 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4090 deselected in 34.95s`；shared guard GREEN 為 `5 passed, 4090 deselected in 22.74s`，沒有新增 consumer-specific cleanup。
2. D3446 post-fix recertification validation attendance certification renewal matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded recertification validation attendance certification renewal 與 already-guarded validation certification renewal recertification attendance controls 均為 `[]`。
3. D3445-D3446 adjacent regression 通過 `10 passed, 4085 deselected in 45.44s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_complete_recertification_validation_attendance_certification_renewal_lifecycle'`：RED `5 failed, 4090 deselected in 34.95s`；GREEN `5 passed, 4090 deselected in 22.74s`。
- D3446 post-fix recertification validation attendance certification renewal matrix：`480 cases / leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to complete recertification validation attendance certification renewal` 與 already-guarded `time to issue validation certification renewal recertification attendance` 均為 `[]`；next residual `planning metric time to issue renewal attendance certification recertification validation forecast 12 個` 為 `[12.0]`。
- D3445-D3446 adjacent regression：`10 passed, 4085 deselected in 45.44s`。

### 完成後維護 / D3445 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3444 後重新掃描 complete attendance certification renewal recertification validation、issue validation certification renewal recertification attendance、verify renewal recertification attendance certification validation、schedule attendance renewal certification validation recertification 與其他 variants，選擇前四個完整缺口 roots；以 `time to renew certification attendance validation recertification renewal`、`time to attend validation certification recertification renewal attendance`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to complete attendance certification renewal recertification validation`、`time to issue validation certification renewal recertification attendance`、`time to verify renewal recertification attendance certification validation` 與 `time to schedule attendance renewal certification validation recertification` 是 attendance/certification renewal lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；前四組各為 `100 leaks / 48 valid-misses`，本輪跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示前六組各為 `0 leaks / 0 valid-misses`；第 7、8 組仍是 parser residual，分別為 `80/48` 與 `100/48`，因此下一輪先處理 `time to complete recertification validation attendance certification renewal`，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 attendance certification renewal recertification validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 新增共享 `QUALITY_SERVICE_TIME_TO_METRIC_PATTERN` 與 value stripping guard，並由 `backend/report_target_price_detection.py` 共用，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4085 deselected in 36.29s`；shared guard GREEN 為 `5 passed, 4085 deselected in 32.01s`，沒有新增 consumer-specific cleanup。
2. D3445 post-fix attendance certification renewal recertification validation matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded attendance certification renewal recertification validation 與 already-guarded renewal certification attendance validation recertification controls 均為 `[]`。
3. D3444-D3445 adjacent regression 通過 `10 passed, 4080 deselected in 65.23s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_complete_attendance_certification_renewal_recertification_validation_lifecycle'`：RED `5 failed, 4085 deselected in 36.29s`；GREEN `5 passed, 4085 deselected in 32.01s`。
- D3445 post-fix attendance certification renewal recertification validation matrix：`480 cases / leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to complete attendance certification renewal recertification validation` 與 already-guarded `time to renew certification attendance validation recertification` 均為 `[]`；next residual `planning metric time to complete recertification validation attendance certification renewal forecast 12 個` 為 `[12.0]`。
- D3444-D3445 adjacent regression：`10 passed, 4080 deselected in 65.23s`。

### 完成後維護 / D3444 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3443 後重新掃描 attendance recertification validation renewal certification、recertification renewal certification validation attendance、recertification validation renewal certification attendance、renewal certification recertification attendance validation 與其他四個 variants，選擇 renew attendance recertification validation renewal certification、issue recertification renewal certification validation attendance、attend recertification validation renewal certification attendance 及 schedule renewal certification recertification attendance validation；以未選取的 `time to complete attendance certification renewal recertification validation`、`time to renew validation certification attendance recertification renewal`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to renew attendance recertification validation renewal certification`、`time to issue recertification renewal certification validation attendance`、`time to attend recertification validation renewal certification attendance` 與 `time to schedule renewal certification recertification attendance validation` 是 attendance/recertification validation lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組、第 6 組與第 7 組各為 `0 leaks / 0 valid-misses`；第 5、8 組仍是 parser residual，分別為 `100/48` 與 `80/48`，因此下一輪先處理第 5 組，不把 financial `time to price` 或明確 `target price` 語意外推。

落地修改

1. 五個報告品質入口新增 attendance recertification validation renewal certification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 attendance recertification validation renewal certification roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4080 deselected in 35.37s`；shared-pattern GREEN 為 `5 passed, 4080 deselected in 32.91s`，沒有新增 consumer-specific cleanup。
2. D3444 post-fix attendance recertification validation renewal certification matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course`、newly guarded renewal attendance recertification validation renewal certification 與 already-guarded validation recertification attendance certification renewal controls 均為 `[]`。
3. D3443-D3444 adjacent regression 通過 `10 passed, 4075 deselected in 66.80s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_renew_attendance_recertification_validation_renewal_certification_lifecycle'`：RED `5 failed, 4080 deselected in 35.37s`；GREEN `5 passed, 4080 deselected in 32.91s`。
- D3444 post-fix attendance recertification validation renewal certification matrix：`480 cases / leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to renew attendance recertification validation renewal certification` 與 already-guarded `time to issue validation recertification attendance certification renewal` 均為 `[]`；next residual `planning metric time to complete attendance certification renewal recertification validation forecast 12 個` 為 `[12.0]`。
- D3443-D3444 adjacent regression：`10 passed, 4075 deselected in 66.80s`。

### 完成後維護 / D3443 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3442 後重新掃描 renewal recertification certification attendance validation、recertification certification validation attendance renewal、validation renewal attendance certification recertification、attendance certification renewal validation recertification 與其他四個 variants，選擇 attend renewal recertification certification attendance validation、schedule recertification certification validation attendance renewal、complete validation renewal attendance certification recertification 及 issue attendance certification renewal validation recertification；以 post-fix `time to renew attendance recertification validation renewal certification`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to attend renewal recertification certification attendance validation`、`time to schedule recertification certification validation attendance renewal`、`time to complete validation renewal attendance certification recertification` 與 `time to issue attendance certification renewal validation recertification` 是 renewal/recertification attendance KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；第 5、7 組既有 guard 比較組也為 `0/0`，第 6、8 組各為 `100/48`，下一輪優先驗證 `time to renew attendance recertification validation renewal certification`。

落地修改

1. 五個報告品質入口新增 renewal recertification certification attendance validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 renewal recertification certification attendance validation roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4075 deselected in 35.81s`；shared-pattern GREEN 為 `5 passed, 4075 deselected in 33.25s`，沒有新增 consumer-specific cleanup。
2. D3443 post-fix renewal recertification certification attendance validation matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded renewal recertification certification attendance validation controls 均為 `[]`。
3. D3442-D3443 adjacent regression 通過 `10 passed, 4070 deselected in 65.64s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_attend_renewal_recertification_certification_attendance_validation_lifecycle'`：RED `5 failed, 4075 deselected in 35.81s`；GREEN `5 passed, 4075 deselected in 33.25s`。
- D3443 post-fix renewal recertification certification attendance validation matrix：`480 cases / leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to attend renewal recertification certification attendance validation` 與 already-guarded `time to verify certification renewal recertification attendance validation` 均為 `[]`；next residual `time to renew attendance recertification validation renewal certification target 12 個` 為 `[12.0]`。
- D3442-D3443 adjacent regression：`10 passed, 4070 deselected in 65.64s`。

### 完成後維護 / D3442 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3441 後重新掃描 renewal attendance recertification certification validation、certification recertification validation attendance renewal、recertification attendance renewal validation certification、certification validation renewal recertification attendance 與其他四個 variants，選擇 verify renewal attendance recertification certification validation、renew certification recertification validation attendance renewal、complete recertification attendance renewal validation certification 及 issue certification validation renewal recertification attendance；以 post-fix `time to attend renewal recertification certification attendance validation`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to verify renewal attendance recertification certification validation`、`time to renew certification recertification validation attendance renewal`、`time to complete recertification attendance renewal validation certification` 與 `time to issue certification validation renewal recertification attendance` 是 renewal/recertification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；後四組各為 `100/48`，下一輪優先驗證 `time to attend renewal recertification certification attendance validation`。

落地修改

1. 五個報告品質入口新增 renewal attendance recertification certification validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 renewal attendance recertification certification validation roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4070 deselected in 35.44s`；shared-pattern GREEN 為 `5 passed, 4070 deselected in 33.29s`，沒有新增 consumer-specific cleanup。
2. D3442 post-fix renewal attendance recertification certification validation matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded renewal attendance recertification certification validation controls 均為 `[]`。
3. D3441-D3442 adjacent regression 通過 `10 passed, 4065 deselected in 65.79s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_verify_renewal_attendance_recertification_certification_validation_lifecycle'`：RED `5 failed, 4070 deselected in 35.44s`；GREEN `5 passed, 4070 deselected in 33.29s`。
- D3442 post-fix renewal attendance recertification certification validation matrix：`480 cases / leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to verify renewal attendance recertification certification validation` 均為 `[]`；next residual `time to attend renewal recertification certification attendance validation target 12 個` 為 `[12.0]`。
- D3441-D3442 adjacent regression：`10 passed, 4065 deselected in 65.79s`。

### 完成後維護 / D3441 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3440 後重新掃描 recertification renewal certification validation attendance、certification recertification validation renewal attendance、attendance renewal certification validation recertification、validation attendance recertification renewal certification 與其他四個 variants，選擇 attend recertification renewal certification validation attendance、schedule certification recertification validation renewal attendance、complete attendance renewal certification validation recertification 及 issue validation attendance recertification renewal certification；以 post-fix `time to verify renewal attendance recertification certification validation`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to attend recertification renewal certification validation attendance`、`time to schedule certification recertification validation renewal attendance`、`time to complete attendance renewal certification validation recertification` 與 `time to issue validation attendance recertification renewal certification` 是 recertification/attendance lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；後四組各為 `100/48`，下一輪優先驗證 `time to verify renewal attendance recertification certification validation`。

落地修改

1. 五個報告品質入口新增 recertification renewal certification validation attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 recertification renewal certification validation attendance roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4065 deselected in 35.42s`；shared-pattern GREEN 為 `5 passed, 4065 deselected in 33.20s`，沒有新增 consumer-specific cleanup。
2. D3441 post-fix recertification renewal certification validation attendance matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded recertification renewal certification validation attendance controls 均為 `[]`。
3. D3440-D3441 adjacent regression 通過 `10 passed, 4060 deselected in 65.29s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_attend_recertification_renewal_certification_validation_attendance_lifecycle'`：RED `5 failed, 4065 deselected in 35.42s`；GREEN `5 passed, 4065 deselected in 33.20s`。
- D3441 post-fix recertification renewal certification validation attendance matrix：`480 cases / leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to attend recertification renewal certification validation attendance` 均為 `[]`；next residual `time to verify renewal attendance recertification certification validation target 12 個` 為 `[12.0]`。
- D3440-D3441 adjacent regression：`10 passed, 4060 deselected in 65.29s`。

### 完成後維護 / D3440 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3439 後重新掃描 attendance recertification renewal certification validation、recertification attendance validation certification renewal、certification validation attendance renewal recertification、renewal certification attendance recertification validation 與其他四個 variants，選擇 verify attendance recertification renewal certification validation、renew recertification attendance validation certification renewal、complete certification validation attendance renewal recertification 及 issue renewal certification attendance recertification validation；以 post-fix `time to attend recertification renewal certification validation attendance`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to verify attendance recertification renewal certification validation`、`time to renew recertification attendance validation certification renewal`、`time to complete certification validation attendance renewal recertification` 與 `time to issue renewal certification attendance recertification validation` 是 attendance/recertification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；後四組各為 `100/48`，下一輪優先驗證 `time to attend recertification renewal certification validation attendance`。

落地修改

1. 五個報告品質入口新增 attendance recertification renewal certification validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 attendance recertification renewal certification validation roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4060 deselected in 35.16s`；shared-pattern GREEN 為 `5 passed, 4060 deselected in 33.20s`，沒有新增 consumer-specific cleanup。
2. D3440 post-fix attendance recertification renewal certification validation matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded attendance recertification renewal certification validation controls 均為 `[]`。
3. D3439-D3440 adjacent regression 通過 `10 passed, 4055 deselected in 66.05s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_verify_attendance_recertification_renewal_certification_validation_lifecycle'`：RED `5 failed, 4060 deselected in 35.16s`；GREEN `5 passed, 4060 deselected in 33.20s`。
- D3440 post-fix attendance recertification renewal certification validation matrix：`480 cases / leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to verify attendance recertification renewal certification validation` 均為 `[]`；next residual `time to attend recertification renewal certification validation attendance target 12 個` 為 `[12.0]`。
- D3439-D3440 adjacent regression：`10 passed, 4055 deselected in 66.05s`。

### 完成後維護 / D3439 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3438 後重新掃描 certification renewal recertification validation attendance、validation certification renewal recertification attendance、renewal certification recertification validation attendance、attendance recertification validation certification renewal 與其他四個 variants，選擇 attend certification renewal recertification validation attendance、schedule validation certification renewal recertification attendance、complete renewal certification recertification validation attendance 及 issue attendance recertification validation certification renewal；以 post-fix `time to verify attendance recertification renewal certification validation`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to attend certification renewal recertification validation attendance`、`time to schedule validation certification renewal recertification attendance`、`time to complete renewal certification recertification validation attendance` 與 `time to issue attendance recertification validation certification renewal` 是 certification/recertification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；後四組分別為 `100/48`、`80/48`、`100/48`、`100/48`，下一輪優先驗證 `time to verify attendance recertification renewal certification validation`。

落地修改

1. 五個報告品質入口新增 certification renewal recertification validation attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 certification renewal recertification validation attendance roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4055 deselected in 34.99s`；shared-pattern GREEN 為 `5 passed, 4055 deselected in 33.79s`，沒有新增 consumer-specific cleanup。
2. D3439 post-fix certification renewal recertification validation attendance matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded certification renewal recertification validation attendance controls 均為 `[]`。
3. D3438-D3439 adjacent regression 通過 `10 passed, 4050 deselected in 78.45s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_attend_certification_renewal_recertification_validation_attendance_lifecycle'`：RED `5 failed, 4055 deselected in 34.99s`；GREEN `5 passed, 4055 deselected in 33.79s`。
- D3439 post-fix certification renewal recertification validation attendance matrix：`480 cases / leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to attend certification renewal recertification validation attendance` 均為 `[]`；next residual `time to verify attendance recertification renewal certification validation target 12 個` 為 `[12.0]`。
- D3438-D3439 adjacent regression：`10 passed, 4050 deselected in 78.45s`。

### 完成後維護 / D3438 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3437 後重新掃描 certification renewal attendance recertification validation、attendance certification validation recertification renewal、recertification validation certification attendance renewal、validation certification recertification renewal attendance 與其他四個 variants，選擇 verify certification renewal attendance recertification validation、renew attendance certification validation recertification renewal、complete recertification validation certification attendance renewal 及 issue validation certification recertification renewal attendance；以 post-fix `time to attend certification renewal recertification validation attendance`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to verify certification renewal attendance recertification validation`、`time to renew attendance certification validation recertification renewal`、`time to complete recertification validation certification attendance renewal` 與 `time to issue validation certification recertification renewal attendance` 是 certification/recertification renewal KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；後四組分別為 `100/48`、`100/48`、`100/48`、`80/48`，下一輪優先驗證 `time to attend certification renewal recertification validation attendance`。

落地修改

1. 五個報告品質入口新增 certification renewal attendance recertification validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 certification renewal attendance recertification validation roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4050 deselected in 43.75s`；shared-pattern GREEN 為 `5 passed, 4050 deselected in 33.29s`，沒有新增 consumer-specific cleanup。
2. D3438 post-fix certification renewal attendance recertification validation matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded certification renewal attendance recertification validation controls 均為 `[]`。
3. D3437-D3438 adjacent regression 通過 `10 passed, 4045 deselected in 65.69s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_verify_certification_renewal_attendance_recertification_validation_lifecycle'`：RED `5 failed, 4050 deselected in 43.75s`；GREEN `5 passed, 4050 deselected in 33.29s`。
- D3438 post-fix certification renewal attendance recertification validation matrix：`480 cases / leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to verify certification renewal attendance recertification validation` 均為 `[]`；next residual `time to attend certification renewal recertification validation attendance target 12 個` 為 `[12.0]`。
- D3437-D3438 adjacent regression：`10 passed, 4045 deselected in 65.69s`。

### 完成後維護 / D3437 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3436 後重新掃描 certification renewal attendance validation recertification、validation attendance renewal certification recertification、recertification certification renewal attendance validation、renewal certification recertification attendance validation 與其他四個 variants，選擇 schedule certification renewal attendance validation recertification、complete validation attendance renewal certification recertification、issue recertification certification renewal attendance validation 及 attend renewal certification recertification attendance validation；以 post-fix `time to verify certification renewal attendance recertification validation`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to schedule certification renewal attendance validation recertification`、`time to complete validation attendance renewal certification recertification`、`time to issue recertification certification renewal attendance validation` 與 `time to attend renewal certification recertification attendance validation` 是 certification renewal/attendance KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；後四組分別為 `100/48`、`80/48`、`100/48`、`100/48`，下一輪優先驗證 `time to verify certification renewal attendance recertification validation`。

落地修改

1. 五個報告品質入口新增 certification renewal attendance validation recertification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 certification renewal attendance validation recertification roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4045 deselected in 35.52s`；shared-pattern GREEN 為 `5 passed, 4045 deselected in 34.04s`，沒有新增 consumer-specific cleanup。
2. D3437 post-fix certification renewal attendance validation recertification matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded certification renewal attendance validation recertification controls 均為 `[]`。
3. D3436-D3437 adjacent regression 通過 `10 passed, 4040 deselected in 66.03s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_schedule_certification_renewal_attendance_validation_recertification_lifecycle'`：RED `5 failed, 4045 deselected in 35.52s`；GREEN `5 passed, 4045 deselected in 34.04s`。
- D3437 post-fix certification renewal attendance validation recertification matrix：`480 cases / leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to schedule certification renewal attendance validation recertification` 均為 `[]`；next residual `time to verify certification renewal attendance recertification validation target 12 個` 為 `[12.0]`。
- D3436-D3437 adjacent regression：`10 passed, 4040 deselected in 66.03s`。

### 完成後維護 / D3436 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3435 後重新掃描 renewal certification attendance validation recertification、renewal validation certification attendance recertification、certification attendance validation recertification renewal、attendance renewal recertification validation certification 與其他四個 variants，選擇 verify renewal certification attendance validation recertification、renew renewal validation certification attendance recertification、complete certification attendance validation recertification renewal 及 issue attendance renewal recertification validation certification；以 post-fix `time to schedule certification renewal attendance validation recertification`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to verify renewal certification attendance validation recertification`、`time to renew renewal validation certification attendance recertification`、`time to complete certification attendance validation recertification renewal` 與 `time to issue attendance renewal recertification validation certification` 是 renewal/certification attendance KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；後四組各為 `100/48`，下一輪優先驗證 `time to schedule certification renewal attendance validation recertification`。

落地修改

1. 五個報告品質入口新增 renewal certification attendance validation recertification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 renewal certification attendance validation recertification roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4040 deselected in 31.89s`；shared-pattern GREEN 為 `5 passed, 4040 deselected in 33.18s`，沒有新增 consumer-specific cleanup。
2. D3436 post-fix renewal certification attendance validation recertification matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded renewal certification attendance validation recertification controls 均為 `[]`。
3. D3435-D3436 adjacent regression 通過 `10 passed, 4035 deselected in 65.35s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_verify_renewal_certification_attendance_validation_recertification_lifecycle'`：RED `5 failed, 4040 deselected in 31.89s`；GREEN `5 passed, 4040 deselected in 33.18s`。
- D3436 post-fix renewal certification attendance validation recertification matrix：`480 cases / leaks=0 / valid_misses=0`。
- controls：explicit target price `[205.0]`；financial `time to price`、existing `time to complete course`、newly guarded `time to verify renewal certification attendance validation recertification` 均為 `[]`；next residual `time to schedule certification renewal attendance validation recertification target 12 個` 為 `[12.0]`。
- D3435-D3436 adjacent regression：`10 passed, 4035 deselected in 65.35s`。

### 完成後維護 / D3435 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3434 後重新掃描 renewal validation certification attendance recertification、validation certification attendance renewal recertification、recertification attendance renewal validation certification、certification validation renewal recertification attendance 與其他四個 variants，選擇 schedule renewal validation certification attendance recertification、complete validation certification attendance renewal recertification、issue recertification attendance renewal validation certification 及 attend certification validation renewal recertification attendance；以 post-fix `time to verify renewal certification attendance validation recertification`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to schedule renewal validation certification attendance recertification`、`time to complete validation certification attendance renewal recertification`、`time to issue recertification attendance renewal validation certification` 與 `time to attend certification validation renewal recertification attendance` 是 renewal validation/certification KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；後四組分別為 `100/48`、`80/48`、`100/48`、`100/48`，下一輪優先驗證 `time to verify renewal certification attendance validation recertification`。

落地修改

1. 五個報告品質入口新增 renewal validation certification attendance recertification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 renewal validation certification attendance recertification roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4035 deselected in 36.19s`；shared-pattern GREEN 為 `5 passed, 4035 deselected in 33.39s`，沒有新增 consumer-specific cleanup。
2. D3435 post-fix renewal validation certification attendance recertification matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded renewal validation certification attendance recertification controls 均為 `[]`。
3. D3434-D3435 adjacent regression 通過 `10 passed, 4030 deselected in 65.53s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_schedule_renewal_validation_certification_attendance_recertification_lifecycle'`：RED `5 failed, 4035 deselected in 36.19s`；GREEN `5 passed, 4035 deselected in 33.39s`。
- D3435 post-fix renewal validation certification attendance recertification matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded renewal validation certification attendance recertification：`[]`；post-fix next residual `time to verify renewal certification attendance validation recertification target 12 個`：`[12.0]`。
- D3434-D3435 adjacent regression：`10 passed, 4030 deselected in 65.53s`。

### 完成後維護 / D3434 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3433 後重新掃描 certification attendance renewal validation recertification、certification attendance validation recertification renewal、attendance renewal validation certification recertification、validation recertification attendance certification renewal 與其他四個 variants，選擇 verify certification attendance renewal validation recertification、renew certification attendance validation recertification renewal、complete attendance renewal validation certification recertification 及 issue validation recertification attendance certification renewal；以 post-fix `time to schedule renewal validation certification attendance recertification`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to verify certification attendance renewal validation recertification`、`time to renew certification attendance validation recertification renewal`、`time to complete attendance renewal validation certification recertification` 與 `time to issue validation recertification attendance certification renewal` 是 certification attendance/renewal KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；後四組各為 `100/48`，下一輪優先驗證 `time to schedule renewal validation certification attendance recertification`。

落地修改

1. 五個報告品質入口新增 certification attendance renewal validation recertification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 certification attendance renewal validation recertification roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4030 deselected in 34.10s`；shared-pattern GREEN 為 `5 passed, 4030 deselected in 33.13s`，沒有新增 consumer-specific cleanup。
2. D3434 post-fix certification attendance renewal validation recertification matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded certification attendance renewal validation recertification controls 均為 `[]`。
3. D3433-D3434 adjacent regression 通過 `10 passed, 4025 deselected in 74.97s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_verify_certification_attendance_renewal_validation_recertification_lifecycle'`：RED `5 failed, 4030 deselected in 34.10s`；GREEN `5 passed, 4030 deselected in 33.13s`。
- D3434 post-fix certification attendance renewal validation recertification matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded certification attendance renewal validation recertification：`[]`；post-fix next residual `time to schedule renewal validation certification attendance recertification target 12 個`：`[12.0]`。
- D3433-D3434 adjacent regression：`10 passed, 4025 deselected in 74.97s`。

### 完成後維護 / D3433 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3432 後重新掃描 certification validation attendance renewal recertification、renewal certification attendance validation recertification、recertification renewal attendance certification validation、validation recertification certification renewal attendance 與其他四個 variants，選擇 schedule certification validation attendance renewal recertification、complete renewal certification attendance validation recertification、issue recertification renewal attendance certification validation 及 attend validation recertification certification renewal attendance；以 post-fix `time to verify certification attendance renewal validation recertification`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to schedule certification validation attendance renewal recertification`、`time to complete renewal certification attendance validation recertification`、`time to issue recertification renewal attendance certification validation` 與 `time to attend validation recertification certification renewal attendance` 是 certification validation/renewal KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；後四組分別為 `100/48`、`80/48`、`100/48`、`100/48`，下一輪優先驗證 `time to verify certification attendance renewal validation recertification`。

落地修改

1. 五個報告品質入口新增 certification validation attendance renewal recertification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 certification validation attendance renewal recertification roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4025 deselected in 36.17s`；shared-pattern GREEN 為 `5 passed, 4025 deselected in 36.43s`，沒有新增 consumer-specific cleanup。
2. D3433 post-fix certification validation attendance renewal recertification matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded certification validation attendance renewal recertification controls 均為 `[]`。
3. D3432-D3433 adjacent regression 通過 `10 passed, 4020 deselected in 65.35s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_schedule_certification_validation_attendance_renewal_recertification_lifecycle'`：RED `5 failed, 4025 deselected in 36.17s`；GREEN `5 passed, 4025 deselected in 36.43s`。
- D3433 post-fix certification validation attendance renewal recertification matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded certification validation attendance renewal recertification：`[]`；post-fix next residual `time to verify certification attendance renewal validation recertification target 12 個`：`[12.0]`。
- D3432-D3433 adjacent regression：`10 passed, 4020 deselected in 65.35s`。

### 完成後維護 / D3432 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3431 後重新掃描 validation attendance certification renewal recertification、validation certification attendance recertification、attendance certification validation renewal recertification、certification attendance recertification validation renewal 與其他四個 variants，選擇 verify validation attendance certification renewal recertification、renew validation certification attendance recertification、complete attendance certification validation renewal recertification 及 issue certification attendance recertification validation renewal；以 post-fix `time to schedule certification validation attendance renewal recertification`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to verify validation attendance certification renewal recertification`、`time to renew validation certification attendance recertification`、`time to complete attendance certification validation renewal recertification` 與 `time to issue certification attendance recertification validation renewal` 是 validation/attendance certification KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；後四組各為 `100/48`，下一輪優先驗證 `time to schedule certification validation attendance renewal recertification`。

落地修改

1. 五個報告品質入口新增 validation attendance certification renewal recertification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 validation attendance certification renewal recertification roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4020 deselected in 34.67s`；shared-pattern GREEN 為 `5 passed, 4020 deselected in 32.84s`，沒有新增 consumer-specific cleanup。
2. D3432 post-fix validation attendance certification renewal recertification matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded validation attendance certification renewal recertification controls 均為 `[]`。
3. D3431-D3432 adjacent regression 通過 `10 passed, 4015 deselected in 65.25s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_verify_validation_attendance_certification_renewal_recertification_lifecycle'`：RED `5 failed, 4020 deselected in 34.67s`；GREEN `5 passed, 4020 deselected in 32.84s`。
- D3432 post-fix validation attendance certification renewal recertification matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded validation attendance certification renewal recertification：`[]`；post-fix next residual `time to schedule certification validation attendance renewal recertification target 12 個`：`[12.0]`。
- D3431-D3432 adjacent regression：`10 passed, 4015 deselected in 65.25s`。

### 完成後維護 / D3431 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3430 後重新掃描 attendance renewal certification recertification validation、validation renewal attendance recertification certification、recertification validation certification attendance renewal、certification renewal validation recertification attendance 與其他四個 variants，選擇 schedule attendance renewal certification recertification validation、complete validation renewal attendance recertification certification、issue recertification validation certification attendance renewal 及 attend certification renewal validation recertification attendance；以 post-fix `time to verify validation attendance certification renewal recertification`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to schedule attendance renewal certification recertification validation`、`time to complete validation renewal attendance recertification certification`、`time to issue recertification validation certification attendance renewal` 與 `time to attend certification renewal validation recertification attendance` 是 attendance renewal/recertification KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；後四組分別為 `100/48`、`80/48`、`100/48`、`100/48`，下一輪優先驗證 `time to verify validation attendance certification renewal recertification`。

落地修改

1. 五個報告品質入口新增 attendance renewal certification recertification validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 attendance renewal certification recertification validation roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4015 deselected in 35.52s`；shared-pattern GREEN 為 `5 passed, 4015 deselected in 33.27s`，沒有新增 consumer-specific cleanup。
2. D3431 post-fix attendance renewal certification recertification validation matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded attendance renewal certification recertification validation controls 均為 `[]`。
3. D3430-D3431 adjacent regression 通過 `10 passed, 4010 deselected in 65.50s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_schedule_attendance_renewal_certification_recertification_validation_lifecycle'`：RED `5 failed, 4015 deselected in 35.52s`；GREEN `5 passed, 4015 deselected in 33.27s`。
- D3431 post-fix attendance renewal certification recertification validation matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded attendance renewal certification recertification validation：`[]`；post-fix next residual `time to verify validation attendance certification renewal recertification target 12 個`：`[12.0]`。
- D3430-D3431 adjacent regression：`10 passed, 4010 deselected in 65.50s`。

### 完成後維護 / D3430 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3429 後重新掃描 attendance certification renewal recertification validation、certification validation recertification attendance renewal、renewal attendance certification validation recertification、certification recertification attendance validation renewal 與其他四個 variants，選擇 verify attendance certification renewal recertification validation、renew certification validation recertification attendance renewal、complete renewal attendance certification validation recertification 及 issue certification recertification attendance validation renewal；以 post-fix `time to schedule attendance renewal certification recertification validation`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to verify attendance certification renewal recertification validation`、`time to renew certification validation recertification attendance renewal`、`time to complete renewal attendance certification validation recertification` 與 `time to issue certification recertification attendance validation renewal` 是 attendance/certification renewal KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；後四組各為 `100/48`，下一輪優先驗證 `time to schedule attendance renewal certification recertification validation`。

落地修改

1. 五個報告品質入口新增 attendance certification renewal recertification validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 attendance certification renewal recertification validation roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4010 deselected in 35.31s`；shared-pattern GREEN 為 `5 passed, 4010 deselected in 33.18s`，沒有新增 consumer-specific cleanup。
2. D3430 post-fix attendance certification renewal recertification validation matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded attendance certification renewal recertification validation controls 均為 `[]`。
3. D3429-D3430 adjacent regression 通過 `10 passed, 4005 deselected in 65.49s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_verify_attendance_certification_renewal_recertification_validation_lifecycle'`：RED `5 failed, 4010 deselected in 35.31s`；GREEN `5 passed, 4010 deselected in 33.18s`。
- D3430 post-fix attendance certification renewal recertification validation matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded attendance certification renewal recertification validation：`[]`；post-fix next residual `time to schedule attendance renewal certification recertification validation target 12 個`：`[12.0]`。
- D3429-D3430 adjacent regression：`10 passed, 4005 deselected in 65.49s`。

### 完成後維護 / D3429 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3428 後重新掃描 validation renewal recertification certification attendance、attendance validation recertification certification renewal、renewal recertification certification attendance validation、validation certification recertification renewal attendance 與其他四個 variants，選擇 schedule validation renewal recertification certification attendance、complete attendance validation recertification certification renewal、issue renewal recertification certification attendance validation 及 attend validation certification recertification renewal attendance；以 post-fix `time to verify attendance certification renewal recertification validation`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to schedule validation renewal recertification certification attendance`、`time to complete attendance validation recertification certification renewal`、`time to issue renewal recertification certification attendance validation` 與 `time to attend validation certification recertification renewal attendance` 是 validation/renewal certification attendance KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；後四組各為 `100/48`，下一輪優先驗證 `time to verify attendance certification renewal recertification validation`。

落地修改

1. 五個報告品質入口新增 validation renewal recertification certification attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 validation renewal recertification certification attendance roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4005 deselected in 35.39s`；shared-pattern GREEN 為 `5 passed, 4005 deselected in 33.37s`，沒有新增 consumer-specific cleanup。
2. D3429 post-fix validation renewal recertification certification attendance matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded validation renewal recertification certification attendance controls 均為 `[]`。
3. D3428-D3429 adjacent regression 通過 `10 passed, 4000 deselected in 75.03s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_schedule_validation_renewal_recertification_certification_attendance_lifecycle'`：RED `5 failed, 4005 deselected in 35.39s`；GREEN `5 passed, 4005 deselected in 33.37s`。
- D3429 post-fix validation renewal recertification certification attendance matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded validation renewal recertification certification attendance：`[]`；post-fix next residual `time to verify attendance certification renewal recertification validation target 12 個`：`[12.0]`。
- D3428-D3429 adjacent regression：`10 passed, 4000 deselected in 75.03s`。

### 完成後維護 / D3428 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3427 後重新掃描 certification renewal recertification attendance validation、validation attendance recertification certification、certification validation recertification renewal attendance、recertification attendance certification validation renewal 與其他四個 variants，選擇 verify certification renewal recertification attendance validation、renew validation attendance recertification certification、complete certification validation recertification renewal attendance 及 issue recertification attendance certification validation renewal；以 post-fix `time to schedule validation renewal recertification certification attendance`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to verify certification renewal recertification attendance validation`、`time to renew validation attendance recertification certification`、`time to complete certification validation recertification renewal attendance` 與 `time to issue recertification attendance certification validation renewal` 是 certification/recertification attendance KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；後四組仍為 residual family，下一輪優先驗證 `time to schedule validation renewal recertification certification attendance`。

落地修改

1. 五個報告品質入口新增 certification renewal recertification attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 certification renewal recertification attendance roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 4000 deselected in 34.56s`；shared-pattern GREEN 為 `5 passed, 4000 deselected in 32.68s`，沒有新增 consumer-specific cleanup。
2. D3428 post-fix certification renewal recertification attendance matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded certification renewal recertification attendance validation controls 均為 `[]`。
3. D3427-D3428 adjacent regression 通過 `10 passed, 3995 deselected in 63.91s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_verify_certification_renewal_recertification_attendance_validation_lifecycle'`：RED `5 failed, 4000 deselected in 34.56s`；GREEN `5 passed, 4000 deselected in 32.68s`。
- D3428 post-fix certification renewal recertification attendance matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded certification renewal recertification attendance validation：`[]`；post-fix next residual `time to schedule validation renewal recertification certification attendance target 12 個`：`[12.0]`。
- D3427-D3428 adjacent regression：`10 passed, 3995 deselected in 63.91s`。

### 完成後維護 / D3427 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3426 後重新掃描 renewal recertification certification attendance、recertification certification validation attendance、validation certification recertification attendance renewal、recertification certification attendance validation 與其他四個 variants，選擇 schedule renewal recertification certification attendance、complete recertification certification validation attendance、issue validation certification recertification attendance renewal 及 attend recertification certification attendance validation；以 post-fix `time to verify certification renewal recertification attendance validation`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to schedule renewal recertification certification attendance`、`time to complete recertification certification validation attendance`、`time to issue validation certification recertification attendance renewal` 與 `time to attend recertification certification attendance validation` 是 renewal/recertification certification attendance KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；後四組仍是完整 residual family，下一輪優先驗證 `time to verify certification renewal recertification attendance validation`。

落地修改

1. 五個報告品質入口新增 renewal recertification certification attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 renewal recertification certification attendance roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 3995 deselected in 33.62s`；shared-pattern GREEN 為 `5 passed, 3995 deselected in 32.41s`，沒有新增 consumer-specific cleanup。
2. D3427 post-fix renewal recertification certification attendance matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded validation certification recertification attendance renewal controls 均為 `[]`。
3. D3426-D3427 adjacent regression 通過 `10 passed, 3990 deselected in 62.04s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_renewal_recertification_certification_attendance_lifecycle'`：RED `5 failed, 3995 deselected in 33.62s`；GREEN `5 passed, 3995 deselected in 32.41s`。
- D3427 post-fix renewal recertification certification attendance matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded validation certification recertification attendance renewal：`[]`；post-fix next residual `time to verify certification renewal recertification attendance validation target 12 個`：`[12.0]`。
- D3426-D3427 adjacent regression：`10 passed, 3990 deselected in 62.04s`。

### 完成後維護 / D3426 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3425 後重新掃描 renewal validation recertification attendance、attendance recertification certification validation、certification validation renewal attendance、recertification attendance certification validation 與其他四個 variants，選擇 verify renewal validation recertification attendance、complete attendance recertification certification validation、issue certification validation renewal attendance 及 renew recertification attendance certification validation；以 post-fix `time to schedule renewal recertification certification attendance`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to verify renewal validation recertification attendance`、`time to complete attendance recertification certification validation`、`time to issue certification validation renewal attendance` 與 `time to renew recertification attendance certification validation` 是 validation/recertification attendance KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；後四組各為 `100 / 120`，因此下一輪仍有四組可獨立驗證的完整缺口。

落地修改

1. 五個報告品質入口新增 renewal validation recertification attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 renewal validation recertification attendance roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 3990 deselected in 33.07s`；shared-pattern GREEN 通過 `5 passed in 31.29s`，沒有新增 consumer-specific cleanup。
2. D3426 post-fix renewal validation recertification attendance matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded recertification attendance certification validation controls 均為 `[]`。
3. D3425-D3426 adjacent regression 通過 `10 passed, 3985 deselected in 62.21s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_renewal_validation_recertification_attendance_lifecycle'`：`5 passed in 31.29s`。
- D3426 post-fix renewal validation recertification attendance matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded recertification attendance certification validation：`[]`；post-fix next residual `time to schedule renewal recertification certification attendance target 12 個`：`[12.0]`。
- D3425-D3426 adjacent regression：`10 passed, 3985 deselected in 62.21s`。

### 完成後維護 / D3425 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3424 後重新掃描 validation recertification certification attendance scheduling、recertification validation renewal attendance、renewal certification recertification attendance validation、certification recertification validation renewal 與其他四個 variants，選擇 schedule validation recertification certification attendance、complete recertification validation renewal attendance、issue renewal certification recertification attendance validation 及 attend certification recertification validation renewal；以 post-fix `time to verify renewal validation recertification attendance`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to schedule validation recertification certification attendance`、`time to complete recertification validation renewal attendance`、`time to issue renewal certification recertification attendance validation` 與 `time to attend certification recertification validation renewal` 是 validation/recertification attendance KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；後四組各為 `100 / 120`，因此下一輪仍有四組可獨立驗證的完整缺口。

落地修改

1. 五個報告品質入口新增 validation recertification certification attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 validation recertification certification attendance roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 3985 deselected in 33.70s`；shared-pattern GREEN 通過 `5 passed in 31.70s`，沒有新增 consumer-specific cleanup。
2. D3425 post-fix validation recertification certification attendance matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded certification recertification validation renewal controls 均為 `[]`。
3. D3424-D3425 adjacent regression 通過 `10 passed, 3980 deselected in 61.66s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_validation_recertification_certification_attendance_lifecycle'`：`5 passed in 31.70s`。
- D3425 post-fix validation recertification certification attendance matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded certification recertification validation renewal：`[]`；post-fix next residual `time to verify renewal validation recertification attendance target 12 個`：`[12.0]`。
- D3424-D3425 adjacent regression：`10 passed, 3980 deselected in 61.66s`。

### 完成後維護 / D3424 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3423 後重新掃描 validation recertification attendance completion、attendance certification renewal validation、recertification validation certification attendance、certification attendance validation recertification 與其他四個 variants，選擇 complete validation recertification attendance、issue attendance certification renewal validation、verify recertification validation certification attendance 及 renew certification attendance validation recertification；以 post-fix `time to schedule validation recertification certification attendance`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to complete validation recertification attendance`、`time to issue attendance certification renewal validation`、`time to verify recertification validation certification attendance` 與 `time to renew certification attendance validation recertification` 是 validation/recertification attendance KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；後四組各為 `100 / 120`，因此下一輪仍有四組可獨立驗證的完整缺口。

落地修改

1. 五個報告品質入口新增 validation recertification attendance certification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 validation recertification attendance certification roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 3980 deselected in 31.70s`；shared-pattern GREEN 通過 `5 passed in 30.76s`，沒有新增 consumer-specific cleanup。
2. D3424 post-fix validation recertification attendance certification matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded certification attendance validation recertification controls 均為 `[]`。
3. D3423-D3424 adjacent regression 通過 `10 passed, 3975 deselected in 59.59s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_validation_recertification_attendance_certification_lifecycle'`：`5 passed in 30.76s`。
- D3424 post-fix validation recertification attendance certification matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded certification attendance validation recertification：`[]`；post-fix next residual `time to schedule validation recertification certification attendance target 12 個`：`[12.0]`。
- D3423-D3424 adjacent regression：`10 passed, 3975 deselected in 59.59s`。

### 完成後維護 / D3423 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3422 後重新掃描 validation recertification attendance issuance、renewal certification validation、recertification certification attendance、certification validation renewal attendance 與其他四個 variants，選擇 issue validation recertification attendance、attend renewal certification validation、schedule recertification certification attendance 及 verify certification validation renewal attendance；以 post-fix `time to complete validation recertification attendance`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue validation recertification attendance`、`time to attend renewal certification validation`、`time to schedule recertification certification attendance` 與 `time to verify certification validation renewal attendance` 是 validation/recertification attendance KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；後四組各為 `100 / 120`，因此下一輪仍有四組可獨立驗證的完整缺口。

落地修改

1. 五個報告品質入口新增 validation recertification attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 validation recertification attendance roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 3975 deselected in 29.98s`；shared-pattern GREEN 通過 `5 passed in 29.61s`，沒有新增 consumer-specific cleanup。
2. D3423 post-fix validation recertification attendance matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded certification validation renewal attendance controls 均為 `[]`。
3. D3422-D3423 adjacent regression 通過 `10 passed, 3970 deselected in 58.85s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_validation_recertification_attendance_lifecycle'`：`5 passed in 29.61s`。
- D3423 post-fix validation recertification attendance matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded certification validation renewal attendance：`[]`；post-fix next residual `time to complete validation recertification attendance target 12 個`：`[12.0]`。
- D3422-D3423 adjacent regression：`10 passed, 3970 deselected in 58.85s`。

### 完成後維護 / D3422 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3421 後重新掃描 certification attendance renewal validation、validation recertification attendance、certification recertification validation、certification attendance renewal validation 與其他四個 variants，選擇 verify certification attendance renewal validation、renew validation recertification attendance、schedule certification recertification validation 及 complete certification attendance renewal validation；以 post-fix `time to issue validation recertification attendance`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to verify certification attendance renewal validation`、`time to renew validation recertification attendance`、`time to schedule certification recertification validation` 與 `time to complete certification attendance renewal validation` 是 certification/recertification validation KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定前四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；後四組各為 `100 / 120`，因此下一輪仍有四組可獨立驗證的完整缺口。

落地修改

1. 五個報告品質入口新增 certification attendance renewal validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 certification attendance renewal validation roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 3970 deselected in 30.42s`；shared-pattern GREEN 通過 `5 passed in 30.02s`，沒有新增 consumer-specific cleanup。
2. D3422 post-fix certification attendance renewal validation matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded validation recertification attendance renewal controls 均為 `[]`。
3. D3421-D3422 adjacent regression 通過 `10 passed, 3965 deselected in 59.49s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_certification_attendance_renewal_validation_lifecycle'`：`5 passed in 30.02s`。
- D3422 post-fix certification attendance renewal validation matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded validation recertification attendance renewal：`[]`；post-fix next residual `time to issue validation recertification attendance target 12 個`：`[12.0]`。
- D3421-D3422 adjacent regression：`10 passed, 3965 deselected in 59.49s`。

### 完成後維護 / D3421 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3420 後重新掃描 recertification certification attendance completion、certification renewal attendance validation、recertification certification validation、certification validation renewal attendance 與其他四個 variants，選擇 complete recertification certification attendance、complete validation certification renewal attendance、issue certification renewal attendance validation 及 attend recertification certification validation；以 post-fix `time to verify certification attendance renewal validation`、部分覆蓋的 `time to schedule validation certification renewal`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to complete recertification certification attendance`、`time to complete validation certification renewal attendance`、`time to issue certification renewal attendance validation` 與 `time to attend recertification certification validation` 是 recertification/certification validation KPI；其數值不應進入股票 target-price candidates。
2. fresh pre-fix residual candidate scan 對八組候選各測 120 cases；本輪選定四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；下一批三組各為 `100 / 120`，`time to schedule validation certification renewal` 為 `80 / 102`，因此保留部分覆蓋組的獨立邊界。

落地修改

1. 五個報告品質入口新增 certification recertification validation attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 certification recertification validation attendance roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 3965 deselected in 30.82s`；shared-pattern GREEN 通過 `5 passed in 30.44s`，沒有新增 consumer-specific cleanup。
2. D3421 post-fix certification recertification validation attendance matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded recertification certification validation controls 均為 `[]`。
3. D3420-D3421 adjacent regression 通過 `10 passed, 3960 deselected in 58.97s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_certification_recertification_validation_attendance_lifecycle'`：`5 passed in 30.44s`。
- D3421 post-fix certification recertification validation attendance matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded recertification certification validation：`[]`；post-fix next residual `time to verify certification attendance renewal validation target 12 個`：`[12.0]`。
- D3420-D3421 adjacent regression：`10 passed, 3960 deselected in 58.97s`。

### 完成後維護 / D3420 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3419 後重新掃描 recertification attendance validation issuance、certification validation renewal attendance、recertification certification validation、attendance validation recertification 與其他四個 variants，選擇 issue recertification attendance validation、attend certification validation renewal、renew recertification certification validation 及 verify attendance validation recertification；以 post-fix `time to complete recertification certification attendance`、部分覆蓋的 `time to schedule validation certification renewal`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue recertification attendance validation`、`time to attend certification validation renewal`、`time to renew recertification certification validation` 與 `time to verify attendance validation recertification` 是 recertification/certification validation KPI；其數值不應進入股票 target-price candidates。
2. fresh pre-fix residual candidate scan 對八組候選各測 120 cases；本輪選定四個完整缺口 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；下一批三組各為 `100 / 120`，`time to schedule validation certification renewal` 為 `80 / 102`，因此保留部分覆蓋組的獨立邊界。

落地修改

1. 五個報告品質入口新增 recertification certification validation attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 recertification certification validation attendance roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 3960 deselected in 29.19s`；shared-pattern GREEN 通過 `5 passed in 29.30s`，沒有新增 consumer-specific cleanup。
2. D3420 post-fix recertification certification validation attendance matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded recertification certification validation renewal controls 均為 `[]`。
3. D3419-D3420 adjacent regression 通過 `10 passed, 3955 deselected in 57.82s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_recertification_certification_validation_attendance_lifecycle'`：`5 passed in 29.30s`。
- D3420 post-fix recertification certification validation attendance matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded recertification certification validation renewal：`[]`；post-fix next residual `time to complete recertification certification attendance target 12 個`：`[12.0]`。
- D3419-D3420 adjacent regression：`10 passed, 3955 deselected in 57.82s`。

### 完成後維護 / D3419 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3418 後重新掃描 recertification validation attendance scheduling、certification renewal attendance、certification attendance recertification、validation renewal certification 與其他四個 variants，選擇 schedule recertification validation attendance、renew certification validation attendance、complete certification attendance recertification 及 verify validation renewal certification；以 post-fix `time to issue recertification attendance validation`、部分覆蓋的 `time to schedule validation certification renewal`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to schedule recertification validation attendance`、`time to renew certification validation attendance`、`time to complete certification attendance recertification` 與 `time to verify validation renewal certification` 是 recertification/certification validation KPI；其數值不應進入股票 target-price candidates。
2. fresh pre-fix residual candidate scan 對八組候選各測 120 cases；本輪選定四個 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. post-fix 重掃顯示本輪四組各為 `0 leaks / 0 valid-misses`；下一批三組各為 `100 / 120`，`time to schedule validation certification renewal` 為 `80 / 102`，因此保留部分覆蓋組的獨立邊界。

落地修改

1. 五個報告品質入口新增 recertification validation attendance scheduling lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 recertification validation attendance scheduling roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 3955 deselected in 29.30s`；shared-pattern GREEN 通過 `5 passed in 29.27s`，沒有新增 consumer-specific cleanup。
2. D3419 post-fix recertification validation attendance scheduling matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded certification attendance recertification completion controls 均為 `[]`。
3. D3418-D3419 adjacent regression 通過 `10 passed, 3950 deselected in 57.42s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_recertification_validation_attendance_scheduling_lifecycle'`：`5 passed in 29.27s`。
- D3419 post-fix recertification validation attendance scheduling matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded certification attendance recertification completion：`[]`；post-fix next residual `time to issue recertification attendance validation target 12 個`：`[12.0]`。
- D3418-D3419 adjacent regression：`10 passed, 3950 deselected in 57.42s`。

### 完成後維護 / D3418 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3417 後重新掃描 recertification validation、certification attendance validation、certification renewal validation、renewal validation attendance 與其他四個 variants，選擇 attend recertification validation、issue certification attendance validation、verify certification renewal validation 及 complete renewal validation attendance；以 `time to schedule recertification validation attendance`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to attend recertification validation`、`time to issue certification attendance validation`、`time to verify certification renewal validation` 與 `time to complete renewal validation attendance` 是 recertification/certification validation KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定四個 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. production 只追加四個 recertification/certification validation roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；financial `time to price` 與 recertification validation attendance variants 保持獨立。

落地修改

1. 五個報告品質入口新增 recertification validation certification attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 recertification validation certification attendance roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 3950 deselected in 28.23s`；shared-pattern GREEN 通過 `5 passed in 36.26s`，沒有新增 consumer-specific cleanup。
2. D3418 post-fix recertification validation certification attendance matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded `time to verify certification renewal validation` controls 均為 `[]`，residual `time to schedule recertification validation attendance target 12 個` 仍為 `[12.0]`。
3. D3417-D3418 adjacent regression 通過 `10 passed, 3945 deselected in 55.92s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_recertification_validation_attendance_lifecycle'`：`5 passed in 36.26s`。
- D3418 post-fix recertification validation certification attendance matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded certification renewal validation verification：`[]`；residual `time to schedule recertification validation attendance target 12 個`：`[12.0]`。
- D3417-D3418 adjacent regression：`10 passed, 3945 deselected in 55.92s`。

### 完成後維護 / D3417 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3416 後重新掃描 renewal certification attendance、attendance validation、validation recertification、attendance certification 與其他四個 variants，選擇 verify renewal certification attendance、renew certification attendance validation、complete validation recertification 及 schedule attendance certification；以 `time to attend recertification validation`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to verify renewal certification attendance`、`time to renew certification attendance validation`、`time to complete validation recertification` 與 `time to schedule attendance certification` 是 renewal certification/attendance validation KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定四個 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. production 只追加四個 renewal certification attendance/validation roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；financial `time to price` 與 recertification validation variants 保持獨立。

落地修改

1. 五個報告品質入口新增 renewal certification attendance validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 renewal certification attendance validation roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 3945 deselected in 35.94s`；shared-pattern GREEN 通過 `5 passed in 28.21s`，沒有新增 consumer-specific cleanup。
2. D3417 post-fix renewal certification attendance validation matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded `time to complete validation recertification` controls 均為 `[]`，residual `time to attend recertification validation target 12 個` 仍為 `[12.0]`。
3. D3416-D3417 adjacent regression 通過 `10 passed, 3940 deselected in 56.52s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_renewal_certification_attendance_validation_lifecycle'`：`5 passed in 28.21s`。
- D3417 post-fix renewal certification attendance validation matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded validation recertification completion：`[]`；residual `time to attend recertification validation target 12 個`：`[12.0]`。
- D3416-D3417 adjacent regression：`10 passed, 3940 deselected in 56.52s`。

### 完成後維護 / D3416 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3415 後重新掃描 certification renewal validation attendance、scheduling、completion、issuance 與其他四個 variants，選擇 attend certification renewal validation、schedule certification renewal validation、complete certification renewal validation 及 issue certification renewal validation；以 `time to verify renewal certification attendance`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to attend certification renewal validation`、`time to schedule certification renewal validation`、`time to complete certification renewal validation` 與 `time to issue certification renewal validation` 是 certification renewal validation KPI；其數值不應進入股票 target-price candidates。
2. fresh residual candidate scan 對八組候選各測 120 cases；本輪選定四個 roots，跨五入口聯集為 `480 cases / 400 leaks / 480 valid-misses`，不把不同入口對同一案例的命中重複加總。
3. production 只追加四個 certification renewal validation roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；financial `time to price` 與 renewal certification attendance variants 保持獨立。

落地修改

1. 五個報告品質入口新增 certification renewal validation attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 certification renewal validation roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 為 `5 failed, 3940 deselected in 28.26s`；shared-pattern GREEN 通過 `5 passed in 28.78s`，沒有新增 consumer-specific cleanup。
2. D3416 post-fix certification renewal validation matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded `time to issue certification renewal validation` controls 均為 `[]`，residual `time to verify renewal certification attendance target 12 個` 仍為 `[12.0]`。
3. D3415-D3416 adjacent regression 通過 `10 passed, 3935 deselected in 56.07s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_certification_renewal_validation_attendance_lifecycle'`：`5 passed in 28.78s`。
- D3416 post-fix certification renewal validation matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded certification renewal validation issuance：`[]`；residual `time to verify renewal certification attendance target 12 個`：`[12.0]`。
- D3415-D3416 adjacent regression：`10 passed, 3935 deselected in 56.07s`。

### 完成後維護 / D3415 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3414 後重新掃描 certification validation issuance、recertification certificate scheduling、recertification validation completion、certification renewal attendance verification 與其他 variants，選擇 issue certification validation、schedule recertification certificate、complete recertification validation 及 verify certification renewal attendance；以 `time to attend certification renewal validation`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue certification validation`、`time to schedule recertification certificate`、`time to complete recertification validation` 與 `time to verify certification renewal attendance` 是 certification validation/recertification certificate KPI；其數值不應進入股票 target-price candidates。
2. fresh candidate union scan 為 `480 cases / 400 leaks / 480 valid-misses`；這是五入口聯集口徑，不重複加總同一案例在不同入口的命中。
3. production 只追加四個 certification validation/recertification certificate roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；financial `time to price` 與 certification renewal validation variants 保持獨立。

落地修改

1. 五個報告品質入口新增 certification validation recertification certificate attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 certification validation recertification certificate attendance lifecycle roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 28.00s`，沒有新增 consumer-specific cleanup。
2. D3415 post-fix certification validation recertification certificate attendance matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded `time to verify certification renewal attendance` controls 均為 `[]`，residual `time to attend certification renewal validation target 12 個` 仍為 `[12.0]`。
3. D3414-D3415 adjacent regression 通過 `10 passed, 3930 deselected in 54.71s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_certification_validation_recertification_certificate_attendance_lifecycle'`：`5 passed in 28.00s`。
- D3415 post-fix certification validation recertification certificate attendance matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded certification renewal attendance verification：`[]`；residual `time to attend certification renewal validation target 12 個`：`[12.0]`。
- D3414-D3415 adjacent regression：`10 passed, 3930 deselected in 54.71s`。

### 完成後維護 / D3414 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3413 後重新掃描 certification validation attendance、recertification validation scheduling、recertification attendance completion、certification validation renewal 與其他 variants，選擇 attend certification validation、schedule recertification validation、complete recertification attendance 及 renew certification validation；以 `time to issue certification validation`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to attend certification validation`、`time to schedule recertification validation`、`time to complete recertification attendance` 與 `time to renew certification validation` 是 certification validation/recertification attendance KPI；其數值不應進入股票 target-price candidates。
2. fresh candidate union scan 為 `480 cases / 400 leaks / 480 valid-misses`；這是五入口聯集口徑，不重複加總同一案例在不同入口的命中。
3. production 只追加四個 certification validation/recertification attendance roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；financial `time to price` 與 certification validation issuance variants 保持獨立。

落地修改

1. 五個報告品質入口新增 certification validation recertification attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 certification validation recertification attendance lifecycle roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 37.98s`，沒有新增 consumer-specific cleanup。
2. D3414 post-fix certification validation recertification attendance matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded `time to renew certification validation` controls 均為 `[]`，residual `time to issue certification validation target 12 個` 仍為 `[12.0]`。
3. D3413-D3414 adjacent regression 通過 `10 passed, 3925 deselected in 54.10s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_certification_validation_recertification_attendance_lifecycle'`：`5 passed in 37.98s`。
- D3414 post-fix certification validation recertification attendance matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded certification validation renewal：`[]`；residual `time to issue certification validation target 12 個`：`[12.0]`。
- D3413-D3414 adjacent regression：`10 passed, 3925 deselected in 54.10s`。

### 完成後維護 / D3413 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3412 後重新掃描 recertification renewal issuance、certification renewal scheduling、certification renewal completion、recertification certificate verification 與其他 variants，選擇 issue recertification renewal、schedule certification renewal、complete certification renewal 及 verify recertification certificate；以 `time to attend certification validation`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue recertification renewal`、`time to schedule certification renewal`、`time to complete certification renewal` 與 `time to verify recertification certificate` 是 recertification renewal/certificate verification KPI；其數值不應進入股票 target-price candidates。
2. fresh candidate union scan 為 `480 cases / 340 leaks / 426 valid-misses`；這是五入口聯集口徑，不重複加總同一案例在不同入口的命中。
3. production 只追加四個 recertification renewal/certificate verification roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；financial `time to price` 與 certification attendance validation variants 保持獨立。

落地修改

1. 五個報告品質入口新增 recertification renewal certificate validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 recertification renewal certificate validation lifecycle roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 27.14s`，沒有新增 consumer-specific cleanup。
2. D3413 post-fix recertification renewal certificate validation matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded `time to verify recertification certificate` controls 均為 `[]`，residual `time to attend certification validation target 12 個` 仍為 `[12.0]`。
3. D3412-D3413 adjacent regression 通過 `10 passed, 3920 deselected in 62.01s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_recertification_renewal_certificate_validation_lifecycle'`：`5 passed in 27.14s`。
- D3413 post-fix recertification renewal certificate validation matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded recertification certificate verification：`[]`；residual `time to attend certification validation target 12 個`：`[12.0]`。
- D3412-D3413 adjacent regression：`10 passed, 3920 deselected in 62.01s`。

### 完成後維護 / D3412 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3411 後重新掃描 recertification certificate renewal、certification validation scheduling、renewal certification attendance、certification validation completion 與其他 variants，選擇 renew recertification certificate、schedule certification validation、attend renewal certification 及 complete certification validation；以 `time to issue recertification renewal forecast 12 個`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to renew recertification certificate`、`time to schedule certification validation`、`time to attend renewal certification` 與 `time to complete certification validation` 是 certificate-renewal validation/attendance KPI；其數值不應進入股票 target-price candidates。
2. fresh candidate union scan 為 `480 cases / 400 leaks / 480 valid-misses`；這是五入口聯集口徑，不重複加總同一案例在不同入口的命中。
3. production 只追加四個 certificate renewal/validation/attendance roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；financial `time to price` 與 recertification renewal issuance variants 保持獨立。

落地修改

1. 五個報告品質入口新增 certificate renewal validation attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 certificate renewal validation attendance lifecycle roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 27.22s`，沒有新增 consumer-specific cleanup。
2. D3412 post-fix certificate renewal validation attendance matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded `time to complete certification validation` controls 均為 `[]`，residual `time to issue recertification renewal forecast 12 個` 仍為 `[12.0]`。
3. D3411-D3412 adjacent regression 通過 `10 passed, 3915 deselected in 53.19s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_certificate_renewal_validation_attendance_lifecycle'`：`5 passed in 27.22s`。
- D3412 post-fix certificate renewal validation attendance matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded certification validation completion：`[]`；residual `time to issue recertification renewal forecast 12 個`：`[12.0]`。
- D3411-D3412 adjacent regression：`10 passed, 3915 deselected in 53.19s`。

### 完成後維護 / D3411 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3410 後重新掃描 recertification renewal、recertification renewal completion、renewal certification scheduling、certification attendance validation 與其他 variants，選擇 renew recertification、complete recertification renewal、schedule renewal certification 及 validate certification attendance；以 `time to renew recertification certificate`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to renew recertification`、`time to complete recertification renewal`、`time to schedule renewal certification` 與 `time to validate certification attendance` 是 recertification-renewal lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh candidate union scan 為 `480 cases / 380 leaks / 462 valid-misses`；這是五入口聯集口徑，不重複加總同一案例在不同入口的命中。
3. production 只追加四個 recertification renewal/completion/scheduling/validation roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；financial `time to price` 與 certificate renewal variants 保持獨立。

落地修改

1. 五個報告品質入口新增 recertification renewal certification attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 recertification renewal certification attendance lifecycle roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 26.84s`，沒有新增 consumer-specific cleanup。
2. D3411 post-fix recertification renewal certification attendance matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded `time to validate certification attendance` controls 均為 `[]`，residual `time to renew recertification certificate target 12 個` 仍為 `[12.0]`。
3. D3410-D3411 adjacent regression 通過 `10 passed, 3910 deselected in 53.23s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_recertification_renewal_certification_attendance_lifecycle'`：`5 passed in 26.84s`。
- D3411 post-fix recertification renewal certification attendance matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded certification attendance validation：`[]`；residual `time to renew recertification certificate target 12 個`：`[12.0]`。
- D3410-D3411 adjacent regression：`10 passed, 3910 deselected in 53.23s`。

### 完成後維護 / D3410 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3409 後重新掃描 certification renewal attendance scheduling、recertification renewal verification、certificate renewal issuance、recertification renewal attendance 與其他 variants，選擇 schedule certification renewal attendance、verify recertification renewal、issue certificate renewal 及 attend recertification renewal；以 `time to renew recertification`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to schedule certification renewal attendance`、`time to verify recertification renewal`、`time to issue certificate renewal` 與 `time to attend recertification renewal` 是 certification-renewal lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh candidate union scan 為 `480 cases / 360 leaks / 444 valid-misses`；這是五入口聯集口徑，不重複加總同一案例在不同入口的命中。
3. production 只追加四個 certification-renewal attendance/verification/issuance roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；financial `time to price` 與 recertification renewal/completion variants 保持獨立。

落地修改

1. 五個報告品質入口新增 certification-renewal attendance verification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 certification-renewal attendance verification lifecycle roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 27.70s`，沒有新增 consumer-specific cleanup。
2. D3410 post-fix certification-renewal attendance verification matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded `time to attend recertification renewal` controls 均為 `[]`，residual `time to renew recertification target 12 個` 仍為 `[12.0]`。
3. D3409-D3410 adjacent regression 通過 `10 passed, 3905 deselected in 53.68s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_certification_renewal_attendance_verification_lifecycle'`：`5 passed in 27.70s`。
- D3410 post-fix certification-renewal attendance verification matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded recertification renewal attendance：`[]`；residual `time to renew recertification target 12 個`：`[12.0]`。
- D3409-D3410 adjacent regression：`10 passed, 3905 deselected in 53.68s`。

### 完成後維護 / D3409 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3408 後重新掃描 recertification attendance scheduling、recertification validation、certification attendance renewal、renewal certification completion 與其他 variants，選擇 schedule recertification attendance、validate recertification、renew certification attendance 及 complete renewal certification；以 `time to schedule certification renewal attendance`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to schedule recertification attendance`、`time to validate recertification`、`time to renew certification attendance` 與 `time to complete renewal certification` 是 recertification attendance/validation lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh candidate union scan 為 `480 cases / 400 leaks / 480 valid-misses`；這是五入口聯集口徑，不重複加總同一案例在不同入口的命中。
3. production 只追加四個 recertification attendance/validation/renewal roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；financial `time to price` 與 certification renewal attendance scheduling 保持獨立。

落地修改

1. 五個報告品質入口新增 recertification attendance validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 recertification attendance validation lifecycle roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 27.15s`，沒有新增 consumer-specific cleanup。
2. D3409 post-fix recertification attendance validation matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded `time to complete renewal certification` controls 均為 `[]`，residual `time to schedule certification renewal attendance target 12 個` 仍為 `[12.0]`。
3. D3408-D3409 adjacent regression 通過 `10 passed, 3900 deselected in 53.65s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_recertification_attendance_validation_lifecycle'`：`5 passed in 27.15s`。
- D3409 post-fix recertification attendance validation matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded renewal certification completion：`[]`；residual `time to schedule certification renewal attendance target 12 個`：`[12.0]`。
- D3408-D3409 adjacent regression：`10 passed, 3900 deselected in 53.65s`。

### 完成後維護 / D3408 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3407 後重新掃描 recertification certificate issuance、certification renewal attendance、renewal certification verification、certification renewal attendance completion 與其他反向語序 variants，選擇 issue recertification certificate、attend certification renewal、verify renewal certification 及 complete certification renewal attendance；以 `time to schedule recertification attendance`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue recertification certificate`、`time to attend certification renewal`、`time to verify renewal certification` 與 `time to complete certification renewal attendance` 是 recertification-renewal lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh candidate union scan 為 `480 cases / 380 leaks / 462 valid-misses`；這是五入口聯集口徑，不重複加總同一案例在不同入口的命中。
3. production 只追加四個 recertification-renewal issuance/attendance/verification roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；financial `time to price` 與其他 attendance scheduling/validation variants 保持獨立。

落地修改

1. 五個報告品質入口新增 recertification-renewal attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 recertification-renewal attendance lifecycle roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 27.24s`，沒有新增 consumer-specific cleanup。
2. D3408 post-fix recertification-renewal attendance matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded `time to complete certification renewal attendance` controls 均為 `[]`，residual `time to schedule recertification attendance target 12 個` 仍為 `[12.0]`。
3. D3407-D3408 adjacent regression 通過 `10 passed, 3895 deselected in 53.51s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_recertification_renewal_attendance_lifecycle'`：`5 passed in 27.24s`。
- D3408 post-fix recertification-renewal attendance matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded certification renewal attendance：`[]`；residual `time to schedule recertification attendance target 12 個`：`[12.0]`。
- D3407-D3408 adjacent regression：`10 passed, 3895 deselected in 53.51s`。

### 完成後維護 / D3407 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3406 後重新掃描 certification-renewal issuance、recertification training、certification attendance scheduling、renewal validation 與其他 certification variants，選擇 issue certification renewal、complete recertification training、schedule certification attendance 及 validate certification renewal；以 `time to issue recertification certificate`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to issue certification renewal`、`time to complete recertification training`、`time to schedule certification attendance` 與 `time to validate certification renewal` 是 certification-renewal lifecycle KPI；其數值不應進入股票 target-price candidates。
2. fresh candidate union scan 為 `480 cases / 360 leaks / 444 valid-misses`；這是五入口聯集口徑，不重複加總同一案例在不同入口的命中。
3. production 只追加四個 certification-renewal issuance/training/attendance/validation roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；financial `time to price` 與其他 certification variants 保持獨立。

落地修改

1. 五個報告品質入口新增 certification-renewal issuance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 certification-renewal issuance lifecycle roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 27.09s`，沒有新增 consumer-specific cleanup。
2. D3407 post-fix certification-renewal issuance matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded `time to validate certification renewal` controls 均為 `[]`，residual `time to issue recertification certificate target 12 個` 仍為 `[12.0]`。
3. D3406-D3407 adjacent regression 通過 `10 passed, 3890 deselected in 53.05s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_certification_renewal_issuance_lifecycle'`：`5 passed in 27.09s`。
- D3407 post-fix certification-renewal issuance matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded renewal validation：`[]`；residual `time to issue recertification certificate target 12 個`：`[12.0]`。
- D3406-D3407 adjacent regression：`10 passed, 3890 deselected in 53.05s`。

### 完成後維護 / D3406 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3405 後重新掃描 certification-training attendance、certificate recertification verification、certificate renewal completion、certification-training renewal 與後續 variants，選擇 attend certification training、verify certificate recertification、complete certificate renewal 及 renew certification training；以 `time to issue certification renewal`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to attend certification training`、`time to verify certificate recertification`、`time to complete certificate renewal` 與 `time to renew certification training` 是 certification-renewal attendance/verification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. pre-fix matrix 為 `480 cases / 2000 leaks / 792 valid-misses`；四個 roots 各有 500 leaks。
3. production 只追加四個 certification-renewal lifecycle roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；financial `time to price` 與後續 certification issuance/attendance variants 保持獨立。

落地修改

1. 五個報告品質入口新增 certification-renewal attendance lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 certification-renewal lifecycle roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 27.87s`，沒有新增 consumer-specific cleanup。
2. D3406 post-fix certification-renewal attendance matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete course` 與 newly guarded `time to verify certificate recertification` controls 均為 `[]`，residual `time to issue certification renewal forecast 12 個` 仍為 `[12.0]`。
3. D3405-D3406 adjacent regression 通過 `10 passed, 3885 deselected in 54.89s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_certification_renewal_attendance_lifecycle'`：`5 passed in 27.87s`。
- D3406 post-fix certification-renewal attendance matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course：`[]`；newly guarded certificate recertification：`[]`；residual `time to issue certification renewal forecast 12 個`：`[12.0]`。
- D3405-D3406 adjacent regression：`10 passed, 3885 deselected in 54.89s`。

### 完成後維護 / D3405 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3404 後重新掃描 certification-training scheduling、training certificate review attendance、certificate renewal verification 與 certificate-training scheduling variants，選擇 schedule certification training、attend training certificate review、verify certificate renewal 及 schedule certificate training；以 `time to attend certification training`、既有 training certification review control、financial time-to 與 explicit target price 作為比較組。另 probe 確認 `time to complete training certification review` 已由 D3404 覆蓋。

核心判斷

1. `time to schedule certification training`、`time to attend training certificate review`、`time to verify certificate renewal` 與 `time to schedule certificate training` 是 certification-training word-order variant KPI；其數值不應進入股票 target-price candidates。
2. pre-fix matrix 為 `480 cases / 2000 leaks / 792 valid-misses`；四個 roots 各有 500 leaks。
3. production 只追加四個 word-order variant roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；已被 D3404 覆蓋的 training certification review 不重複追加，financial `time to price` 保持獨立。

落地修改

1. 五個報告品質入口新增 training-certificate word-order lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 word-order variant roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 26.98s`，沒有新增 consumer-specific cleanup。
2. D3405 post-fix training-certificate word-order matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price` 與 existing `time to complete training certification review` control 均為 `[]`，residual `time to attend certification training` 仍為 `[12.0]`。
3. D3404-D3405 adjacent regression 通過 `10 passed, 3880 deselected in 54.51s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_training_certificate_word_order_lifecycle'`：`5 passed in 26.98s`。
- D3405 post-fix training-certificate word-order matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing training certification review：`[]`；residual `time to attend certification training`：`[12.0]`。
- D3404-D3405 adjacent regression：`10 passed, 3880 deselected in 54.51s`。

### 完成後維護 / D3404 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3403 後重新掃描 training certification review/scheduling、certificate verification attendance 與 certification training completion controls，選擇 complete review、schedule certification、attend verification 及 complete certification training；以 `time to schedule certification training`、既有 training certificate review control、financial time-to 與 explicit target price 作為比較組。另 probe 確認 `time to verify certification renewal` 已由既有泛化 verify guard 覆蓋。

核心判斷

1. `time to complete training certification review`、`time to schedule training certification`、`time to attend certificate verification` 與 `time to complete certification training` 是 training certification variant KPI；其數值不應進入股票 target-price candidates。
2. pre-fix matrix 為 `480 cases / 2000 leaks / 792 valid-misses`；四個 roots 各有 500 leaks。
3. production 只追加四個 training certification variant roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；已被泛化 verify guard 覆蓋的 certification-renewal verification 不重複追加，financial `time to price` 保持獨立。

落地修改

1. 五個報告品質入口新增 training-certification variant lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 training-certification variant roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 28.01s`，沒有新增 consumer-specific cleanup。
2. D3404 post-fix training-certification variant matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price`、existing `time to complete training certificate review` 與 generic `time to verify certification renewal` controls 均為 `[]`，residual `time to schedule certification training` 仍為 `[12.0]`。
3. D3403-D3404 adjacent regression 通過 `10 passed, 3875 deselected in 54.23s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_training_certification_variant_lifecycle'`：`5 passed in 28.01s`。
- D3404 post-fix training-certification variant matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing training certificate review：`[]`；generic verify control：`[]`；residual `time to schedule certification training`：`[12.0]`。
- D3403-D3404 adjacent regression：`10 passed, 3875 deselected in 54.23s`。

### 完成後維護 / D3403 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3402 後重新掃描 training certificate review、certificate validation scheduling、training certification attendance 與 recertification verification controls，選擇 complete review、schedule validation、attend certification 及 verify recertification；以 `time to complete training certification review`、既有 training certificate review control、financial time-to 與 explicit target price 作為比較組。另 probe 確認 `time to verify certification renewal` 已由既有泛化 verify guard 覆蓋。

核心判斷

1. `time to complete training certificate review`、`time to schedule certificate validation`、`time to attend training certification` 與 `time to verify recertification` 是 training-specific credential lifecycle KPI；其數值不應進入股票 target-price candidates。
2. pre-fix matrix 為 `480 cases / 2000 leaks / 792 valid-misses`；四個 roots 各有 500 leaks。
3. production 只追加四個 training-specific review/validation/attendance/verification roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；已被既有泛化 verify 規則覆蓋的 certification-renewal verification 不重複追加，financial `time to price` 保持獨立。

落地修改

1. 五個報告品質入口新增 training-certificate verification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 training-certificate verification lifecycle roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 27.33s`，沒有新增 consumer-specific cleanup。
2. D3403 post-fix training-certificate verification matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price` 與 existing `time to complete training certificate review` control 均為 `[]`，residual `time to complete training certification review` 仍為 `[12.0]`。
3. D3402-D3403 adjacent regression 通過 `10 passed, 3870 deselected in 53.88s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_training_certificate_verification_lifecycle'`：`5 passed in 27.33s`。
- D3403 post-fix training-certificate verification matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing `time to complete training certificate review`：`[]`；residual `time to complete training certification review`：`[12.0]`。
- `time to verify certification renewal` existing generic verify control：五入口皆為 `[]`。
- D3402-D3403 adjacent regression：`10 passed, 3870 deselected in 53.88s`。

### 完成後維護 / D3402 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3401 後重新掃描 training certificate review、training certificate renewal scheduling、certification assessment attendance 與 training certificate verification controls，選擇 complete review、schedule renewal、attend assessment 及 verify training certificate；以 `time to complete training certificate review`、既有 certification review control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to complete certification review`、`time to schedule training certificate renewal`、`time to attend certification assessment` 與 `time to verify training certificate` 是 training-specific credential lifecycle KPI；其數值不應進入股票 target-price candidates。
2. pre-fix matrix 為 `480 cases / 2000 leaks / 792 valid-misses`；四個 roots 各有 500 leaks。
3. production 只追加四個 training-specific review/renewal/assessment/verification roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；training certificate review/verification 與 financial `time to price` 保持獨立。

落地修改

1. 五個報告品質入口新增 training-credential review lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 training-specific review/renewal/assessment/verification roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 27.15s`，沒有新增 consumer-specific cleanup。
2. D3402 post-fix training-credential review matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price` 與 existing `time to complete certification review` control 均為 `[]`，residual `time to complete training certificate review` 仍為 `[12.0]`。
3. D3401-D3402 adjacent regression 通過 `10 passed, 3865 deselected in 52.78s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_training_credential_review_validation_lifecycle'`：`5 passed in 27.15s`。
- D3402 post-fix training-credential review matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing `time to complete certification review`：`[]`；residual `time to complete training certificate review`：`[12.0]`。
- D3401-D3402 adjacent regression：`10 passed, 3865 deselected in 52.78s`。

### 完成後維護 / D3401 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3400 後重新掃描 certification assessment、recertification scheduling、certificate renewal attendance 與 certificate verification controls，選擇 complete assessment、schedule recertification、attend renewal 及 verify certificate；以 `time to complete certification review`、既有 assessment control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to complete certification assessment`、`time to schedule recertification`、`time to attend certificate renewal` 與 `time to verify certificate` 是 certification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. pre-fix matrix 為 `480 cases / 2000 leaks / 792 valid-misses`；四個 roots 各有 500 leaks。
3. production 只追加四個 assessment/scheduling/renewal/verification roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；certification review、training certificate renewal scheduling、certification assessment attendance、training certificate verification 與 financial `time to price` 保持獨立。

落地修改

1. 五個報告品質入口新增 certification-review lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 certification-review lifecycle roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 26.10s`，沒有新增 consumer-specific cleanup。
2. D3401 post-fix certification-review matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price` 與 existing `time to complete certification assessment` control 均為 `[]`，residual `time to complete certification review` 仍為 `[12.0]`。
3. D3400-D3401 adjacent regression 通過 `10 passed, 3860 deselected in 51.42s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_training_certification_review_lifecycle'`：`5 passed in 26.10s`。
- D3401 post-fix certification-review matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing `time to complete certification assessment`：`[]`；residual `time to complete certification review`：`[12.0]`。
- D3400-D3401 adjacent regression：`10 passed, 3860 deselected in 51.42s`。

### 完成後維護 / D3400 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3399 後重新掃描 certification exam、certificate renewal scheduling、recertification attendance 與 training certificate validation controls，選擇 complete exam、schedule renewal、attend recertification 及 validate training certificate；以 `time to complete certification assessment`、既有 credential completion control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to complete certification exam`、`time to schedule certificate renewal`、`time to attend recertification` 與 `time to validate training certificate` 是 certification lifecycle KPI；其數值不應進入股票 target-price candidates。
2. pre-fix matrix 為 `480 cases / 2000 leaks / 792 valid-misses`；四個 roots 各有 500 leaks。
3. production 只追加四個 certification assessment/renewal/validation roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；certification assessment、recertification scheduling、certificate renewal attendance、certificate verification 與 financial `time to price` 保持獨立。

落地修改

1. 五個報告品質入口新增 certification-assessment lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 certification-assessment/renewal/validation roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 26.76s`，沒有新增 consumer-specific cleanup。
2. D3400 post-fix certification-assessment matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price` 與 existing `time to complete recertification` control 均為 `[]`，residual `time to complete certification assessment` 仍為 `[12.0]`。
3. D3399-D3400 adjacent regression 通過 `10 passed, 3855 deselected in 53.38s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_training_certification_assessment_lifecycle'`：`5 passed in 26.76s`。
- D3400 post-fix certification-assessment matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing `time to complete recertification`：`[]`；residual `time to complete certification assessment`：`[12.0]`。
- D3399-D3400 adjacent regression：`10 passed, 3855 deselected in 53.38s`。

### 完成後維護 / D3399 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3398 後重新掃描 recertification completion、renewal certificate、training certificate renewal 與 certification pass controls，選擇 complete recertification、issue/renew certificate 及 pass certification；以 `time to complete certification exam`、既有 attendance control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to complete recertification`、`time to issue renewal certificate`、`time to renew training certificate` 與 `time to pass certification` 是 credential completion/renewal KPI；其數值不應進入股票 target-price candidates。
2. pre-fix matrix 為 `480 cases / 2000 leaks / 792 valid-misses`；四個 roots 各有 500 leaks。
3. production 只追加四個 credential completion/renewal/pass roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；certification exam、renewal scheduling、recertification attendance、training certificate validation 與 financial `time to price` 保持獨立。

落地修改

1. 五個報告品質入口新增 credential completion lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 credential completion/renewal/pass roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 26.10s`，沒有新增 consumer-specific cleanup。
2. D3399 post-fix credential-completion matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price` 與 existing `time to attend certification` control 均為 `[]`，residual `time to complete certification exam` 仍為 `[12.0]`。
3. D3398-D3399 adjacent regression 通過 `10 passed, 3850 deselected in 50.47s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_training_credential_completion_lifecycle'`：`5 passed in 26.10s`。
- D3399 post-fix credential-completion matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing `time to attend certification`：`[]`；residual `time to complete certification exam`：`[12.0]`。
- D3398-D3399 adjacent regression：`10 passed, 3850 deselected in 50.47s`。

### 完成後維護 / D3398 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3397 後重新掃描 recertification、certificate validation、certification scheduling/attendance 與既有 renewal controls，選擇 recertify/validate training credential 及 schedule/attend certification；以 `time to complete recertification`、既有 certificate-renewal control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to recertify training`、`time to validate certificate`、`time to schedule certification` 與 `time to attend certification` 是 credential lifecycle KPI；其數值不應進入股票 target-price candidates。
2. pre-fix matrix 為 `480 cases / 2000 leaks / 792 valid-misses`；四個 roots 各有 500 leaks。
3. production 只追加四個 recertification/validation/attendance roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；certificate renewal、complete recertification、pass certification 與 financial `time to price` 保持獨立。

落地修改

1. 五個報告品質入口新增 recertification/validation lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 recertification/validation/attendance roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 25.56s`，沒有新增 consumer-specific cleanup。
2. D3398 post-fix recertification matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price` 與 existing `time to renew certification` control 均為 `[]`，residual `time to complete recertification` 仍為 `[12.0]`。
3. D3397-D3398 adjacent regression 通過 `10 passed, 3845 deselected in 50.69s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_training_certification_attendance_lifecycle'`：`5 passed in 25.56s`。
- D3398 post-fix recertification matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing `time to renew certification`：`[]`；residual `time to complete recertification`：`[12.0]`。
- D3397-D3398 adjacent regression：`10 passed, 3845 deselected in 50.69s`。

### 完成後維護 / D3397 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3396 後重新掃描 certificate renewal、training-specific certificate 與 recertification/validation controls，選擇 renew certification、complete/issue/renew training certificate；以 `time to validate certificate`、既有 credential control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to renew certification`、`time to complete training certification`、`time to issue training certificate` 與 `time to renew training certification` 是 credential 維護流程 KPI；其數值不應進入股票 target-price candidates。
2. pre-fix matrix 為 `480 cases / 2000 leaks / 792 valid-misses`；四個 roots 各有 500 leaks。
3. production 只追加四個 certificate-renewal/training-specific roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；recertify/validate/schedule/attend certification 與 financial `time to price` 保持獨立。

落地修改

1. 五個報告品質入口新增 certificate-renewal lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 certificate-renewal/training-specific roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 26.95s`，沒有新增 consumer-specific cleanup。
2. D3397 post-fix certificate-renewal matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price` 與 existing `time to issue certificate` control 均為 `[]`，residual `time to validate certificate` 仍為 `[12.0]`。
3. D3396-D3397 adjacent regression 通過 `10 passed, 3840 deselected in 50.26s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_training_certificate_renewal_lifecycle'`：`5 passed in 26.95s`。
- D3397 post-fix certificate-renewal matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing `time to issue certificate`：`[]`；residual `time to validate certificate`：`[12.0]`。
- D3396-D3397 adjacent regression：`10 passed, 3840 deselected in 50.26s`。

### 完成後維護 / D3396 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3395 後重新掃描 training credential、certificate issuance/renewal 與既有 training-certification controls，選擇 graduate/pass training、complete certification 與 issue certificate；以 `time to renew certification`、既有 training certification control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to graduate/pass training`、`time to complete certification` 與 `time to issue certificate` 是訓練 credential 流程 KPI；其數值不應進入股票 target-price candidates。
2. pre-fix matrix 為 `480 cases / 2000 leaks / 792 valid-misses`；四個 roots 各有 500 leaks。
3. production 只追加四個 training-credential roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；`time to renew certification`、training certificate 變體與 financial `time to price` 保持獨立。

落地修改

1. 五個報告品質入口新增 training-credential lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 training-credential roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 24.81s`，沒有新增 consumer-specific cleanup。
2. D3396 post-fix training-credential matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price` 與 existing `time to certify training` control 均為 `[]`，residual `time to renew certification` 仍為 `[12.0]`。
3. D3395-D3396 adjacent regression 通過 `10 passed, 3835 deselected in 48.92s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_training_credential_lifecycle'`：`5 passed in 24.81s`。
- D3396 post-fix training-credential matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing `time to certify training`：`[]`；residual `time to renew certification`：`[12.0]`。
- D3395-D3396 adjacent regression：`10 passed, 3835 deselected in 48.92s`。

### 完成後維護 / D3395 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3394 後重新掃描 training certification/completion、training session 與既有 course/training controls，選擇 certify/finish training 與 training session；以 `time to graduate training`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to certify/finish training` 與 `time to certify/finish training session` 是訓練認證及完成流程 KPI；其數值不應進入股票 target-price candidates。
2. pre-fix matrix 為 `480 cases / 1440 leaks / 780 valid-misses`；training roots 各 400 leaks、training-session roots 各 320 leaks，valid-miss 分布為 parser 192、calibration 120、credibility 12、structured output 120、detector 336。
3. production 只追加四個 training-certification/completion roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；`time to graduate/pass training`、certificate issuance/renewal 與 financial `time to price` 保持獨立。

落地修改

1. 五個報告品質入口新增 training-certification lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 training-certification/completion roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 25.45s`，沒有新增 consumer-specific cleanup。
2. D3395 post-fix training-certification matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price` 與 existing course control 均為 `[]`，residual `time to graduate training` 仍為 `[12.0]`。
3. `time_to_` full selector 通過 `216 passed, 3624 deselected in 2323.87s`，涵蓋本輪與既有 time-to guard。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_training_certification_lifecycle'`：`5 passed in 25.45s`。
- D3395 post-fix training-certification matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing course control：`[]`；residual `time to graduate training`：`[12.0]`。
- `-k 'time_to_'` full selector：`216 passed, 3624 deselected in 2323.87s`。
- completion gate：import boundary `503 passed in 10.06s`；HCS/文件契約 `135 passed in 3.23s`；`py_compile` exit 0；`git diff --check` exit 0；trailing-whitespace 無命中；runtime doctor exit 0，canonical operational DB 為 `backend/cache/operational.sqlite3`、report index 為 `backend/cache/stock_agent_cache.sqlite3`；parser/detector 行數維持 `349/189`。

### 完成後維護 / D3394 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3393 後重新掃描 training session、training certification 與既有 training-event/course controls，選擇 schedule/deliver/enroll/start training session；以 `time to certify training`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to schedule/deliver/enroll/start training session` 是訓練場次流程 KPI；其數值不應進入股票 target-price candidates。
2. pre-fix matrix 為 `480 cases / 1600 leaks / 768 valid-misses`；每個入口各有 320 leaks，valid-miss 分布為 parser 192、calibration 120、credibility 24、structured output 120、detector 312。
3. production 只追加四個 training-session roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；`time to certify training` 保持 residual control，financial `time to price` 維持獨立。

落地修改

1. 五個報告品質入口新增 training-session lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 training-session roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 26.03s`，沒有新增 consumer-specific cleanup。
2. D3394 post-fix training-session matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price` 與 existing course control 均為 `[]`，residual `time to certify training` 仍為 `[12.0]`。
3. D3376-D3394 完整相鄰 regression 為 `95 passed, 3740 deselected in 596.84s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_training_session_lifecycle'`：`5 passed in 26.03s`。
- D3394 post-fix training-session matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；residual `time to certify training`：`[12.0]`。
- D3376-D3394 adjacent regression：`95 passed, 3740 deselected in 596.84s`。

### 完成後維護 / D3393 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3392 後重新掃描 training event、training session 與既有 learning/course controls，選擇 launch/attend/complete/evaluate training event；以 `time to certify training`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to launch/attend training` 與 `time to complete/evaluate training event` 是訓練活動 KPI；其數值不應進入股票 target-price candidates。
2. pre-fix matrix 為 `480 cases / 2000 leaks / 792 valid-misses`；每個入口各有 400 leaks，valid-miss 分布為 parser 192、calibration 120、credibility 0、structured output 120、detector 360。
3. production 只追加四個 training-event roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；`time to certify training` 保持 residual control，financial `time to price` 維持獨立。

落地修改

1. 五個報告品質入口新增 training-event lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 training-event roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 25.21s`，沒有新增 consumer-specific cleanup。
2. D3393 post-fix training-event matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price` 與 existing course control 均為 `[]`，residual `time to certify training` 仍為 `[12.0]`。
3. D3376-D3393 完整相鄰 regression 為 `90 passed, 3740 deselected in 570.51s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_training_event_lifecycle'`：`5 passed in 25.21s`。
- D3393 post-fix training-event matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；residual `time to certify training`：`[12.0]`。
- D3376-D3393 adjacent regression：`90 passed, 3740 deselected in 570.51s`。

### 完成後維護 / D3392 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3391 後重新掃描 learning-module lifecycle、training event 與既有 training/course controls，選擇 enroll/start/complete/evaluate learning module；以 `time to launch training`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to enroll/start/complete/evaluate learning module` 是學習模組流程 KPI；其數值不應進入股票 target-price candidates。
2. pre-fix matrix 為 `480 cases / 1600 leaks / 768 valid-misses`；每個入口各有 320 leaks，valid-miss 分布為 parser 192、calibration 120、credibility 24、structured output 120、detector 312。
3. production 只追加四個 learning-module roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；`time to launch training` 保持 residual control，financial `time to price` 維持獨立。

落地修改

1. 五個報告品質入口新增 learning-module lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 learning-module roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 25.90s`，沒有新增 consumer-specific cleanup。
2. D3392 post-fix learning-module matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price` 與 existing course control 均為 `[]`，residual `time to launch training` 仍為 `[12.0]`。
3. D3376-D3392 完整相鄰 regression 為 `85 passed, 3740 deselected in 545.46s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_learning_module_lifecycle'`：`5 passed in 25.90s`。
- D3392 post-fix learning-module matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；residual `time to launch training`：`[12.0]`。
- D3376-D3392 adjacent regression：`85 passed, 3740 deselected in 545.46s`。

### 完成後維護 / D3391 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3390 後重新掃描 training enrollment/program、course module、learning module 與 training-event candidates，收斂主流程的 enroll/start/complete/evaluate roots；以 `time to launch training`、既有 course control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to enroll training`、`time to start training program`、`time to complete/evaluate course module` 是訓練與課程流程 KPI；其數值不應進入股票 target-price candidates。
2. pre-fix matrix 為 `480 cases / 2000 leaks / 792 valid-misses`；每個入口各有 400 leaks，valid-miss 分布為 parser 192、calibration 120、credibility 0、structured output 120、detector 360。
3. production 只追加四個 training/course-module roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；`time to launch training` 保持 residual control，financial `time to price` 維持獨立。

落地修改

1. 五個報告品質入口新增 training-course lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 training/course-module roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 25.59s`，沒有新增 consumer-specific cleanup。
2. D3391 post-fix training-course matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price` 與 existing course control 均為 `[]`，residual `time to launch training` 仍為 `[12.0]`。
3. D3376-D3391 完整相鄰 regression 為 `80 passed, 3740 deselected in 517.39s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_training_course_lifecycle'`：`5 passed in 25.59s`。
- D3391 post-fix training-course matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；residual `time to launch training`：`[12.0]`。
- D3376-D3391 adjacent regression：`80 passed, 3740 deselected in 517.39s`。

### 完成後維護 / D3390 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3389 後重新掃描 deferred course roots、training 與 course-module candidates，沿用 D3389 的 backlog 邊界，收斂 schedule/deliver/finish/certify course；以 `time to enroll training`、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to schedule/deliver/finish/certify course` 是課程流程 KPI；其數值不應進入股票 target-price candidates。
2. pre-fix matrix 為 `480 cases / 2000 leaks / 792 valid-misses`；每個入口各有 400 leaks，valid-miss 分布為 parser 192、calibration 120、credibility 0、structured output 120、detector 360。
3. production 只追加四個 deferred course roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；`time to enroll training` 保持 residual control，financial `time to price` 維持獨立。

落地修改

1. 五個報告品質入口新增 course-residual lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 deferred course roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 24.42s`，沒有新增 consumer-specific cleanup。
2. D3390 post-fix course-residual matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price` 與 existing course control 均為 `[]`，residual `time to enroll training` 仍為 `[12.0]`。
3. D3376-D3390 完整相鄰 regression 為 `75 passed, 3740 deselected in 493.87s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_course_residual_lifecycle'`：`5 passed in 24.42s`。
- D3390 post-fix course-residual matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；residual `time to enroll training`：`[12.0]`。
- D3376-D3390 adjacent regression：`75 passed, 3740 deselected in 493.87s`。

### 完成後維護 / D3389 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3388 後重新掃描 course lifecycle 與 training controls，選擇明確非金融且尚未被既有 training guard 覆蓋的 enroll/start/complete/evaluate course roots；以 schedule course 作為 residual control，並保留 financial time-to 邊界。

核心判斷

1. `time to enroll/start/complete/evaluate course` 是課程流程 KPI；其數值不應進入股票 target-price candidates。
2. pre-fix matrix 為 `480 cases / 2000 leaks / 792 valid-misses`；每個入口各有 400 leaks，valid-miss 分布為 parser 192、calibration 120、credibility 0、structured output 120、detector 360。
3. production 只追加四個 course roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`；`time to schedule course` 保持 residual control，financial `time to price` 維持獨立。

落地修改

1. 五個報告品質入口新增 course lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 course roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 25.79s`，沒有新增 consumer-specific cleanup。
2. D3389 post-fix course matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`、financial `time to price` 與 existing training control 均為 `[]`，residual `time to schedule course` 仍為 `[12.0]`。
3. D3376-D3389 完整相鄰 regression 為 `70 passed, 3740 deselected in 475.51s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_course_lifecycle'`：`5 passed in 25.79s`。
- D3389 post-fix course matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；residual `time to schedule course`：`[12.0]`。
- D3376-D3389 adjacent regression：`70 passed, 3740 deselected in 475.51s`。

### 完成後維護 / D3388 / #拆解問題 #差距分析 #偏誤降低 #比較組 #證據基礎 #可驗證性 #來源品質

本次使用：在 D3387 後重新掃描 training、learning 與 employee/training controls，選擇明確非金融且未被既有 `time to complete training` 覆蓋的 training lifecycle roots；以既有 employee control、financial time-to 與 explicit target price 作為比較組。

核心判斷

1. `time to start/schedule/deliver/evaluate training` 是訓練流程 KPI；其數值不應進入股票 target-price candidates。
2. pre-fix matrix 為 `480 cases / 2000 leaks / 792 valid-misses`；每個入口各有 400 leaks，valid-miss 分布為 parser 192、calibration 120、credibility 0、structured output 120、detector 360。
3. production 只追加四個 training roots 到共享 `QUALITY_SERVICE_METRIC_PATTERN`，既有 `time to complete training`、`time to train employee` 與金融 `time to price` 保持獨立。

落地修改

1. 五個報告品質入口新增 training lifecycle regression；parser、calibration、credibility、structured output 覆蓋 480 組語料，detector 依既有 path boundary 覆蓋 400 組語料。
2. `backend/price_parser.py` 共享 time-to branch 加入四個 training roots，維持 parser/detector `349/189` 行及 runtime/storage 邊界。

優化說明

1. 五入口 RED 後 shared-pattern GREEN 通過 `5 passed in 25.39s`，沒有新增 consumer-specific cleanup。
2. D3388 post-fix training matrix 為 `480 cases / leaks=0 / valid_misses=0`；explicit target price `[205.0]`，financial `time to price`、existing `time to complete training` 與 `time to train employee` controls 均為 `[]`。
3. D3376-D3388 完整相鄰 regression 為 `65 passed, 3740 deselected in 450.64s`。

驗證方式

- `$(scripts/project_python.sh) -m pytest tests/test_price_parser.py tests/test_recommendation_calibration.py tests/test_content_credibility_inputs.py tests/test_structured_output_parser.py tests/test_report_target_price_detection.py -q -k 'time_to_training_lifecycle'`：`5 passed in 25.39s`。
- D3388 post-fix training matrix：`480 cases / leaks=0 / valid_misses=0`。
- explicit target price：`[205.0]`；financial `time to price`：`[]`；existing training/employee controls：`[]`。
- D3376-D3388 adjacent regression：`65 passed, 3740 deselected in 450.64s`。

### 完成後維護 / D3530 / #拆解問題 #差距分析 #偏誤降低 #證據基礎 #可驗證性

- RED 測試先驗證品質稽核 CTA 沒有呈現 audit item 的白話 `detail`、`title` 與 `reason_codes`；GREEN 實作只在 watchlist helper 加上 `title`、`aria-label` 與 `data-quality-reason-codes`。
- 保留既有 report preview callback 與唯讀邊界，reason code 不會被當作可執行 action；helper cache-buster 更新為 `20260816-quality-audit-provenance-ui`。

### 完成後維護 / D3531 / #拆解問題 #差距分析 #偏誤降低 #證據基礎 #可驗證性 #來源品質

- 以 live RQ snapshot 的 `stock-analysis failed=10` 作為問題證據，確認既有 queue depth/registry payload 未形成 metric、ops status 或維運 UI 的一致訊號。
- 先以 RED 鎖定 failed registry metric、named queue aggregate、ops warning 與 maintenance copy，再以 GREEN 實作共用 `failed_queue_count` 和 `stock_agent_queue_failed_jobs`；不觸發清除、重試或資料寫入。
- safe-output regression 校正為：有效的 `failed=3` 即使伴隨 malformed named fields，也必須保留 `warning`，避免安全轉換掩蓋真實失敗工作。

### 完成後維護 / D3532 / #拆解問題 #差距分析 #偏誤降低 #證據基礎 #抽樣 #可驗證性 #來源品質

- 抽樣 live failed registry 的 10 筆 job，確認皆為 6 月 28 日 `test_rq_sys_config.run_job` timeout/abandoned；以 RQ `failure_ttl=7 天` 作為過期比較組。
- RED 先鎖定 job `ended_at`/`created_at` 的 recent/stale 分類、stale-only 不觸發 ops warning、三組 Prometheus metrics 與前端「過期失敗殘留」文案；GREEN 後保留總量證據但降低過期殘留對事故警示的干擾。

### 完成後維護 / D3533 / #拆解問題 #差距分析 #偏誤降低 #證據基礎 #受眾 #語意含義 #可驗證性

- `market_data` 的 FMP stable quote 雖是非主要 fallback，健康的 yfinance 不能抹掉 FMP provider 在 system window 的實際失敗；既有 D3516「不降級 system-level critical」決策繼續有效。
- dashboard 改以同一選定視窗的 provider rows 判定 usable evidence：有健康資料時只新增 `current_source_has_healthy_entry=true`，不改 `impact=core`、`status=critical` 或核心告警計數；這避免「備援覆蓋」與「provider 恢復」兩個語意混在一起。
- focused runtime observability regression 通過 8 tests；新增文件契約要求保留 system-level critical 與 fallback coverage 欄位，報告動作仍回到 `data_trust`/`今日工作台`。

### 完成後維護 / D3534 / #拆解問題 #差距分析 #偏誤降低 #證據基礎 #受眾 #可驗證性

- 把核心 provider critical 拆成 covered/uncovered summary count，讓操作人員不用逐筆展開 alert 才知道是否已有同 source 的健康資料。
- count 只讀取已判定的 `current_source_has_healthy_entry`，不重算、不改 system-level `critical`，也不越界到單份報告 rerun；新增 runtime 與 docs contract assertions。

### 完成後維護 / D3535 / #拆解問題 #差距分析 #偏誤降低 #證據基礎 #受眾 #責任 #可驗證性

- 將品質 repair item 的精確缺 gate 輸出為 `missing_quality_fields`，並在 audit serializer 與 watchlist CTA 保留；前端另以 `data-quality-missing-fields` 和新 cache-buster 確保人工核對讀到新欄位。
- 以 live full audit 的 160 份 verified snapshot、158 份 complete、2 份 1623.TW 缺 metadata 作為範圍證據；欄位只描述已存在的缺口，不從 HTML/Markdown 重建品質結果。
- RED→GREEN 鎖定 repair queue、full audit、前端 attribute、docs contract；不自動修 artifact/index、不進 daily action queue、不 enqueue rerun。

### 完成後維護 / D3536 / #拆解問題 #差距分析 #偏誤降低 #證據基礎 #受眾 #語意含義 #可驗證性

- full audit 的缺口總數與可見 item 明細不是同一個集合；先以 `items_returned`/`items_truncated` 固定 envelope 語意，再讓前端明說未展開筆數，避免把 UI cap 誤讀成 audit cap。
- RED 測試先讓 3 筆缺口、`item_limit=2` 暴露 metadata 缺失，再以工作台 8 筆缺口/2 筆可見案例鎖定提示文字；GREEN 後維持 read-only 與 report history 查詢邊界。
- 不用 `items.length` 猜全量、不新增 rerun/repair side effect；docs contract、audit regression 與 JavaScript syntax check 共同驗證跨層契約。

### 完成後維護 / D3537 / #拆解問題 #差距分析 #偏誤降低 #證據基礎 #責任 #可驗證性

- 用 `MappingProxyType` 做邊界 probe，確認 repair helper 的 `dict.get` 對唯讀 top-level mapping 會直接 TypeError；先修容器形狀邊界，再保留原有 gate 判定與優先級。
- RED→GREEN 以完整 verified snapshot 加三個 passed gate 的 mapping wrapper 驗證 helper 回傳 `None`，並同步要求 nested gate mapping 可被安全讀取；不以例外 fallback 掩蓋品質缺口。
- 新增 mapping-safe code path、docs contract 與 HCS 紀錄；audit/repair focused regression 通過，後續仍需跑完整跨層回歸與 live restart。

### 完成後維護 / D3538 / #拆解問題 #差距分析 #偏誤降低 #證據基礎 #語意含義 #可驗證性

- `非空文字` 不是品質 gate 結果；先用 contract allowlist 區分「已記錄但 warning/blocked」與「placeholder/未知值」，避免 coverage 產生假綠燈。
- RED 以 `not_recorded`、`unknown`、`N/A` 三種 placeholder 鎖定三 gate 缺失，再用 `warning`、`caution`、`blocked` 比較組確認合法非通過狀態仍算已記錄。
- GREEN 同時覆蓋 repair helper 與 full audit；保留既有 priority、reason code、live artifact 不寫入與 daily action queue 邊界。

### 完成後維護 / D3539 / #拆解問題 #差距分析 #偏誤降低 #證據基礎 #受眾 #語意含義 #可驗證性

- 以 filesystem `1330` 份 snapshot 對 live audit `160` rows 的差距確認 `all_indexed_reports` 不是 historical versions 全掃，而是最新 ticker/pipeline 索引列。
- RED→GREEN 把 `selection_basis=latest_per_ticker_pipeline` 加入 API 與工作台 label，保留相容 `scope` 但補足讀者範圍；cache-buster 同步更新，避免舊 helper 隱藏限制句。
- 不把 coverage 數字外推成所有 artifact 品質、不新增昂貴 historical scan；docs、frontend、audit payload 與 static asset contract 一起驗證。

### 完成後維護 / D3540 / #拆解問題 #差距分析 #偏誤降低 #證據基礎 #受眾 #語意含義 #可驗證性

- live historical audit 量化為 1330 個 indexed versions、143 個品質 metadata 缺口、89.25% verified snapshot coverage；確認缺口不能只靠 daily 最新列觀察。
- RED→GREEN 新增 `build_historical_indexed_report_quality_audit()` 與 `/api/watchlist/report-quality-audit/historical`，以明確 `all_indexed_versions` selection basis 和 `item_limit=0` summary mode 保持操作範圍可讀。
- route test 證明歷史查核不呼叫 mutation authorization；保留 read-only artifact/index/rerun 邊界，並同步 API、operator、architecture、OpenAPI 契約。

### 完成後維護 / D3541 / #拆解問題 #差距分析 #偏誤降低 #證據基礎 #受眾 #語意含義 #可驗證性

- 以 live 143 筆 historical 缺口確認總數不足以判斷人工順序；field distribution 必須與 verified snapshot 分母同一個 evidence boundary。
- RED→GREEN 新增 `missing_quality_field_counts`，三個 gate 各自計數；前端以白話 label 顯示，未知欄位不被渲染成任意文字。
- 完成 API/operator/architecture/docs contract、Node syntax、focused regression；不把欄位統計轉成 daily queue、rerun 或 repair。

### 完成後維護 / D3542 / #拆解問題 #差距分析 #偏誤降低 #證據基礎 #受眾 #語意含義 #可驗證性

- repeated live probe 量得 historical audit 約 1.85 秒；以 filtered audit 降低 targeted review 成本，不用未驗證的 TTL cache 掩蓋新 snapshot。
- RED→GREEN 鎖定 `q`/`pipeline` 從 FastAPI route 傳到 `query_report_metadata`，並保持 `include_versions=True` 與 `all_indexed_versions` 語意。
- 文件補充 filtered `audited_reports` 的分母意義；builder/route compile 與 focused tests 通過，仍無 mutation authorization 或寫入副作用。

### 完成後維護 / D3543 / #拆解問題 #差距分析 #偏誤降低 #證據基礎 #受眾 #語意含義 #可驗證性

- live pipeline probe 找到 v1/v2/v3 高缺口與 v4 低缺口的集中差異；不把全歷史 coverage 當成所有模式同質。
- RED→GREEN 新增 `quality_metadata_by_pipeline` 與前端「模式缺口」摘要；每個分組保留 verified denominator/basis，避免分組百分比失去語意。
- 完成 docs contract、Node syntax、focused regression；詳細查核仍走 q/pipeline read-only filter，不新增 queue、rerun 或 repair side effect。
### 完成後維護 / D3666 / #拆解問題 #差距分析 #最小變更 #受眾 #溝通設計 #來源品質 #偏誤降低 #可驗證性 #語意含義 #責任

- live `/api/reports` full latest scope 是 165 份，current quality gate 分布與 persisted metadata coverage/freshness 是不同 evidence layer；若只顯示近期 20 份，操作人員無法知道全量 warning/blocked 風險。
- 新增 `backend/report_current_quality_summary.py`，以既有 report-history current-rule projection 為唯一來源，分開統計 conformance/content/evidence 三組分布，並限制 5 筆 non-passed targets；不把 UI sample 當成全量分母。
- daily dashboard 保持快速回應；watchlist 在首屏完成後背景呼叫獨立 `GET /api/watchlist/current-quality-summary`，再用獨立 helper 呈現「目前品質」與 history CTA。summary/target 都驗證 schema、scope、selection basis、分母與 bounded counts，legacy payload 沒有新欄位時維持既有畫面。
- current target 只呼叫既有 `StockAgentOpenHistoricalQualityAudit` 導覽，沒有 queue、review、artifact、index 或 rerun side effect；API/operator/architecture/system map 同步記錄這個邊界。
- focused tests `94 passed`；第一次 full concurrent projection 曾使 dashboard 約 18 秒，改成背景載入後需驗證 fast daily response、current endpoint `165` 分母、30 秒 TTL 與 browser/Node rendering，再跑完整 scoped regression。
- D3667：P3-? 修正 evidence claim parser 將日期年份誤判為數字 claim：live 抽樣重現 `2026/07/31`、`2026-08-20` 後，先以紅燈回歸鎖定斜線／連字號／句點日期，保留裸年份與 `TWD` 金融數字；最小 production 修正合併既有年份 guard，`backend/evidence_exit_gate.py` 維持 349 行。focused evidence/projection `20 passed`，完整 suite `8189 passed, 6 skipped` 僅觸發一次 350 行門檻後，以等價壓縮修正並重跑門檻 `1 passed`；live 165 reports 的日期年份 claim `3→0`、`unverifiable 242→239`、`sampled 336→333`，總體 caution 分布不變，未將局部改善誇大為全量通過。
- D3668：P3-? 以 live snapshot 驗證 evidence claim 的停損語意映射：`停損／止損／stop_loss` 對到 `stop_loss` path，新增 fixture regression；focused report-quality `136 passed`、import/docs `572 passed`、`py_compile`、`git diff --check` 與 doctor_runtime 通過。live 165 reports 的 `approved 39→54`、`caution 125→110`、`unverifiable 239→199`，40 筆停損 claims verified。曾試驗支撐→stop_loss，但 `2031.TW`、`6226.TW` 顯示歷史支撐與停損可能不同，造成假 mismatch，因此撤回該過寬映射。
- D3669：P3-? 依 #拆解問題 / #差距分析 / #偏誤降低 / #證據基礎 / #抽樣 / #可驗證性 / #來源品質，將 evidence gate 的同語意籌碼欄位納入 canonical snapshot：先用 `Margin balance (2026-07-29): 5,290K` 取得 parser RED，確認 snapshot 以千股顯示單位保存 5290；再以 RED→GREEN 鎖定 `K/k` 單位、句尾句點、major/retail holders、margin/short balance、margin/short purchase/sale 與 borrowed short sale balance 的精確路徑。保留 borrowed short `k` 股數的單位差異、confidence、歷史 target 與 support/stop_loss 的人工核對邊界，不用寬泛 marker 消除 warning。focused evidence `22 passed`、py_compile、health/readiness 與 doctor runtime 通過；live 165 reports 由 D3668 基線 approved 54→60、caution 110→104、rejected 維持 1、unverifiable 199→172，抽樣 333 筆 verified 160、mismatch 1。唯一 mismatch 是既有 3653.TW v1 淨利率與 canonical snapshot 不一致；本輪未寫 snapshot、artifact、index、review、rerun、repair 或 queue。
- D3670：P3-? 依 #拆解問題 / #差距分析 / #偏誤降低 / #證據基礎 / #抽樣 / #比較組 / #可驗證性 / #來源品質，修正兩個 evidence 語意邊界：3653.TW 的年度 DuPont `26.0%` 必須驗證到 `data.dupont_identity_note`，不可與 TTM `data.profit_margin=28.4%` 混比；報告明示 `market_data.week_52_high_twd/low_twd` 時，只有 source marker 緊鄰該數字才映射 `data.week_52_high/low`，避免 2455.TW 同行後段來源污染前段 claim。先取得 DuPont 與 source-adjacency RED，再完成 GREEN；focused evidence `25 passed`、py_compile、line guard 349、health/readiness 與 doctor runtime 通過。live 165 reports 的 evidence `approved 60 / caution 105 / rejected 0`，抽樣 333 筆 `verified 164 / unverifiable 169 / mismatch 0`；本輪未寫 snapshot、artifact、index、review、rerun、repair 或 queue。
- D3671：P3-? 依 #拆解問題 / #差距分析 / #偏誤降低 / #證據基礎 / #抽樣 / #比較組 / #可驗證性 / #來源品質，補齊英文 TDCC concentration/retail claim 的精確路徑：`Concentration: 72.78% (>1000 lots)` 對到大戶持有比例，`Retail: 14.85% (<50 lots)` 對到散戶持有比例；先取得 fixture RED，再用「label + lots threshold」雙條件完成 GREEN，保留 `券資比`、派發評分等沒有 canonical scalar 的語意不映射。focused evidence `26 passed`、py_compile、line guard 349；runtime reload 後 live 165 份 evidence `approved 61 / caution 104 / rejected 0`，抽樣 333 筆 `verified 166 / unverifiable 167 / mismatch 0`，mismatch 仍為 0；report conformance `passed 43 / warning 114 / blocked 8`、content credibility `passed 45 / warning 112 / blocked 8`。本輪未寫 snapshot、artifact、index、review、rerun、repair 或 queue。
- D3672：P3-? 依 #拆解問題 / #差距分析 / #偏誤降低 / #證據基礎 / #抽樣 / #比較組 / #可驗證性 / #來源品質，補齊 explicit current-price 與 prefixed week-52 source claim：`當前價格 85.5 元（market_data.current_price_twd）` 對到 `data.current_price`，`52週高點 112.3 TWD（data.market_data.week_52_high_twd）` 對到 `data.week_52_high`。先取得 RED，再以 `當前價格` 精確 hint 與 `data.` optional prefix 完成 GREEN；保留 source adjacency guard，沒有放寬歷史支撐／壓力或信心欄位。focused evidence 新增 fixture 通過；runtime reload 後 live 165 份 evidence `approved 62 / caution 103 / rejected 0`，抽樣 333 筆 `verified 169 / unverifiable 164 / mismatch 0`。本輪未寫 snapshot、artifact、index、review、rerun、repair 或 queue。
- D3673：P3-? 依 #拆解問題 / #差距分析 / #偏誤降低 / #證據基礎 / #抽樣 / #比較組 / #可驗證性 / #來源品質，補齊標準 52 週高／低點 claim 的格式與語意邊界：支援 `52 週高點：2,585.0 TWD`、`壓力位：21.6 TWD（52 週高點）`、`支撐位：17.6 TWD（52 週低點）`，也接受數字後的 Markdown `**`，但只在 exact label/unit 且 reported value 與同句標籤相符時映射。3406.TW 的前段 659 與 stop-loss 仍未被後段 52 週高點污染。focused evidence `30 passed`、py_compile、line guard 349；runtime reload 後 live 165 份 evidence `approved 63 / caution 102 / rejected 0`，抽樣 333 筆 `verified 172 / unverifiable 161 / mismatch 0`；report conformance `passed 44 / warning 113 / blocked 8`、content credibility `passed 46 / warning 111 / blocked 8`。本輪未寫 snapshot、artifact、index、review、rerun、repair 或 queue。
- D3674：P3-? 依 #拆解問題 / #差距分析 / #偏誤降低 / #證據基礎 / #抽樣 / #比較組 / #可驗證性 / #來源品質，補齊籌碼 `Previous` claim 的 line-local semantic context：同句有 `Margin Balance` 才映射 `margin_previous_balance`，同句有 `Short Balance` 才映射 `short_previous_balance`；先取得孤立 Previous RED，再完成 GREEN，保留跨行與無 context 的人工核對邊界。focused evidence `31 passed`、py_compile、line guard 349；runtime reload 後 live 165 份 evidence `approved 65 / caution 100 / rejected 0`，抽樣 333 筆 `verified 175 / unverifiable 158 / mismatch 0`、mismatch 為 0；report conformance `passed 46 / warning 111 / blocked 8`、content credibility `passed 48 / warning 109 / blocked 8`。本輪未寫 snapshot、artifact、index、review、rerun、repair 或 queue。
- D3675：P3-? 依 #拆解問題 / #差距分析 / #偏誤降低 / #證據基礎 / #抽樣 / #比較組 / #可驗證性 / #來源品質，將明示 `price_history` claim 綁定到日期索引：`2026年6月30日` 只可命中 snapshot 同日期的 `prices[index]`，錯日期即 mismatch；0050.TW 命中 `data.price_history[2026-06-30].prices[9]`，3702.TW 命中 `[10]`。先取得同值錯日期 RED，再完成 GREEN；focused evidence `32 passed`、py_compile、line guard 349。runtime reload 後 live 165 份 evidence `approved 67 / caution 98 / rejected 0`，抽樣 333 筆 `verified 177 / unverifiable 156 / mismatch 0`；report conformance `passed 47 / warning 110 / blocked 8`、content credibility `passed 49 / warning 108 / blocked 8`。本輪未寫 snapshot、artifact、index、review、rerun、repair 或 queue。
- D3676：P3-? 依 #拆解問題 / #差距分析 / #偏誤降低 / #偏誤辨識 / #證據基礎 / #抽樣 / #比較組 / #可驗證性 / #來源品質，補齊 explicit institutional total net-buy claim：只有 label `totalnetbuythousandshares` 與同句欄位 marker 同時成立，才映射 `data.institutional_trading.total_net_buy_thousand_shares`；category/daily/last-5-day 同值不被混用。先取得 exact-path RED，再完成 GREEN；focused evidence `33 passed`、py_compile、line guard 349。runtime reload 後 live 165 份 evidence `approved 67 / caution 98 / rejected 0`，抽樣 333 筆 `verified 178 / unverifiable 155 / mismatch 0`、mismatch 為 0；report conformance `passed 47 / warning 110 / blocked 8`、content credibility `passed 49 / warning 108 / blocked 8`。本輪未寫 snapshot、artifact、index、review、rerun、repair 或 queue。
- D3677：P3-? 依 #拆解問題 / #差距分析 / #偏誤降低 / #偏誤辨識 / #證據基礎 / #抽樣 / #比較組 / #可驗證性 / #來源品質，補齊 explicit institutional last-5-day net-buy claim：只有同句 exact field marker `last_5_trading_days_net_buy_thousand_shares` 成立，才映射 `data.institutional_trading.last_5_trading_days_net_buy_thousand_shares`；total/daily 同值不被混用。先取得 exact-path RED，再完成 GREEN；`tests/test_evidence_exit_gate.py` `32 passed`、py_compile、line guard 349。runtime reload 後 live 165 份 evidence `approved 67 / caution 98 / rejected 0`，抽樣 333 筆 `verified 178 / unverifiable 155 / mismatch 0`、mismatch 為 0；report conformance `passed 47 / warning 110 / blocked 8`、content credibility `passed 49 / warning 108 / blocked 8`。本輪未寫 snapshot、artifact、index、review、rerun、repair 或 queue。
- D3678：P3-? 依 #拆解問題 / #差距分析 / #偏誤降低 / #偏誤辨識 / #證據基礎 / #抽樣 / #比較組 / #可驗證性 / #來源品質，修正固定 random sample 漏掉高風險 valuation claim 的盲點：反引號欄位 marker 與 `PE TTM` / `Forward PE` / `本益比` 優先入樣，剩餘名額才使用既有 seed；不增加 sample 上限、不改寫 mismatch。3653.TW 的 `135.1239` 對 canonical `data.pe_ratio_raw=126.6109`、`37.2535` 對 `data.forward_pe_raw=40.577065` 現在 live 被抽中並判 mismatch。先取得抽樣 RED，再完成 GREEN；`tests/test_evidence_exit_gate.py` `33 passed`、py_compile、line guard 348。runtime reload 後 live 165 份 evidence `approved 66 / caution 98 / rejected 1`，抽樣 `verified 176 / unverifiable 155 / mismatch 2`；report conformance `passed 46 / warning 111 / blocked 8`、content credibility `passed 48 / warning 109 / blocked 8`。本輪未寫 snapshot、artifact、index、review、rerun、repair 或 queue。
- D3679：P3-? 依 #拆解問題 / #差距分析 / #偏誤降低 / #偏誤辨識 / #證據基礎 / #抽樣 / #比較組 / #可驗證性 / #來源品質，收斂無欄位 marker 的日期價格 claim：3406.TW 的 `近期高點壓力 659.0 元（2026 年 6 月 30 日收盤價）` 精確對到 `data.price_history[2026-06-30].prices[9]`；以 8438.TW 的 `market_catalysts` 新聞壓力值 55.8、canonical 收盤 53.7 作反例，拒絕任意「高點／壓力＋日期」映射。只有日期、價格語意、貨幣單位與 `收盤／close` 同時成立才補 `price_history[date]` marker，已有明示 `price_history` marker 的路徑不變。先取得 RED，再完成 GREEN 與反例回歸；`tests/test_evidence_exit_gate.py` `35 passed`、report-quality scoped `1209 passed`、py_compile、line guard 349。runtime reload 後 live 165 份 evidence `approved 68 / caution 96 / rejected 1`，抽樣 `verified 180 / unverifiable 151 / mismatch 2`；report conformance `passed 48 / warning 109 / blocked 8`、content credibility `passed 50 / warning 107 / blocked 8`。本輪未寫 snapshot、artifact、index、review、rerun、repair 或 queue。
- D3680：P3-? 依 #拆解問題 / #差距分析 / #偏誤降低 / #證據基礎 / #來源品質 / #可驗證性 / #受眾，將 deterministic financial cross-check 從 prompt-only 計算收斂為可回溯 snapshot evidence：`3653.TW` 的 `forward_eps_implied_revenue_growth_pct: 262.715%` 在既有 snapshot 沒有 canonical path，保持 `unverifiable`；RED 先以 `build_data_snapshot()` 缺少 `financial_cross_checks` 的 KeyError 鎖定缺口，再新增共用 `backend/financial_cross_checks.py`，由 prompt 與新 snapshot 共同使用 `shares_raw`、`forward_eps`、`profit_margin_raw`、`revenue_ttm_raw`，snapshot 只保存 deterministic result，不回寫歷史 artifact。新增 evidence fixture 驗證精確 path，缺 raw input 時仍不推導。GREEN：data-trust 183、prompt 137、evidence 36、報告品質主回歸 553、import boundary 504 passed；py_compile、doctor、health/ready 通過，`financial_tools.py` 恢復 `<240` 行。live current 165 份為 evidence approved 68 / caution 96 / rejected 1、conformance 48/109/8、content 50/107/8；historical read-only 1222 份且三 gate metadata gap 各 115；queue depth 0、failed_recent 0、stale 10，沒有新增 queue 或其他寫入副作用。
- D3681：P3-? 依 #拆解問題 / #差距分析 / #偏誤降低 / #證據基礎 / #語意含義 / #可驗證性 / #責任，對齊 quality-audit row 與 report-history 的 current-rule evidence projection：新增 `report_quality_audit_rows` 只讀重驗 Markdown + snapshot，只有 persisted `approved`/`caution`/`rejected` 才投影；缺 gate 不補齊，full audit 仍保留 `project_current_quality=False`，因此 persisted metadata coverage 分母不變。RED→GREEN 以 stale `approved` 對 mismatch snapshot 得到 current `rejected`，並鎖定缺 gate 與 full-audit 隔離；quality-audit focused 34、跨層 quality/evidence/frontend 67、報告品質/data-trust 418、import boundary 504 passed，py_compile/diff check 通過。正式 runtime `3653.TW v3` current projection 為 `rejected`（2 mismatch、2 unverifiable），保留 `persisted_verdict=approved` 與 `needs_rerun`，data/Markdown hashes 未變；historical 1222 份、三個 persisted gate gap 各 115，current 165 份 conformance 48/109/8、content 50/107/8、evidence 68/96/1。health/readiness/doctor 通過，queue depth 0、failed_recent 0、stale 10；未改 artifact、index、review、rerun、repair 或 queue。
