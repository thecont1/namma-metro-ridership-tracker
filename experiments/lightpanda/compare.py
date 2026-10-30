#!/usr/bin/env python
"""Compare the latest (or given) Lightpanda and Chrome run JSONs.

Diffs values field by field, reports timing/memory, reconciles component
totals, writes out/compare_<ts>.json, and appends a row to the runs table
in REPORT.md.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
OUT_DIR = EXPERIMENT_DIR / "out"
REPORT = EXPERIMENT_DIR / "REPORT.md"

EXPECTED_COLUMNS = [
    'Record Date', 'Total Smart Cards', 'Stored Value Card',
    'One Day Pass', 'Three Day Pass', 'Five Day Pass',
    'Total Tokens', 'Total NCMC', 'Group Ticket',
    'Total QR', 'QR NammaMetro', 'QR WhatsApp', 'QR Paytm', 'QR ONDC'
]

RECONCILIATIONS = {
    "Total Smart Cards == SVC+1d+3d+5d":
        lambda v: v["Total Smart Cards"] == (
            v["Stored Value Card"] + v["One Day Pass"]
            + v["Three Day Pass"] + v["Five Day Pass"]
        ),
    "Total QR == NammaMetro+WhatsApp+Paytm+ONDC":
        lambda v: v["Total QR"] == (
            v["QR NammaMetro"] + v["QR WhatsApp"]
            + v["QR Paytm"] + v["QR ONDC"]
        ),
}


def latest(pattern):
    files = sorted(OUT_DIR.glob(pattern))
    return files[-1] if files else None


def load(path):
    return json.loads(Path(path).read_text())


def engver(report):
    return (
        report.get("engine_version")
        or report.get("lightpanda_version")
        or report.get("chrome_version")
        or "?"
    )


def reconcile(values):
    results = {}
    if any(values.get(c) is None for c in EXPECTED_COLUMNS[1:]):
        return {name: "skipped (missing cols)" for name in RECONCILIATIONS}
    for name, check in RECONCILIATIONS.items():
        try:
            results[name] = "ok" if check(values) else "MISMATCH"
        except Exception as e:  # noqa: BLE001
            results[name] = f"error: {e}"
    return results


def main():
    lp_path = Path(sys.argv[1]) if len(sys.argv) > 1 else latest("lightpanda_*.json")
    ch_path = Path(sys.argv[2]) if len(sys.argv) > 2 else latest("chrome_*.json")
    if not lp_path or not ch_path:
        sys.exit("need a lightpanda_*.json and a chrome_*.json in out/")

    lp, ch = load(lp_path), load(ch_path)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    matching, mismatching, missing = [], [], []
    for col in EXPECTED_COLUMNS:
        lv, cv = lp["values"].get(col), ch["values"].get(col)
        if lv is None or cv is None:
            missing.append({"column": col, "lightpanda": lv, "chrome": cv})
        elif lv == cv:
            matching.append(col)
        else:
            mismatching.append({"column": col, "lightpanda": lv, "chrome": cv})

    date_match = lp["record_date"] == ch["record_date"]

    result = {
        "compare_utc": ts,
        "engine_a": lp.get("engine"),
        "engine_b": ch.get("engine"),
        "file_a": str(lp_path.name),
        "file_b": str(ch_path.name),
        "version_a": engver(lp),
        "version_b": engver(ch),
        "record_dates": {lp.get("engine", "a"): lp["record_date"], ch.get("engine", "b"): ch["record_date"], "match": date_match},
        "matching": matching,
        "mismatching": mismatching,
        "missing": missing,
        "timing": {
            "a_s": lp["elapsed_seconds"],
            "b_s": ch["elapsed_seconds"],
            "speedup": round(ch["elapsed_seconds"] / lp["elapsed_seconds"], 2)
            if lp["elapsed_seconds"] else None,
        },
        "peak_rss_mb": {
            "a": lp["peak_rss_mb"],
            "b": ch["peak_rss_mb"],
        },
        "reconciliation": {
            lp.get("engine", "a"): reconcile(lp["values"]),
            ch.get("engine", "b"): reconcile(ch["values"]),
        },
        "errors": {lp.get("engine", "a"): lp["errors"], ch.get("engine", "b"): ch["errors"]},
        "verdict": (
            "MATCH" if date_match and not mismatching and not missing
            else "DIVERGED"
        ),
    }

    out_path = OUT_DIR / f"compare_{ts}.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # append a row to REPORT.md runs table
    if REPORT.exists():
        row = (
            f"| {ts} | {lp.get('engine','?')} {engver(lp)} | {ch.get('engine','?')} {engver(ch)} "
            f"| {result['verdict']} | {len(matching)}/{len(EXPECTED_COLUMNS)} "
            f"| {len(mismatching)} | {len(missing)} "
            f"| {lp['elapsed_seconds']}s | {ch['elapsed_seconds']}s "
            f"| {result['timing']['speedup']}x | {lp['peak_rss_mb']} | {ch['peak_rss_mb']} |\n"
        )
        text = REPORT.read_text()
        if "<!-- runs -->" in text:
            text = text.replace("<!-- runs -->", row + "<!-- runs -->")
            REPORT.write_text(text)
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
