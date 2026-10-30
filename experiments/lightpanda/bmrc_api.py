"""Shared BMRCL ridership API client with self-healing discovery.

The site ships its API config (key, port, endpoint path) inside the
page's JS bundles. Instead of pinning any of those, this module
re-discovers them on every run from whatever bundle is currently
deployed:

  1. try the default endpoint unauthenticated (covers the site ever
     dropping or proxying auth)
  2. fetch the page's script bundles (ridership bundle first) and pull
     key candidates from a ladder of variable-name patterns
  3. extract the API port and endpoint path from the bundle rather than
     hardcoding them
  4. try every (path, key) combination until one returns a record
  5. normalize the response shape (results[0] / data / record / list)

So key rotation, bundle renames, variable renames, and endpoint renames
self-correct. A genuinely new auth mechanism (HMAC, OAuth, cookie flow)
or an unrecognizable response shape still fails — loudly, with an
attempts log that never contains the key material itself.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request

PAGE_URL = "https://english.bmrc.co.in/ridership/"
DEFAULT_API_PORT = 8282
DEFAULT_API_PATH = "/api/users/getridership"

# Canonical CSV column <- API response field
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
_NORM_FIELD_MAP = {
    re.sub(r"[^a-z0-9]", "", k.lower()): k for k in FIELD_MAP
}

# Variable-name ladder, most specific first
_KEY_VAR_PATTERNS = [
    r"API_KEY", r"api_key", r"apiKey", r"APIKEY",
    r"AUTH_TOKEN", r"ACCESS_TOKEN", r"BEARER_TOKEN",
    r"[Tt]oken", r"[Ss]ecret", r"[Kk]ey",
]
_RESPONSE_LIST_KEYS = ("results", "result", "data", "records", "items", "rows")


def _get(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def _script_urls(html, page_url):
    srcs = re.findall(r'<script[^>]+src="([^"]+)"', html)
    # also catch chunk URLs embedded in serialized state, not just <script src>
    srcs += re.findall(r'"(/_next/static/[^"]+\.js[^"]*)"', html)
    seen, out = set(), []
    for s in srcs:
        u = urllib.parse.urljoin(page_url, s)
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _key_candidates(js):
    cands = []
    for name in _KEY_VAR_PATTERNS:
        for m in re.finditer(
            name + r'[^0-9a-zA-Z]{1,40}["\']?([0-9a-fA-F]{24,64})["\']?', js
        ):
            cands.append((name, m.group(1)))
    seen, out = set(), []
    for c in cands:
        if c[1] not in seen:
            seen.add(c[1])
            out.append(c)
    return out[:8]  # bound auth attempts; generic names yield false hits


def _extract_port_and_prefix(js):
    # bundle computes BASE_API_URL as ...hostname + ":8282/api" — the
    # "/api" suffix is part of the base and must prefix extracted paths.
    m = re.search(r'":(\d+)(/[a-zA-Z0-9_-]+)', js)
    if m:
        return int(m.group(1)), m.group(2)
    return None, "/api"


def _extract_paths(js):
    """Endpoint paths concatenated onto the API base in the bundle."""
    paths = []
    for m in re.finditer(
        r'BASE_API_URL[^0-9a-zA-Z/]{1,20}\\?"(\\?/[a-zA-Z0-9_/-]+)\\?"', js
    ):
        paths.append(m.group(1).replace("\\/", "/"))
    if not paths:
        for m in re.finditer(r'"(/(?:api/)?[a-z]+/[a-zA-Z]+)"', js):
            paths.append(m.group(1))
    # prefer ridership-ish paths, keep discovery order otherwise
    paths.sort(key=lambda p: 0 if "rider" in p.lower() else 1)
    return paths


def _first_record(payload):
    if isinstance(payload, list):
        return payload[0] if payload and isinstance(payload[0], dict) else None
    if not isinstance(payload, dict):
        return None
    for k in _RESPONSE_LIST_KEYS:
        v = payload.get(k)
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return v[0]
        if isinstance(v, dict):
            return v
    normed = {re.sub(r"[^a-z0-9]", "", k.lower()) for k in payload}
    return payload if normed & set(_NORM_FIELD_MAP) else None


def _try(url, key, timeout):
    headers = {"Accept": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        payload = json.loads(_get(url, headers=headers, timeout=timeout))
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except (ValueError, urllib.error.URLError, TimeoutError) as e:
        return None, type(e).__name__
    return _first_record(payload), "ok"


def map_record(record):
    """Map an API record onto canonical CSV columns (fuzzy field match)."""
    norm = {re.sub(r"[^a-z0-9]", "", k.lower()): v for k, v in record.items()}
    return {
        FIELD_MAP[api_field]: norm[norm_key]
        for norm_key, api_field in _NORM_FIELD_MAP.items()
        if norm_key in norm
    }


def fetch_ridership(page_url=PAGE_URL, timeout=30):
    """Return (record, meta); raise RuntimeError with an attempts log.

    meta never contains key material — candidates are referenced by the
    variable-name pattern that produced them.
    """
    attempts = []
    parsed = urllib.parse.urlparse(page_url)
    origin = f"{parsed.scheme}://{parsed.hostname}"

    html = _get(page_url, timeout=timeout)
    srcs = _script_urls(html, page_url)
    srcs.sort(key=lambda s: 0 if "ridership" in s else 1)

    # walk bundles: ridership chunk first, extract port/paths/keys
    for src in srcs:
        try:
            js = _get(src, timeout=timeout)
        except Exception as e:  # noqa: BLE001
            attempts.append(f"bundle {src}: {type(e).__name__}")
            continue
        if not any(t in js for t in ("API_KEY", "BASE_API_URL", "ridership", "/api")):
            continue
        port, api_prefix = _extract_port_and_prefix(js)
        port = port or DEFAULT_API_PORT
        paths = _extract_paths(js) or [DEFAULT_API_PATH]
        keys = _key_candidates(js)
        attempts.append(
            f"bundle {src.rsplit('/',1)[-1]}: "
            f"{len(keys)} key candidate(s), paths={paths}, port={port}"
        )
        for path in paths:
            full = path if path.startswith(api_prefix) else api_prefix + path
            url = f"{origin}:{port}{full}"
            for name, key in keys:
                rec, why = _try(url, key, timeout)
                attempts.append(f"key({name}) {url}: {why}")
                if rec is not None:
                    return rec, {
                        "attempts": attempts,
                        "key_source": f"bundle var {name}",
                    }

    # last resort: unauthenticated default endpoint, in case the site
    # dropped or proxied auth (short timeout — it may hang, not 401)
    url = f"{origin}:{DEFAULT_API_PORT}{DEFAULT_API_PATH}"
    rec, why = _try(url, None, min(timeout, 15))
    attempts.append(f"no-auth {url}: {why}")
    if rec is not None:
        return rec, {"attempts": attempts, "key_source": "none (unauthenticated)"}

    raise RuntimeError(
        "all API candidates exhausted. " + " | ".join(attempts[-8:])
    )
