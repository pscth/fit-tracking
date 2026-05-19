#!/usr/bin/env python3
"""First-time Garmin Connect authentication.

Logs in to Garmin Connect using GARMIN_CONNECT_USER / GARMIN_CONNECT_PWD env
vars, prompts for an MFA code if your account has it enabled, and caches OAuth
tokens to ~/.garminconnect/garmin_tokens.json. After running this once, the
other garmin_*.py scripts can run unattended (tokens auto-refresh).

Must be run interactively (real TTY) so the MFA prompt works. If your tokens
expire or get invalidated, rerun this script to refresh them.

Usage:
    python3 scripts/garmin_auth.py
"""

import os
import sys
from pathlib import Path

try:
    from garminconnect import Garmin
except ImportError:
    sys.exit(
        "garminconnect not installed. Run:\n"
        "  python3 -m pip install --user -r requirements.txt"
    )

TOKENSTORE = os.path.expanduser(os.getenv("GARMINTOKENS", "~/.garminconnect"))


def main() -> None:
    user = os.environ.get("GARMIN_CONNECT_USER")
    pwd = os.environ.get("GARMIN_CONNECT_PWD")
    if not user or not pwd:
        sys.exit(
            "Missing env vars GARMIN_CONNECT_USER / GARMIN_CONNECT_PWD.\n"
            "Set them in ~/.zshenv (see README) then re-run this script."
        )

    # Try cached tokens first — skip credential auth if they're still valid.
    try:
        g = Garmin()
        g.login(TOKENSTORE)
        print(f"Already authenticated. Tokens at {TOKENSTORE} are valid.")
        return
    except Exception:
        pass

    print("No valid cached tokens — running fresh login...")
    g = Garmin(
        email=user,
        password=pwd,
        prompt_mfa=lambda: input("MFA code: ").strip(),
    )
    g.login(TOKENSTORE)
    print(f"Login successful. Tokens saved to {TOKENSTORE}")


if __name__ == "__main__":
    main()
