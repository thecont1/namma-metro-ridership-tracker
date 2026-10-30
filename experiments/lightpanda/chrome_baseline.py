#!/usr/bin/env python
"""Chrome/Selenium baseline extractor for the Lightpanda experiment.

Replicates ridership.py's Selenium flow but writes JSON to out/ instead
of appending to the CSV. Kept standalone because ridership.py writes the
CSV on import.
"""

import json
import os
import resource
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

EXPERIMENT_DIR = Path(__file__).resolve().parent
OUT_DIR = EXPERIMENT_DIR / "out"
URL = "https://english.bmrc.co.in/ridership/"

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
        "engine": "chrome",
        "chrome_version": None,
        "run_utc": ts,
        "url": URL,
        "record_date": None,
        "values": {},
        "missing_columns": [],
        "raw_cards": [],
        "elapsed_seconds": None,
        "peak_rss_mb": None,
        "errors": [],
    }

    options = Options()
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--incognito")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/110.0.5481.77 Safari/537.37"
    )

    driver = None
    exit_code = 0
    try:
        driver = webdriver.Chrome(options=options)
        report["chrome_version"] = driver.capabilities.get("browserVersion")
        wait = WebDriverWait(driver, 20)

        driver.get(URL)

        toggle = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".link.top-navcustom-text"))
        )
        time.sleep(10)  # same fixed sleep as ridership.py
        toggle.click()

        record_date_el = wait.until(
            EC.visibility_of_element_located((By.TAG_NAME, "h3"))
        )
        report["record_date"] = record_date_el.text.split()[-1]

        data_points = wait.until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, ".features-card.achivement-area.bg-color")
            )
        )
        report["raw_cards"] = [el.text for el in data_points]

        parsed = {}
        for card in data_points:
            for line in card.text.split("\n"):
                parts = line.split(": ")
                if len(parts) == 2:
                    try:
                        parsed[parts[0]] = int(parts[1].replace(",", ""))
                    except ValueError:
                        parsed[parts[0]] = parts[1]
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

        (OUT_DIR / f"chrome_{ts}.html").write_text(
            driver.page_source, encoding="utf-8"
        )
    except Exception as e:  # noqa: BLE001
        report["errors"].append(f"fatal: {type(e).__name__}: {e}")
        exit_code = 1
    finally:
        if driver is not None:
            driver.quit()

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

    out_path = OUT_DIR / f"chrome_{ts}.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nwrote {out_path}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
