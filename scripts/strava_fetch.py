#!/usr/bin/env python3
"""Strava API client: list recent activities, get activity detail.

Setup (one-time):
1. Register an API app at https://www.strava.com/settings/api
   - Set "Authorization Callback Domain" to `localhost`
   - Note the Client ID and Client Secret
2. Export the credentials (e.g. in ~/.zshenv):
       export STRAVA_CLIENT_ID="your-client-id"
       export STRAVA_CLIENT_SECRET="your-client-secret"
3. Run the OAuth dance once:
       python3 scripts/strava_fetch.py --auth
   Browser opens, you approve, tokens cache to ~/.fit-tracking/strava_tokens.json.

Usage:
    python3 scripts/strava_fetch.py recent              # 10 most recent activities
    python3 scripts/strava_fetch.py recent --n 30
    python3 scripts/strava_fetch.py <activity_id>       # detail for one activity
    python3 scripts/strava_fetch.py --auth              # rerun OAuth
"""

import argparse
import json
import os
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    from stravalib.client import Client
except ImportError:
    sys.exit("stravalib not installed. Run: python3 -m pip install --user -r requirements.txt")

CALLBACK_PORT = 8765
TOKEN_FILE = Path(os.path.expanduser("~/.fit-tracking/strava_tokens.json"))


def env_required(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        sys.exit(f"Missing env var {name}. See header of {__file__} for setup.")
    return val


def _catch_oauth_code(port: int) -> str:
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
    client_id = env_required("STRAVA_CLIENT_ID")
    client_secret = env_required("STRAVA_CLIENT_SECRET")
    redirect_uri = f"http://localhost:{CALLBACK_PORT}/callback"

    client = Client()
    auth_url = client.authorization_url(
        client_id=int(client_id),
        redirect_uri=redirect_uri,
        scope=["read", "activity:read_all", "profile:read_all"],
    )

    print("Opening browser to authorize Strava access...")
    print(f"If browser doesn't open, visit:\n  {auth_url}\n")
    webbrowser.open(auth_url)
    code = _catch_oauth_code(CALLBACK_PORT)

    print("Received code, exchanging for tokens...")
    tokens = client.exchange_code_for_token(
        client_id=int(client_id),
        client_secret=client_secret,
        code=code,
    )

    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2, default=str))
    print(f"Login successful. Tokens saved to {TOKEN_FILE}")


def load_tokens() -> dict:
    if not TOKEN_FILE.exists():
        sys.exit(f"No tokens at {TOKEN_FILE}. Run with --auth first.")
    return json.loads(TOKEN_FILE.read_text())


def get_client() -> Client:
    tokens = load_tokens()
    if int(time.time()) >= int(tokens.get("expires_at", 0)) - 60:
        client_id = env_required("STRAVA_CLIENT_ID")
        client_secret = env_required("STRAVA_CLIENT_SECRET")
        c = Client()
        refreshed = c.refresh_access_token(
            client_id=int(client_id),
            client_secret=client_secret,
            refresh_token=tokens["refresh_token"],
        )
        tokens.update(refreshed)
        TOKEN_FILE.write_text(json.dumps(tokens, indent=2, default=str))
    # Pass refresh_token + token_expires too so stravalib doesn't warn about
    # missing auto-refresh state (we manage refresh manually above, but the
    # library still wants these attributes set on the client).
    return Client(
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        token_expires=tokens.get("expires_at"),
    )


def cmd_recent(args) -> None:
    client = get_client()
    for a in client.get_activities(limit=args.n):
        date = a.start_date_local.strftime("%Y-%m-%d") if a.start_date_local else "?"
        km = float(a.distance) / 1000 if a.distance else 0
        elev = float(a.total_elevation_gain or 0)
        sport = a.sport_type or a.type or "?"
        print(f"  {a.id}  {date}  {str(sport):14}  {km:6.1f} km  {elev:5.0f} m  {a.moving_time}  {a.name}")


def cmd_activity(activity_id: int) -> None:
    client = get_client()
    a = client.get_activity(activity_id)
    km = float(a.distance) / 1000 if a.distance else 0
    print(f"Activity {a.id}: {a.name}")
    print(f"  Date:        {a.start_date_local}")
    print(f"  Sport:       {a.sport_type or a.type}")
    print(f"  Distance:    {km:.2f} km")
    print(f"  Elev gain:   {a.total_elevation_gain} m")
    print(f"  Moving time: {a.moving_time}")
    print(f"  Elapsed:     {a.elapsed_time}")
    print(f"  Avg power:   {a.average_watts} W")
    print(f"  Max power:   {a.max_watts} W")
    print(f"  Avg HR:      {a.average_heartrate}")
    print(f"  Max HR:      {a.max_heartrate}")
    print(f"  Avg cadence: {a.average_cadence}")
    print(f"  Calories:    {a.calories}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Strava API client")
    ap.add_argument("--auth", action="store_true", help="Run OAuth setup")
    ap.add_argument("target", nargs="?", help='"recent" or an activity ID')
    ap.add_argument("--n", type=int, default=10, help="With 'recent', number to list")
    args = ap.parse_args()

    if args.auth:
        auth_flow()
        return
    if not args.target:
        ap.print_help()
        return

    if args.target == "recent":
        cmd_recent(args)
    elif args.target.isdigit():
        cmd_activity(int(args.target))
    else:
        sys.exit(f"Unrecognized target: {args.target!r}. Use 'recent' or an activity ID.")


if __name__ == "__main__":
    main()
