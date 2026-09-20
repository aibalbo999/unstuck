# 429 退避與連續分鐘限流

本次目標是減少無效重送、讓可用備援繼續工作；保留原始來源、品質閘門與每日額度保護。

## 已查證的問題

2026-09-20 台北時間 00:00–22:04 的正式 Google 呼叫事件共 875 次，記錄到 571 次 429。405 次 429 後，同工作／Agent／模型於 3 秒內換另一把 key；後續仍有 381 次 429、12 次成功、4 次 503 及 8 次其他失敗／取消。這些是應用程式記錄的 transport 嘗試，不能當作所有 HTTP sends 的精確數字。

Gemma 的兩個明確 input TPM 案例，分別在 38.3 秒內送出合計 17726 estimated tokens、40.6 秒內送出 17836 estimated tokens；provider 回覆 16000 TPM 限制。舊 Redis 固定整點分鐘計數會在跨分鐘時允許這種突發量。不能因此推定所有 key 的額度或 Google project 身分相同。

## 行為與入口

- `shared_runtime_guards.py` 使用 Redis TIME 與原子 Lua，按最近 60 秒逐筆計算 key／model RPM、TPM。拒絕不扣帳，須等到足夠舊預留過期；本機 limiter 使用相同滑動窗口。部署時保守等待仍有效的舊計數 TTL，不清空 quota state。
- `llm_congestion_store.py` 聚合同一 Google 模型在 60 秒內的不同 key 429。兩把 key 觸發暫時冷卻，60／120／240／300 秒逐步退避，另加 0–10 秒 jitter；provider 提示更長等待時採較長值。明確 RequestsPerDay 仍走原 key／model 每日停用，不混入此推論。
- 冷卻後僅允許一個 recovery probe。owner 與 generation 比對避免舊請求解除新冷卻；probe lease 至少涵蓋最長已設定生成 timeout 加 30 秒。取消／不確定失敗後等 30 秒再探測。一般成功不清掉近期其他 key 的失敗紀錄。
- `llm_congestion.py` 在 Agent 與 Gemma 的 provider request event 前檢查 admission；transport 在真正呼叫 Google 之後記一次結果。快取命中、品質失敗與中斷的 stream 都不能冒充成功的 recovery probe。
- `KeyRotator.model_circuit_wait()`／preflight 查詢共享等待，沿既有候選與 deferred retry 流程處理；查詢不占用 probe，也不延長冷卻期限。local block 與 provider 429 分開計帳。
- 共用 Google client 關閉 SDK 隱藏自動重試，生成重試交給既有有界 orchestration。共用此 client 的 embedding 也採單次嘗試；失敗沿原 RAG lexical fallback，不改寫來源或品質 gate。

正式 usage-aware profile 的 `congestion_guard_enabled` 控制共享 429 功能，也可用 `LLM_CONGESTION_GUARD_ENABLED` 覆寫。這個開關不關閉滑動分鐘限流與既有 RPD 保護；模型清單及角色候選順序不變。

## 驗收與限制

隔離測試覆蓋跨分鐘 TPM、同毫秒併發 RPM、拒絕不扣帳、兩個獨立 Redis client 的單 probe、不同 key 聚合、過期及舊結果、取消、快取、stream、實際 transport 接線與 RPD 分流。測試透過 `tests/run_prompt_boundary_tests.py` 隔離正式 SQLite／網路，Redis 行為另用一次性 Unix socket Redis 驗證。

- 這是觀測到模型擁塞後的保護策略，不是宣稱所有 key 共用 provider project quota。可能短暫延後尚可用的 key；仍可走其他已核准模型。
- 已送出的並行請求無法撤回；guard 限制後續 admission，不能保證窗口內最多只有兩筆 429。
- Redis 故障會保存本機已知等待，每個首次使用模型暫停至少 60 秒；分鐘 limiter 也等待一次完整窗口，再使用本機狀態。故障後需重新啟動程序才能恢復 Redis client。本機模式不保證跨 rotator／process 的分鐘總量或跨 process 單 probe。
- estimated input tokens 不是 provider 最終 token 計數；不保證消除所有 TPM 429。專案實際額度尚未由 AI Studio 驗證。
- 完整報告測試沿原品質 gate 生成私有產物，不發布到正式報告列表。真實樣本成功支持本次端到端功能，不能代替後續正式流量的長期錯誤率比較。
