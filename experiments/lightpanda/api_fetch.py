#!/usr/bin/env python
"""Browser-free extractor for BMRCL ridership (experiment).

The ridership page's JS bundle carries the site's own API key. This
script extracts it from the bundle at run time and calls the same JSON
endpoint the page uses. The token is never written to disk, logged, or
included in output — it lives only in a local variable for the duration
of the request.
"""

import json
import re
import resource
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
OUT_DIR = EXPERIMENT_DIR / "out"
PAGE_URL = "https://english.bmrc.co.in/ridership/"
API_PATH = "/api/users/getridership"

EXPECTED_COLUMNS = [
    'Record Date', 'Total Smart Cards', 'Stored Value Card',
    'One Day Pass', 'Three Day Pass', 'Five Day Pass',
    'Total Tokens', 'Total NCMC', 'Group Ticket',
    'Total QR', 'QR NammaMetro', 'QR WhatsApp', 'QR Paytm', 'QR ONDC'
]
CORE_COLUMNS = ['Total Smart Cards', 'Total Tokens', 'Total QR']

FIELD_MAP = {
    "RidershipDate": "Record Date",
    "TotalSmartCards": "Total Smart Cards",
    "StoredValueCard": "Stored Value Card",
    "OneDayPass": "One Day Pass",
    "ThreeDayPass": "Three Day Pass",
    "FiveDayPass": "Five Day Pass",
    "Tokens": "Total Tokens",
    "TotalNCMC": "Total NCMC",
    "GroupTicket": "Group Ticket",
    "TotalQR": "Total QR",
    "QRNammaMetro": "QR NammaMetro",
    "QRWhatsApp": "QR WhatsApp",
    "QRPaytm": "QR Paytm",
    "ONDC": "QR ONDC",
}


def _get(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def extract_api_key(page_url):
    """Pull the site's public API key out of its own JS bundle."""
    html = _get(page_url)
    m = re.search(r'src="([^"]*pages/ridership\.js[^"]*)"', html)
    if not m:
        raise RuntimeError("ridership.js bundle URL not found in page HTML")
    js = _get(urllib.parse.urljoin(page_url, m.group(1)))
    # bundle stores the literal as API_KEY = \"<hex>\" inside webpack's
    # escaped module strings, so match loosely rather than on quotes.
    key = re.search(r'API_KEY[^0-9a-fA-F]{1,20}([0-9a-fA-F]{32})', js)
    if not key:
        raise RuntimeError("API_KEY not found in ridership.js bundle")
    port = re.search(r'hostname[^,]*,\s*":(\d+)/api"', js)
    return key.group(1), int(port.group(1)) if port else 8282


def safe_err(e, secret):
    return str(e).replace(secret, "***") if secret else str(e)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    started = time.monotonic()

    parsed = urllib.parse.urlparse(PAGE_URL)
    api_url = f"{parsed.scheme}://{parsed.hostname}:8282{API_PATH}"

    report = {
        "engine": "api",
        "engine_version": "unversioned-json-endpoint",
        "token_source": "extracted from site JS bundle at run time (not stored)",
        "run_utc": ts,
        "url": api_url,
        "record_date": None,
        "values": {},
        "missing_columns": [],
        "raw_response": None,
        "elapsed_seconds": None,
        "peak_rss_mb": None,
        "errors": [],
    }

    api_key = ""
    exit_code = 0
    try:
        api_key, port = extract_api_key(PAGE_URL)
        if port != 8282:
            api_url = f"{parsed.scheme}://{parsed.hostname}:{port}{API_PATH}"
            report["url"] = api_url
        body = _get(api_url, headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        })
        payload = json.loads(body)
        record = (payload.get("results") or [{}])[0]
        report["raw_response"] = record

        for api_field, col in FIELD_MAP.items():
            if api_field in record:
                if col == "Record Date":
                    report["record_date"] = record[api_field]
                    report["values"][col] = record[api_field]
                else:
                    report["values"][col] = record[api_field]
            else:
                report["values"][col] = None
                report["missing_columns"].append(col)
    except Exception as e:  # noqa: BLE001
        report["errors"].append(f"fatal: {type(e).__name__}: {safe_err(e, api_key)}")
        exit_code = 1
    finally:
        api_key = ""  # drop the reference promptly

    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    report["peak_rss_mb"] = round(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024), 1
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
