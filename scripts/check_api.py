"""Check a SmartSolar API key and preview what the integration will parse.

Usage (the key is read from the environment so it never lands in shell history
or this repo):

    PowerShell:  $env:SMARTSOLAR_API_KEY = "<key>"; python scripts/check_api.py
    bash:        SMARTSOLAR_API_KEY=<key> python scripts/check_api.py

By default only the real-time status is fetched (1 request). Pass --all to also
fetch usage, faults and settings (5 requests total). Both stay far below the
API limit of 30 requests/minute.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://smartsolar.net.pk"
ROOT = Path(__file__).resolve().parent.parent

# Load parsing.py directly; importing the package would require Home Assistant.
_spec = importlib.util.spec_from_file_location(
    "smartsolar_parsing", ROOT / "custom_components" / "smartsolar" / "parsing.py"
)
parsing = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(parsing)


def call(api_key: str, path: str, params: dict[str, str] | None = None) -> dict:
    url = f"{BASE_URL}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url, headers={"X-API-KEY": api_key, "Accept": "application/json", "User-Agent": "smartsolar-ha-check"}
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as resp:
            status, body = resp.status, resp.read().decode()
    except urllib.error.HTTPError as err:
        status, body = err.code, err.read().decode(errors="replace")
    print(f"\n=== GET {path} {params or ''} -> HTTP {status}")
    try:
        payload = json.loads(body)
    except ValueError:
        print(body[:500])
        sys.exit(1)
    print(json.dumps(payload, indent=2))
    if "error" in payload:
        sys.exit(f"API error: {payload['error']}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true", help="also fetch usage, faults and settings")
    args = parser.parse_args()

    api_key = os.environ.get("SMARTSOLAR_API_KEY", "").strip()
    if not api_key:
        sys.exit("Set SMARTSOLAR_API_KEY first (see the top of this file).")

    status = call(api_key, "/api/inverter/status.php")["data"]
    print("\n--- Parsed status values ---")
    for field, value in status.items():
        numbers = parsing.parse_numbers(value)
        print(f"{field:20} {value!r:32} -> {numbers if numbers else parsing.parse_text(value)!r}")
    tz = datetime.now().astimezone().tzinfo
    print(f"{'Last_Update':20} -> {parsing.parse_last_update(status.get('Last_Update'), tz)}")

    if args.all:
        call(api_key, "/api/inverter/usage.php", {"period": "today"})
        call(api_key, "/api/inverter/usage.php", {"period": "this_month"})
        call(api_key, "/api/inverter/fault.php", {"period": "this_month"})
        settings = call(api_key, "/api/inverter/isetting.php")["data"]
        print("\n--- Settings: value -> matched option ---")
        for item in settings:
            matched = parsing.match_option(item.get("value"), item.get("options", []))
            flag = "" if matched else "   <-- NO MATCH"
            print(f"{item.get('key'):28} {item.get('value')!r:14} -> {matched!r}{flag}")


if __name__ == "__main__":
    main()
