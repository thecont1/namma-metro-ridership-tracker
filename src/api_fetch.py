#!/usr/bin/env python
"""Browser-free extractor for BMRCL ridership (experiment).

Uses bmrc_api.fetch_ridership, which re-discovers the site's API config
(key, port, endpoint path) from its own JS bundles on every run, so key
rotation and most config churn self-correct. The token is never written
to disk, logged, or included in output.
"""

import json
import resource
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from bmrc_api import fetch_ridership, map_record, PAGE_URL

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "out"

EXPECTED_COLUMNS = [
    'Record Date', 'Total Smart Cards', 'Stored Value Card',
    'One Day Pass', 'Three Day Pass', 'Five Day Pass',
    'Total Tokens', 'Total NCMC', 'Group Ticket',
    'Total QR', 'QR NammaMetro', 'QR WhatsApp', 'QR Paytm', 'QR ONDC'
]
CORE_COLUMNS = ['Total Smart Cards', 'Total Tokens', 'Total QR']


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    started = time.monotonic()

    report = {
        "engine": "api",
        "engine_version": "unversioned-json-endpoint",
        "token_source": "extracted from site JS bundle at run time (not stored)",
        "run_utc": ts,
        "url": PAGE_URL,
        "record_date": None,
        "values": {},
        "missing_columns": [],
        "raw_response": None,
        "discovery": None,
        "elapsed_seconds": None,
        "peak_rss_mb": None,
        "errors": [],
    }

    exit_code = 0
    try:
        record, meta = fetch_ridership(PAGE_URL)
        report["raw_response"] = record
        report["discovery"] = {
            "key_source": meta.get("key_source"),
            "attempts": meta.get("attempts", []),
        }
        mapped = map_record(record)
        report["record_date"] = mapped.get("Record Date")
        for col in EXPECTED_COLUMNS:
            if col in mapped:
                report["values"][col] = mapped[col]
            else:
                report["values"][col] = None
                report["missing_columns"].append(col)
    except Exception as e:  # noqa: BLE001
        report["errors"].append(f"fatal: {type(e).__name__}: {e}")
        exit_code = 1

    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    # ru_maxrss is bytes on macOS, kilobytes on Linux/other platforms
    rss_divisor = (1024 * 1024) if sys.platform == "darwin" else 1024
    report["peak_rss_mb"] = round(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / rss_divisor, 1
    )

    if report["record_date"] is None:
        report["errors"].append("missing record date")
        exit_code = 1
    missing_core = [c for c in CORE_COLUMNS if report["values"].get(c) is None]
    if missing_core:
        report["errors"].append(f"missing core values: {missing_core}")
        exit_code = 1

    out_path = OUT_DIR / f"api_{ts}.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nwrote {out_path}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
