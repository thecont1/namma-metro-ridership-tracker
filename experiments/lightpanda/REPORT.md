# Lightpanda trial — namma-metro-ridership-tracker

Experiment branch: `experiment/lightpanda`. No changes to `ridership.py`,
the CSV, or the GitHub Actions workflow.

- Lightpanda binary: `.tools/lightpanda` (`1.1.0-nightly.11326+948d77378`,
  nightly aarch64-macos)
- CDP endpoint used: `ws://127.0.0.1:9223` (9222 was occupied locally)
- Client: `playwright` 1.64.1 (dev dependency, `connect_over_cdp`, no
  browser download)
- Baseline: Chrome 156.0.8078.73 via Selenium (`chrome_baseline.py`,
  same options as `ridership.py`)

## Runs

| run (UTC) | engine A | engine B | verdict | fields matched | mismatches | missing | A time | B time | speedup | A rss MB | B rss MB |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 20261030T165409Z | 1.1.0-nightly.11326+948d77378 | 156.0.8078.73 | MATCH | 14/14 | 0 | 0 | 3.39s | 16.185s | 4.77x | 44.0 | 47.6 |
| 20261030T165439Z | 1.1.0-nightly.11326+948d77378 | 156.0.8078.73 | MATCH | 14/14 | 0 | 0 | 3.378s | 12.581s | 3.72x | 54.2 | 48.8 |
| 20261030T165458Z | 1.1.0-nightly.11326+948d77378 | 156.0.8078.73 | MATCH | 14/14 | 0 | 0 | 2.692s | 13.087s | 4.86x | 55.5 | 45.4 |
| 20261030T165523Z | 1.1.0-nightly.11326+948d77378 | 156.0.8078.73 | MATCH | 14/14 | 0 | 0 | 8.719s | 12.931s | 1.48x | 49.3 | 54.1 |
| 20261030T165548Z | 1.1.0-nightly.11326+948d77378 | 156.0.8078.73 | MATCH | 14/14 | 0 | 0 | 8.597s | 12.803s | 1.49x | 54.3 | 53.9 |
| 20261030T191246Z | api unversioned-json-endpoint | chrome 156.0.8078.73 | MATCH | 14/14 | 0 | 0 | 1.655s | 12.803s | 7.74x | 37.4 | 53.9 |
<!-- runs -->

5/5 paired runs, all 14 expected columns identical, zero missing, zero
mismatches. Component totals reconcile on both engines
(Smart Cards = SVC+1d+3d+5d; Total QR = NammaMetro+WhatsApp+Paytm+ONDC).

Note: all runs happened on the same day against the same record
(`22-10-2026`). They prove stability, not day-to-day data variance — a
multi-day soak is still open follow-up work.

## How to reproduce

```sh
# terminal 1
LIGHTPANDA_DISABLE_TELEMETRY=true .tools/lightpanda serve --host 127.0.0.1 --port 9223
# terminal 2
uv run python experiments/lightpanda/api_fetch.py       # browser-free route
uv run python experiments/lightpanda/ridership_lp.py
uv run python experiments/lightpanda/chrome_baseline.py
uv run python experiments/lightpanda/compare.py [a.json b.json]  # appends a row above
```

## Findings

### What works

- `lightpanda serve` speaks enough CDP for Playwright's
  `connect_over_cdp` — `goto`, `wait_for_selector`, `locator.click`,
  `evaluate`, `page.content()` all work. No driver binary needed.
- The language toggle click works; English labels render. Numbers were
  already in the DOM in Kannada before the click.
- Fast: ~3s typical end-to-end vs Chrome's ~13-16s (which includes the
  fixed 10s `time.sleep` in the Selenium flow). Best case 4.9x.
- Light footprint: single ~10MB idle server process, ~120MB with a page
  loaded, vs Chrome's multi-process tree (several hundred MB).
- Failures are diagnosable: every run saves `page.content()` HTML plus a
  JSON record with raw card text, missing columns, and errors.

### Gotchas found (all handled in `ridership_lp.py`)

- **STARTUP session page**: the first page Playwright sees has "no real
  target" — `Page.navigate` fails. Must call `ctx.new_page()`.
- **`innerText` whitespace**: Lightpanda renders `"Total Smart Cards:318626"`
  while Chrome produces `"Total Smart Cards: 318626"`. `split(": ")` (what
  `ridership.py` does) silently loses fields under Lightpanda — the
  extractor splits on `:` instead. This is exactly the kind of subtle
  engine divergence that the zero-fill bug would have hidden.
- **Slow runs**: two runs took ~8.6s instead of ~3s; matched site-side
  latency, not a Lightpanda fault (Chrome stayed ~13s). Server restart
  restored ~2.7s.
- **Server RSS growth**: ~7MB retained per page even after `page.close()`
  (`/json/list` shows 0 lingering targets — allocator retention, not live
  pages). Irrelevant for a single-shot CI job, but a long-lived server
  would want periodic restarts.
- Port 9222 was already in use locally; the script defaults to
  `LP_CDP_URL`/`--cdp` `ws://127.0.0.1:9223`.

### Bigger discovery: a browser-free route exists

The page is a Next.js app that fetches its data from a plain JSON API at
`<scheme>://<host>:8282/api/users/getridership`, gated by an
`Authorization: Bearer` token that is shipped publicly in the site's own
JS bundle (`/_next/static/chunks/pages/ridership.js` → `configconst.js`
`API_KEY`). Every visitor's browser sends it; it is not a credential
leak — but per project policy the token is **not committed to this repo,
printed to logs, or recorded in this report**. `api_fetch.py` extracts it
from the bundle at run time.

The response is `{"success":"success","results":[{...}]}` where the
record's field names map 1:1 onto `EXPECTED_COLUMNS`
(`RidershipDate`→`Record Date`, `Tokens`→`Total Tokens`,
`QRNammaMetro`→`QR NammaMetro`, `ONDC`→`QR ONDC`; `TotalPassengers` is
extra). Every value matches both browser engines' output exactly.

## Recommendation

**Go for the API route first, Lightpanda second, Chrome last.**

On the plan's own gate, Lightpanda qualifies: 5/5 runs match Chrome
field-for-field, nothing is silently zero-filled (missing → `null` +
`missing_columns`), failures are diagnosable from saved HTML/JSON, and CI
setup collapses to a single ~90MB binary download instead of Chrome +
chromedriver + selenium-manager. A `--browser lightpanda` switch with
Chrome fallback is justified on the evidence.

However, the JSON endpoint makes *any* browser unnecessary for this
scrape: no toggle click, no language dependency, no JS engine quirks, no
headless process at all — `curl` or `urllib` returns clean typed data in
~200ms. The pragmatic proposal is a three-tier fetch:

1. `fetch via JSON API` — implemented in `api_fetch.py`; extracts the
   site's public token from its JS bundle at run time (never committed,
   logged, or persisted)
2. `--browser lightpanda` fallback if the API shape or auth changes
3. `--browser chrome` kept as the last-resort fallback

Risks to carry forward:

- The API token could be rotated or the endpoint changed at any time —
  same brittleness class as CSS selectors, with cleaner failure modes.
- Lightpanda nightly is pre-release software; pin the binary version in
  CI and expect occasional JS-edge-case breakage on a site like this
  (Next.js *dev build* in production).
- Multi-day soak still pending: re-run `compare.py` over 5 consecutive
  days before merging any workflow change.

### Proposed PR (not applied — Phase 6 requires approval first)

- Add `--source api|lightpanda|chrome` to `ridership.py` (default `api`
  with fallback chain), keeping CSV write logic untouched.
- Workflow downloads the pinned Lightpanda binary
  (`lightpanda-x86_64-linux`) only when the fallback chain needs it.
- Keep `LIGHTPANDA_DISABLE_TELEMETRY=true` everywhere.
- Apply the zero-fill validity fix (separate commit on this branch).
