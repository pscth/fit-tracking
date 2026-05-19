#!/usr/bin/env python3
"""Daily Garmin Connect recovery summary: RHR / sleep / HRV / body battery / training readiness.

Slots into the daily diary "Snapshot" / "Recovery" sections. Uses cached
~/.garminconnect tokens — run `python3 scripts/garmin_auth.py` once
interactively first if not already authenticated.

Usage:
    python3 scripts/garmin_recovery.py              # today
    python3 scripts/garmin_recovery.py 2026-05-19   # specific date
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

try:
    from garminconnect import Garmin
except ImportError:
    sys.exit(
        "garminconnect not installed. Run:\n"
        "  python3 -m pip install --user -e ./python-garminconnect"
    )

TOKENSTORE = os.path.expanduser(os.getenv("GARMINTOKENS", "~/.garminconnect"))


def login() -> Garmin:
    g = Garmin()
    try:
        g.login(TOKENSTORE)
    except Exception as e:
        sys.exit(
            f"Token login failed ({e}).\n"
            "First-time auth: run `python3 scripts/garmin_auth.py` interactively."
        )
    return g


def safe(fn, *args, **kwargs):
    """Call a Garmin API method; return error sentinel on any failure."""
    try:
        result = fn(*args, **kwargs)
        return result if result is not None else {"_error": "no data"}
    except Exception as e:
        return {"_error": str(e)}


def is_err(x) -> bool:
    return isinstance(x, dict) and "_error" in x


def fmt_dur(seconds) -> str:
    if seconds is None:
        return "—"
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return "—"
    h, m = divmod(s // 60, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m"


def section(title: str) -> None:
    print(f"\n-- {title} --")


def kv(label: str, value, suffix: str = "") -> None:
    if value is None or value == "":
        value = "—"
    print(f"{label:<28}{value}{suffix}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("date", nargs="?", default=date.today().isoformat(),
                    help="Date YYYY-MM-DD (default today)")
    ap.add_argument("--raw", action="store_true",
                    help="Dump raw JSON responses (for debugging unknown shapes)")
    args = ap.parse_args()
    cdate = args.date

    g = login()

    # Fetch everything once
    tr = safe(g.get_training_readiness, cdate)
    rhr = safe(g.get_rhr_day, cdate)
    sleep = safe(g.get_sleep_data, cdate)
    hrv = safe(g.get_hrv_data, cdate)
    bb = safe(g.get_body_battery, cdate)

    if args.raw:
        print(json.dumps({
            "training_readiness": tr, "rhr": rhr, "sleep": sleep,
            "hrv": hrv, "body_battery": bb,
        }, indent=2, default=str))
        return

    print("=" * 72)
    print(f"  RECOVERY — {cdate}")
    print("=" * 72)

    # --- Training Readiness (composite 0-100) ---
    section("TRAINING READINESS (Garmin composite 0-100)")
    if isinstance(tr, list) and tr:
        tr = tr[0]
    if not is_err(tr) and isinstance(tr, dict):
        kv("Score:", tr.get("score"))
        kv("Level:", tr.get("level"))
        fb = tr.get("feedbackLong") or tr.get("feedbackShort")
        if fb:
            kv("Feedback:", fb)
    else:
        print(f"(unavailable: {tr.get('_error', 'unknown')})")

    # --- HRV ---
    section("HEART RATE VARIABILITY (overnight RMSSD, ms)")
    if not is_err(hrv) and isinstance(hrv, dict):
        summary = hrv.get("hrvSummary", {}) or {}
        kv("Last night avg:", summary.get("lastNightAvg"), " ms")
        kv("Last night 5-min high:", summary.get("lastNight5MinHigh"), " ms")
        kv("Weekly avg:", summary.get("weeklyAvg"), " ms")
        kv("Status:", summary.get("status"))
        kv("Baseline range:", f"{summary.get('baseline', {}).get('lowUpper', '—')}–{summary.get('baseline', {}).get('balancedUpper', '—')} ms")
    else:
        print(f"(unavailable: {hrv.get('_error', 'unknown') if is_err(hrv) else 'no hrvSummary'})")

    # --- Sleep ---
    section("SLEEP")
    if not is_err(sleep) and isinstance(sleep, dict):
        dto = sleep.get("dailySleepDTO", {}) or {}
        total = dto.get("sleepTimeSeconds")
        deep = dto.get("deepSleepSeconds")
        light = dto.get("lightSleepSeconds")
        rem = dto.get("remSleepSeconds")
        awake = dto.get("awakeSleepSeconds")
        scores = dto.get("sleepScores", {}) or {}
        overall = (scores.get("overall") or {}).get("value") if isinstance(scores.get("overall"), dict) else scores.get("overall")
        kv("Total:", fmt_dur(total))
        kv("Deep:", fmt_dur(deep))
        kv("Light:", fmt_dur(light))
        kv("REM:", fmt_dur(rem))
        kv("Awake:", fmt_dur(awake))
        kv("Score (0-100):", overall)
    else:
        print(f"(unavailable: {sleep.get('_error', 'unknown') if is_err(sleep) else 'no dailySleepDTO'})")

    # --- RHR ---
    section("RESTING HEART RATE")
    if not is_err(rhr) and isinstance(rhr, dict):
        # Garmin returns a structure with allMetrics → metricsMap → WELLNESS_RESTING_HEART_RATE
        metrics = (rhr.get("allMetrics") or {}).get("metricsMap") or {}
        rhr_list = metrics.get("WELLNESS_RESTING_HEART_RATE") or []
        if rhr_list:
            today_rhr = rhr_list[0].get("value")
            kv("Today:", today_rhr, " bpm")
        else:
            # Some responses surface RHR at top level
            kv("Today:", rhr.get("restingHeartRate"), " bpm")
    else:
        print(f"(unavailable: {rhr.get('_error', 'unknown')})")

    # --- Body Battery ---
    section("BODY BATTERY (Garmin composite 0-100)")
    if not is_err(bb):
        entry = bb[0] if isinstance(bb, list) and bb else bb
        if isinstance(entry, dict):
            values = entry.get("bodyBatteryValuesArray") or []
            levels = [v[1] for v in values if isinstance(v, list) and len(v) >= 2 and v[1] is not None]
            kv("Charged (overnight):", entry.get("charged"))
            kv("Drained (waking hours):", entry.get("drained"))
            kv("Highest today:", max(levels) if levels else None)
            kv("Lowest today:", min(levels) if levels else None)
            current = (entry.get("bodyBatteryDynamicFeedbackEvent") or {}).get("bodyBatteryLevel")
            kv("Current level:", current)
            for ev in entry.get("bodyBatteryActivityEvent") or []:
                kind = ev.get("eventType", "?")
                impact = ev.get("bodyBatteryImpact")
                fb = ev.get("shortFeedback", "")
                sign = "+" if isinstance(impact, (int, float)) and impact >= 0 else ""
                kv(f"  {kind.title()} impact:", f"{sign}{impact}", f"  ({fb})" if fb and fb != "NONE" else "")
    else:
        print(f"(unavailable: {bb.get('_error', 'unknown') if is_err(bb) else 'no data'})")

    print()
    print("(Re-run with --raw to dump full JSON responses for any field that shows '—')")


if __name__ == "__main__":
    main()
