"""TCFHC profiles in a private process; shared/generic readers stay unchanged."""
import sys
import syntec_annual_pdf_worker as worker

PROFILES = {
    '2021': (240, (1, 3, 7, 8, 9, 10, 11, 12, 14, 15, 16)),
    '2022': (238, (1, 3, 7, 8, 9, 10, 11, 12, 14, 15, 16)),
    '2023': (242, (1, 3, 7, 8, 9, 10, 11, 12, 14, 15, 16)),
    '2024': (245, (1, 3, 7, 8, 9, 10, 11, 13, 14, 15)),
    '2025': (247, (1, 3, 7, 8, 9, 10, 11, 12, 14, 15, 16)),
}

if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[2] not in PROFILES:
        raise SystemExit(2)
    worker.INPUT_LIMIT = 8 * 1024 * 1024
    worker.PAGE_LIMIT, worker.SELECTED = PROFILES[sys.argv[2]]
    raise SystemExit(worker.main())
