#!/usr/bin/env python3
"""Withings API client: weight, body composition, sleep summary.

Minimal client written directly against the Withings REST API (no third-party
Withings library — the well-maintained ones pin pydantic <2 and conflict with
stravalib).

Setup (one-time):
1. Register a developer app at https://developer.withings.com/dashboard/
   - Set "Callback URI" to http://localhost:8765/callback
   - Note the Client ID and Consumer Secret
2. Export the credentials (e.g. in ~/.zshenv):
       export WITHINGS_CLIENT_ID="your-client-id"
       export WITHINGS_CLIENT_SECRET="your-client-secret"
3. Run the OAuth dance once:
       python3 scripts/withings_fetch.py --auth
   Browser opens, you approve, tokens cache to ~/.fit-tracking/withings_tokens.json.

Usage:
    python3 scripts/withings_fetch.py weight                 # latest morning weight
    python3 scripts/withings_fetch.py weight --days 7        # last 7 days
    python3 scripts/withings_fetch.py body --days 7          # weight + BF% + lean + fat
    python3 scripts/withings_fetch.py sleep [YYYY-MM-DD]     # sleep summary for date
    python3 scripts/withings_fetch.py --auth                 # rerun OAuth setup
"""

import argparse
import json
import os
import sys
import time
import webbrowser
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

API_BASE = "https://wbsapi.withings.net"
AUTH_BASE = "https://account.withings.com"
CALLBACK_PORT = 8765
CALLBACK_PATH = "/callback"
TOKEN_FILE = Path(os.path.expanduser("~/.fit-tracking/withings_tokens.json"))

# Withings measurement types
TYPE_WEIGHT, TYPE_FAT_FREE, TYPE_BF_PCT, TYPE_FAT_MASS, TYPE_MUSCLE = 1, 5, 6, 8, 76


def env_required(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        sys.exit(f"Missing env var {name}. See header of {__file__} for setup.")
    return val


def _catch_oauth_code(port: int) -> str:
    """Spin up a one-shot HTTP server to catch the OAuth redirect, return the code."""
    code_holder: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            q = parse_qs(urlparse(self.path).query)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            if "code" in q:
                code_holder["code"] = q["code"][0]
                self.wfile.write(b"Authorization successful. You can close this window.")
            else:
                self.wfile.write(b"No code in callback.")

        def log_message(self, *_):
            pass

    server = HTTPServer(("localhost", port), Handler)
    while "code" not in code_holder:
        server.handle_request()
    server.server_close()
    return code_holder["code"]


def auth_flow() -> None:
    client_id = env_required("WITHINGS_CLIENT_ID")
    client_secret = env_required("WITHINGS_CLIENT_SECRET")
    redirect_uri = f"http://localhost:{CALLBACK_PORT}{CALLBACK_PATH}"
    auth_url = f"{AUTH_BASE}/oauth2_user/authorize2?" + urlencode({
        "response_type": "code",
        "client_id": client_id,
        "scope": "user.metrics,user.activity,user.sleepevents",
        "redirect_uri": redirect_uri,
        "state": str(int(time.time())),
    })

    print("Opening browser to authorize Withings access...")
    print(f"If browser doesn't open, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)
    code = _catch_oauth_code(CALLBACK_PORT)

    print("Received authorization code, exchanging for tokens...")
    resp = requests.post(f"{API_BASE}/v2/oauth2", data={
        "action": "requesttoken",
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }, timeout=15)
    data = resp.json()
    if data.get("status") != 0:
        sys.exit(f"Token exchange failed: {data}")

    body = data["body"]
    tokens = {
        "access_token": body["access_token"],
        "refresh_token": body["refresh_token"],
        "expires_at": int(time.time()) + body["expires_in"],
        "userid": body.get("userid"),
    }
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2))
    print(f"Login successful. Tokens saved to {TOKEN_FILE}")


def load_tokens() -> dict:
    if not TOKEN_FILE.exists():
        sys.exit(f"No tokens at {TOKEN_FILE}. Run with --auth first.")
    return json.loads(TOKEN_FILE.read_text())


def refresh_if_needed(tokens: dict) -> dict:
    if int(time.time()) < tokens["expires_at"] - 60:
        return tokens
    client_id = env_required("WITHINGS_CLIENT_ID")
    client_secret = env_required("WITHINGS_CLIENT_SECRET")
    resp = requests.post(f"{API_BASE}/v2/oauth2", data={
        "action": "requesttoken",
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": tokens["refresh_token"],
    }, timeout=15).json()
    if resp.get("status") != 0:
        sys.exit(f"Token refresh failed: {resp}")
    b = resp["body"]
    tokens.update({
        "access_token": b["access_token"],
        "refresh_token": b["refresh_token"],
        "expires_at": int(time.time()) + b["expires_in"],
    })
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2))
    return tokens


def api_post(tokens: dict, path: str, params: dict) -> dict:
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = requests.post(f"{API_BASE}{path}", headers=headers, data=params, timeout=15).json()
    if resp.get("status") != 0:
        sys.exit(f"API error on {path}: {resp}")
    return resp["body"]


def get_measurements(tokens: dict, meastypes: str, start: datetime, end: datetime) -> dict:
    return api_post(tokens, "/measure", {
        "action": "getmeas",
        "meastype": meastypes,
        "startdate": int(start.timestamp()),
        "enddate": int(end.timestamp()),
        "category": "1",
    })


def _val(m: dict) -> float:
    return m["value"] * (10 ** m["unit"])


def cmd_weight(tokens: dict, args) -> None:
    end = datetime.now()
    start = end - timedelta(days=args.days)
    body = get_measurements(tokens, str(TYPE_WEIGHT), start, end)
    grps = body.get("measuregrps", [])
    print(f"Weight readings — last {args.days} day(s):")
    for grp in sorted(grps, key=lambda g: g["date"]):
        ts = datetime.fromtimestamp(grp["date"])
        for m in grp["measures"]:
            if m["type"] == TYPE_WEIGHT:
                print(f"  {ts.isoformat()}  {_val(m):.2f} kg")


def cmd_body(tokens: dict, args) -> None:
    end = datetime.now()
    start = end - timedelta(days=args.days)
    types = f"{TYPE_WEIGHT},{TYPE_FAT_FREE},{TYPE_BF_PCT},{TYPE_FAT_MASS},{TYPE_MUSCLE}"
    body = get_measurements(tokens, types, start, end)
    print(f"Body composition — last {args.days} day(s):")
    for grp in sorted(body.get("measuregrps", []), key=lambda g: g["date"]):
        ts = datetime.fromtimestamp(grp["date"]).strftime("%Y-%m-%d %H:%M")
        out = {}
        for m in grp["measures"]:
            v = _val(m)
            label = {
                TYPE_WEIGHT: "weight_kg",
                TYPE_BF_PCT: "bf_pct",
                TYPE_FAT_FREE: "lean_kg",
                TYPE_FAT_MASS: "fat_kg",
                TYPE_MUSCLE: "muscle_kg",
            }.get(m["type"])
            if label:
                out[label] = round(v, 2)
        if out:
            print(f"  {ts}  {out}")


def cmd_sleep(tokens: dict, args) -> None:
    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    target = datetime.fromisoformat(date_str).date()
    body = api_post(tokens, "/v2/sleep", {
        "action": "getsummary",
        "startdateymd": (target - timedelta(days=1)).isoformat(),
        "enddateymd": (target + timedelta(days=1)).isoformat(),
        "data_fields": "deepsleepduration,lightsleepduration,remsleepduration,wakeupduration,wakeupcount,sleep_score",
    })
    series = body.get("series", [])
    if not series:
        print(f"No sleep data near {date_str}")
        return
    print(f"Sleep summaries near {date_str}:")
    for s in series:
        d = s.get("date", "?")
        sd = s.get("data", {})
        deep_m = sd.get("deepsleepduration", 0) / 60
        light_m = sd.get("lightsleepduration", 0) / 60
        rem_m = sd.get("remsleepduration", 0) / 60
        wake_m = sd.get("wakeupduration", 0) / 60
        total_h = (deep_m + light_m + rem_m) / 60
        print(f"  {d}: total {total_h:.1f}h  deep {deep_m:.0f}m  light {light_m:.0f}m  "
              f"REM {rem_m:.0f}m  awake {wake_m:.0f}m  score {sd.get('sleep_score')}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Withings API client")
    ap.add_argument("--auth", action="store_true", help="Run OAuth setup")
    sub = ap.add_subparsers(dest="cmd")
    p_weight = sub.add_parser("weight", help="Recent weight readings")
    p_weight.add_argument("--days", type=int, default=1)
    p_body = sub.add_parser("body", help="Body composition (weight + body fat + lean + fat)")
    p_body.add_argument("--days", type=int, default=7)
    p_sleep = sub.add_parser("sleep", help="Sleep summary")
    p_sleep.add_argument("date", nargs="?", help="YYYY-MM-DD (default today)")
    args = ap.parse_args()

    if args.auth:
        auth_flow()
        return
    if not args.cmd:
        ap.print_help()
        return

    tokens = refresh_if_needed(load_tokens())
    {"weight": cmd_weight, "body": cmd_body, "sleep": cmd_sleep}[args.cmd](tokens, args)


if __name__ == "__main__":
    main()
