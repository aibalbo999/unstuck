# 四模式 prospective OOS 成熟日執行手冊

本手冊只處理已封閉的 `four-mode-credibility-prospective-r1`。不得重做 selection、補送失敗 Job、替換 `3324.TWO` v1／v3，或改寫既有 candidate／dataset／evaluation／summary record。

## 固定輸入

- Attested source commit：`65a1af14f5cb2e55f9bc93614905c209eeff0b24`
- Source ref：`refs/heads/codex/analysis-credibility-spec`
- Manifest raw SHA-256：`f602ac6baa372098fe2bf86505bcae290ec868dd78ee5dd16839e43c1a980022`
- Cohort source SHA-256：`f9d697eacc525ba8c0bbd7d8d4dde0d8619982ee96da6076f2af3c7d2fce0af2`
- Final inventory content hash：`007370b69653c7a6ad3cfc382a31b4c542377991bb1244c40bf4497088844158`
- 固定分母：28 candidates；26 `insufficient_provenance`、2 `missing_report`。除非同一份固定 evidence 經新版 validator 查出真實分類錯誤，否則不得升格為 `admitted`。

正式成熟日：

| Cutoff | 範圍 |
| --- | --- |
| 2026-09-15、09-16、09-17 | 各 first-session 群組的第 5 個交易日 |
| 2026-09-22、09-23、09-24 | 各 first-session 群組的第 10 個交易日 |
| 2026-12-08、12-09、12-10 | v1 的 3 個曆月 endpoint |
| v1 6／12 個月 | 取得覆蓋 2027 年的明確官方 session calendar 後另算，不得猜日期 |

## 每個 checkpoint

從乾淨、已 commit 的 runner checkout 執行。`CHECKPOINT_DIR` 與其下所有檔名都必須是新的 revision；若已存在，保留原件並改用新的 revision 名稱，不得刪除或覆寫。

```bash
PROJECT_PYTHON="/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python"
EVIDENCE_ROOT="/Volumes/X10 Pro Mac/stock-agent-oos-evidence/four-mode-credibility-prospective-r1"
RUN_ID="2026-09-15T150500+0800-r1"
CHECKPOINT_DIR="$EVIDENCE_ROOT/checkpoints/$RUN_ID"
mkdir -m 700 "$CHECKPOINT_DIR"

"$PROJECT_PYTHON" scripts/build_oos_official_market_dataset.py \
  --inventory "$EVIDENCE_ROOT/candidate-inventory-final-2026-09-10.json" \
  --sessions "$EVIDENCE_ROOT/twse-sessions-2026-09-09-to-2026-12-31.json" \
  --cutoff-session 2026-09-15 \
  --raw-dir "$CHECKPOINT_DIR/raw-official" \
  --output "$CHECKPOINT_DIR/dataset.json"

PYTHONPATH=backend "$PROJECT_PYTHON" -m oos_research.cli \
  --root "$EVIDENCE_ROOT/study" \
  --manifest docs/oos-prospective-manifest-2026-09-08.json \
  --inventory "$EVIDENCE_ROOT/candidate-inventory-final-2026-09-10.json" \
  --dataset "$CHECKPOINT_DIR/dataset.json" \
  --attestation-bundle "$EVIDENCE_ROOT/sha256:f602ac6baa372098fe2bf86505bcae290ec868dd78ee5dd16839e43c1a980022.jsonl" \
  --trusted-root "$EVIDENCE_ROOT/trusted-root-2026-09-08.jsonl" \
  --source-commit 65a1af14f5cb2e55f9bc93614905c209eeff0b24 \
  --source-ref refs/heads/codex/analysis-credibility-spec \
  --output "$CHECKPOINT_DIR/replay-result.json" \
  --markdown-output "$CHECKPOINT_DIR/summary.md"
```

行情 builder 只呼叫 TWSE `STOCK_DAY` 與 TPEx `tradingStock` 官方 HTTPS endpoints，保存每次 raw JSON、URL、capture time 與 SHA-256，並在所有回應完成後由程序產生 dataset `as_of`。若任一 ticker 的 cutoff row 尚未發布，整個 dataset fail closed；不得手填完成時間。Python 對 TPEx 憑證只關閉 `VERIFY_X509_STRICT` 相容旗標，CA 與 hostname 驗證仍維持啟用。

Replay 會在同一程序重新執行離線 GitHub/Sigstore verification，不接受序列化 projection 取代 capability；也會由 raw captures 重建 dataset，再核對 OHLC、calendar、inventory hash 與 dataset hash。每個 checkpoint 以 dataset hash 產生獨立的 registration、admission、dataset、evaluation、summary 與 checkpoint record，並保存 runner source hashes。

完成後至少核對：

- `study_classification=prospective` 且 `registration_reason_codes=[]`。
- `candidate_total=28`、分頁未截斷；缺報告仍為 2。
- 非 `admitted` candidate 不得有 scored evaluation；目前固定 inventory 的預期 `evaluation_total=0`。
- `raw_capture_count`、ticker 清單、每檔 bar 日期與 official session calendar 一致；dataset 不含 cutoff 後日期。
- 保存 `dataset.json`、raw responses、`replay-result.json`、`summary.md` 與 study 新增 records 的 SHA-256，再把排程移到下一個實際成熟日。
