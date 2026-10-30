# Official daily feed lag recovery (2026-10-02)

Tonight 18:00 scanning imported ten research names, and all ten obtained formal reports. Thirteen reports completed after 18:00 (including the earlier queued 2481 job); last publication was 1514 at 20:57 Taipei. No qualified actionable two-week candidate was present.

At 21:14 Taipei the official STOCK_DAY_ALL and STOCK_DAY_AVG_ALL responses both reported 1151001. The existing scanner accepted a nonempty stale price frame while institutional observations were 2026-10-02. Same-date guards correctly left normalized ratios unknown, but the scanner exposed no source warning and its fallback ticker order could look like a meaningful ranking.

The free, audited TWSE MI_INDEX date=20261002&type=ALL endpoint returned stat=OK and date=20261002 at 21:17 Taipei. The new adapter accepts this backup only after verifying the response date, status and named table fields. Failure retains the actual old dates and emits warnings; later normal reads may recover. Missing values remain unknown; shares remain shares. The old-date monthly average is not reused to calculate new-date bias, nor substituted for a 20-session baseline or volume ratio. Source URL and a canonical decoded-JSON fingerprint travel with joined observations (this fingerprint is not a hash of archived raw HTTP bytes).

Archived-source replay verified 1,120 common stocks with 2026-10-02 observations, including 1301 close 68.30 and volume 33,115,055 shares. Capture manifests and raw bodies are retained in the review workspace hcs-phase9-official; hcs-phase9-source-replay.json records the replay receipt. This verifies source parsing, not forecast quality, point-in-time independence, adjusted/raw equality for all reports, transaction costs or a trading strategy.

Existing saved observations are not rewritten or rescanned. The read-only saved-list API and screener UI now disclose missing same-date price/volume evidence. The cache version changes so future scheduled scans use the corrected source contract. There is no new schedule or external notification. Existing daily scanning remains 18:00 Asia/Taipei and report processing follows the established queue.

The approved finite batch remains five no-trade revisions and 71 pending; no rerun or performance substitution is performed. Independent event/volume evidence, report adjusted-price versus official-raw checks, valid execution price grids, and remaining maturity/cost limitations still prevent treating research names as qualified recommendations.
