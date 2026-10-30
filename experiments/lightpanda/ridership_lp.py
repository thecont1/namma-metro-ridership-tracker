#!/usr/bin/env python
"""Lightpanda-over-CDP extractor for BMRCL ridership (experiment).

Mirrors ridership.py's flow: open the page, click the language toggle,
read the record date and the .features-card blocks, emit JSON to out/.
Never writes to the CSV. Exits non-zero if the date or a core value is
missing.
"""

import argparse
import json
import os
import re
import resource
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

EXPERIMENT_DIR = Path(__file__).resolve().parent
OUT_DIR = EXPERIMENT_DIR / "out"
REPO_ROOT = EXPERIMENT_DIR.parent.parent
URL = "https://english.bmrc.co.in/ridership/"

EXPECTED_COLUMNS = [
    'Record Date', 'Total Smart Cards', 'Stored Value Card',
    'One Day Pass', 'Three Day Pass', 'Five Day Pass',
    'Total Tokens', 'Total NCMC', 'Group Ticket',
    'Total QR', 'QR NammaMetro', 'QR WhatsApp', 'QR Paytm', 'QR ONDC'
]
CORE_COLUMNS = ['Total Smart Cards', 'Total Tokens', 'Total QR']

TOGGLE_SEL = ".link.top-navcustom-text"
CARD_SEL = ".features-card.achivement-area.bg-color"


def lightpanda_version(binary: Path) -> str:
    try:
        out = subprocess.run(
            [str(binary), "version"],
            capture_output=True, text=True, timeout=15,
            env={**os.environ, "LIGHTPANDA_DISABLE_TELEMETRY": "true"},
        )
        return out.stdout.strip() or out.stderr.strip()
    except Exception as e:  # noqa: BLE001 - report, don't crash
        return f"error: {e}"


def card_texts(page):
    return page.evaluate(
        """() => Array.from(
            document.querySelectorAll('.features-card.achivement-area.bg-color')
        ).map(e => e.innerText)"""
    )


def h3_texts(page):
    return page.evaluate(
        "() => Array.from(document.querySelectorAll('h3')).map(e => e.innerText)"
    )


def wait_for_cards(page, timeout_s, require_english=False):
    """Poll until cards with digits appear. Returns (texts, english_seen)."""
    deadline = time.monotonic() + timeout_s
    texts = []
    while time.monotonic() < deadline:
        try:
            texts = card_texts(page)
        except Exception:
            texts = []
        joined = "\n".join(texts)
        if re.search(r"\d", joined):
            if not require_english or re.search(
                r"Total|Tokens|Smart|QR|NCMC|Group", joined
            ):
                return texts, bool(
                    re.search(r"Total|Tokens|Smart|QR|NCMC|Group", joined)
                )
        time.sleep(0.5)
    return texts, False


def parse_cards(texts):
    """Parse 'Label: 1,234' lines the same way ridership.py does."""
    record = {}
    for card in texts:
        for line in card.split("\n"):
            # Lightpanda's innerText does not reproduce Chrome's space after
            # the colon ("Total Smart Cards:318626"), so split on ':' itself.
            label, sep, value = line.partition(":")
            if sep:
                label, value = label.strip(), value.strip()
                try:
                    record[label] = int(value.replace(",", ""))
                except ValueError:
                    record[label] = value
    return record


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cdp", default=os.environ.get("LP_CDP_URL", "ws://127.0.0.1:9223"))
    ap.add_argument("--lp-binary", default=str(REPO_ROOT / ".tools" / "lightpanda"))
    ap.add_argument("--poll-timeout", type=float, default=30.0)
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    started = time.monotonic()

    report = {
        "engine": "lightpanda",
        "lightpanda_version": lightpanda_version(Path(args.lp_binary)),
        "cdp_url": args.cdp,
        "run_utc": ts,
        "url": URL,
        "record_date": None,
        "values": {},
        "missing_columns": [],
        "raw_cards": [],
        "english_labels": None,
        "elapsed_seconds": None,
        "peak_rss_mb": None,
        "errors": [],
    }

    exit_code = 0
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(args.cdp)
            try:
                ctx = browser.contexts[0] if browser.contexts else browser.new_context()
                # Lightpanda exposes a placeholder STARTUP session page that has
                # no real target; always create a fresh target instead.
                page = ctx.new_page()
                page.goto(URL, wait_until="load", timeout=60000)

                # 1) wait for toggle in DOM (presence, not visibility)
                page.wait_for_selector(TOGGLE_SEL, state="attached", timeout=30000)

                # wait for initial data (Kannada render already carries digits)
                texts, _ = wait_for_cards(page, args.poll_timeout, require_english=False)

                # 2) click the language toggle (first match = language switch)
                clicked = False
                try:
                    page.locator(TOGGLE_SEL).first.click(timeout=10000)
                    clicked = True
                except Exception as e:  # noqa: BLE001
                    report["errors"].append(f"locator click failed: {e}")
                    try:
                        page.evaluate(
                            "document.querySelector('%s')?.click()" % TOGGLE_SEL
                        )
                        clicked = True
                    except Exception as e2:  # noqa: BLE001
                        report["errors"].append(f"js click failed: {e2}")
                report["toggle_clicked"] = clicked

                # 3) poll until English labels + digits appear (fallback: digits)
                texts, english = wait_for_cards(
                    page, args.poll_timeout, require_english=True
                )
                report["english_labels"] = english
                if not english:
                    texts, _ = wait_for_cards(page, 5.0, require_english=False)
                report["raw_cards"] = texts

                # 4) record date from first h3 containing a date
                for h in h3_texts(page):
                    if re.search(r"\d{2}-\d{2}-\d{4}", h):
                        report["record_date"] = re.search(
                            r"\d{2}-\d{2}-\d{4}", h
                        ).group(0)
                        break

                # 5) parse cards
                parsed = parse_cards(texts)
                if "Tokens" in parsed:
                    parsed["Total Tokens"] = parsed.pop("Tokens")
                for col in EXPECTED_COLUMNS:
                    if col == "Record Date":
                        report["values"][col] = report["record_date"]
                    elif col in parsed:
                        report["values"][col] = parsed[col]
                    else:
                        report["values"][col] = None
                        report["missing_columns"].append(col)

                (OUT_DIR / f"lightpanda_{ts}.html").write_text(
                    page.content(), encoding="utf-8"
                )
            finally:
                try:
                    page.close()
                except Exception:
                    pass
                try:
                    browser.close()
                except Exception:
                    pass
    except Exception as e:  # noqa: BLE001
        report["errors"].append(f"fatal: {type(e).__name__}: {e}")
        exit_code = 1

    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    report["peak_rss_mb"] = round(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024), 1
    )

    # exit non-zero if date or any core value missing
    if report["record_date"] is None:
        report["errors"].append("missing record date")
        exit_code = 1
    missing_core = [c for c in CORE_COLUMNS if report["values"].get(c) is None]
    if missing_core:
        report["errors"].append(f"missing core values: {missing_core}")
        exit_code = 1

    out_path = OUT_DIR / f"lightpanda_{ts}.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nwrote {out_path}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
