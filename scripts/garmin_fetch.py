#!/usr/bin/env python3
"""Fetch a Garmin Connect activity file (FIT or TCX) into scripts/cache/.

Usage:
    python3 scripts/garmin_fetch.py latest [--n N] [--format fit|tcx]
    python3 scripts/garmin_fetch.py <activity_id> [--format fit|tcx]

Setup (once):
    1. python3 -m pip install --user -r requirements.txt
    2. Set env vars GARMIN_CONNECT_USER and GARMIN_CONNECT_PWD in ~/.zshenv
    3. Run `python3 scripts/garmin_auth.py` once interactively to cache the
       OAuth tokens at ~/.garminconnect/garmin_tokens.json (handles MFA prompt).
       Subsequent runs are unattended.

Pipe to analyze_fit.py:
    python3 scripts/analyze_fit.py "$(python3 scripts/garmin_fetch.py latest)"
"""

import argparse
import io
import os
import sys
import zipfile
from pathlib import Path

try:
    from garminconnect import Garmin
except ImportError:
    sys.exit(
        "garminconnect not installed. Run:\n"
        "  python3 -m pip install --user -e ./python-garminconnect"
    )

CACHE_DIR = Path(__file__).parent / "cache"
TOKENSTORE = os.path.expanduser(os.getenv("GARMINTOKENS", "~/.garminconnect"))


def login() -> Garmin:
    g = Garmin()
    try:
        g.login(TOKENSTORE)
    except Exception as e:
        sys.exit(
            f"Token login failed ({e}).\n"
            "First-time auth required: run `python3 scripts/garmin_auth.py` "
            "interactively to handle MFA and cache tokens."
        )
    return g


def fetch(g: Garmin, activity_id: str, fmt: str) -> Path:
    activity_id = str(activity_id)
    if fmt == "fit":
        # ORIGINAL returns a zipped FIT
        zipped = g.download_activity(
            activity_id, dl_fmt=Garmin.ActivityDownloadFormat.ORIGINAL
        )
        with zipfile.ZipFile(io.BytesIO(zipped)) as zf:
            fit_names = [n for n in zf.namelist() if n.lower().endswith(".fit")]
            if not fit_names:
                sys.exit(f"No .fit file inside Garmin download for activity {activity_id}")
            payload = zf.read(fit_names[0])
        ext = "fit"
    elif fmt == "tcx":
        payload = g.download_activity(
            activity_id, dl_fmt=Garmin.ActivityDownloadFormat.TCX
        )
        ext = "tcx"
    else:
        sys.exit(f"Unknown format: {fmt}")

    CACHE_DIR.mkdir(exist_ok=True)
    out = CACHE_DIR / f"{activity_id}.{ext}"
    out.write_bytes(payload)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target", help='Activity ID, or "latest" for most recent')
    ap.add_argument(
        "--n", type=int, default=1, help="With 'latest', fetch N most recent (default 1)"
    )
    ap.add_argument("--format", choices=["fit", "tcx"], default="fit")
    args = ap.parse_args()

    g = login()

    if args.target == "latest":
        acts = g.get_activities(start=0, limit=args.n)
        if not acts:
            sys.exit("No activities returned.")
        for a in acts:
            aid = a.get("activityId")
            name = a.get("activityName", "")
            date = (a.get("startTimeLocal", "") or "")[:10]
            out = fetch(g, aid, args.format)
            # path first so the line is pipe-friendly; comment trails
            print(f"{out}  # {date} {name} (id {aid})")
    else:
        out = fetch(g, args.target, args.format)
        print(str(out))


if __name__ == "__main__":
    main()
