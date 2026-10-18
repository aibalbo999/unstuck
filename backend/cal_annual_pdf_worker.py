"""Reuse the audited private extractor in this child process only.

The parent reader validates the exact year/profile and the whole input SHA.
No change is made to the Syntec or generic PDF reader's allowed profile.
"""
import sys
import syntec_annual_pdf_worker as worker

if __name__ == '__main__':
    profiles={'2022':90,'2024':94,'2025':91}
    if len(sys.argv)!=3 or sys.argv[2] not in profiles:
        raise SystemExit(2)
    worker.INPUT_LIMIT=3_000_000
    worker.PAGE_LIMIT=profiles[sys.argv[2]]
    worker.SELECTED=(1,3,6,11,12,13)
    raise SystemExit(worker.main())
