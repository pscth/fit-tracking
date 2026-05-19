#!/usr/bin/env python3
"""Fully unattended morning diary entry.

Pulls today's data from Garmin Connect (recovery + activities) and Withings
(weight + body comp + sleep), runs ride analysis if a ride is present, then
composes a structured Markdown diary entry and writes it to `diary/YYYY-MM-DD.md`.

Designed for cron / launchd: no interactive prompts, no hard failures when a
data source is unavailable (sections degrade gracefully).

Usage:
    python3 scripts/daily.py                # today's entry to diary/YYYY-MM-DD.md
    python3 scripts/daily.py 2026-05-19     # specific date
    python3 scripts/daily.py --dry-run      # print to stdout, don't write
    python3 scripts/daily.py --force        # overwrite existing entry
    python3 scripts/daily.py --no-ride      # skip ride fetch + analysis

Setup: completes the standalone Garmin + Withings auth setup once (see README).
Falls back gracefully if any source isn't configured.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    import requests
    from garminconnect import Garmin
except ImportError as e:
    sys.exit(f"Missing dependency: {e}. Run: python3 -m pip install --user -r requirements.txt")

SCRIPTS_DIR = Path(__file__).parent
REPO_ROOT = SCRIPTS_DIR.parent
DIARY_DIR = REPO_ROOT / "diary"
CACHE_DIR = SCRIPTS_DIR / "cache"
ATHLETE_JSON_PATH = SCRIPTS_DIR / "athlete.json"
GARMIN_TOKENS = os.path.expanduser("~/.garminconnect")
WITHINGS_TOKEN_FILE = Path(os.path.expanduser("~/.fit-tracking/withings_tokens.json"))
WITHINGS_API_BASE = "https://wbsapi.withings.net"


# ----------------------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------------------

def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def safe_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        return {"_error": str(e)}


def fmt_dur(seconds) -> str:
    if seconds is None:
        return "—"
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return "—"
    h, m = divmod(s // 60, 60)
    return f"{h}h{m:02d}m" if h else f"{m}m"


def load_athlete() -> dict:
    if not ATHLETE_JSON_PATH.exists():
        return {}
    try:
        return json.loads(ATHLETE_JSON_PATH.read_text())
    except Exception:
        return {}


# ----------------------------------------------------------------------------
# Garmin
# ----------------------------------------------------------------------------

def garmin_login():
    g = Garmin()
    g.login(GARMIN_TOKENS)
    return g


def fetch_recovery(g, cdate: str) -> dict:
    return {
        "training_readiness": safe_call(g.get_training_readiness, cdate),
        "rhr": safe_call(g.get_rhr_day, cdate),
        "sleep": safe_call(g.get_sleep_data, cdate),
        "hrv": safe_call(g.get_hrv_data, cdate),
        "body_battery": safe_call(g.get_body_battery, cdate),
    }


def fetch_activities(g, n: int = 20) -> list:
    try:
        result = g.get_activities(start=0, limit=n)
        return result if isinstance(result, list) else []
    except Exception:
        return []


def find_today_ride(activities: list, target_date: str) -> dict | None:
    for a in activities:
        start_local = (a.get("startTimeLocal") or "")[:10]
        sport = ((a.get("activityType") or {}).get("typeKey") or "").lower()
        if start_local == target_date and "cycling" in sport:
            return a
    return None


def ensure_fit_cached(activity_id: str) -> Path | None:
    fit_path = CACHE_DIR / f"{activity_id}.fit"
    if fit_path.exists():
        return fit_path
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "garmin_fetch.py"), activity_id],
        capture_output=True, text=True,
    )
    return fit_path if fit_path.exists() else None


def analyze_ride(fit_path: Path) -> str | None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "analyze_fit.py"), str(fit_path)],
        capture_output=True, text=True,
    )
    return result.stdout if result.returncode == 0 else None


# ----------------------------------------------------------------------------
# Withings (minimal client — see withings_fetch.py for the full one)
# ----------------------------------------------------------------------------

def load_withings_tokens():
    if not WITHINGS_TOKEN_FILE.exists():
        return None
    try:
        return json.loads(WITHINGS_TOKEN_FILE.read_text())
    except Exception:
        return None


def refresh_withings(tokens: dict) -> dict | None:
    if int(time.time()) < tokens.get("expires_at", 0) - 60:
        return tokens
    cid = os.environ.get("WITHINGS_CLIENT_ID")
    secret = os.environ.get("WITHINGS_CLIENT_SECRET")
    if not cid or not secret:
        return None
    resp = requests.post(f"{WITHINGS_API_BASE}/v2/oauth2", data={
        "action": "requesttoken",
        "grant_type": "refresh_token",
        "client_id": cid,
        "client_secret": secret,
        "refresh_token": tokens["refresh_token"],
    }, timeout=15).json()
    if resp.get("status") != 0:
        return None
    b = resp["body"]
    tokens.update({
        "access_token": b["access_token"],
        "refresh_token": b["refresh_token"],
        "expires_at": int(time.time()) + b["expires_in"],
    })
    WITHINGS_TOKEN_FILE.write_text(json.dumps(tokens, indent=2))
    return tokens


def withings_post(tokens: dict, path: str, params: dict):
    h = {"Authorization": f"Bearer {tokens['access_token']}"}
    r = requests.post(f"{WITHINGS_API_BASE}{path}", headers=h, data=params, timeout=15).json()
    return r["body"] if r.get("status") == 0 else None


def fetch_withings_body(tokens, days: int = 7) -> list:
    """Returns list of {ts, weight_kg, bf_pct, fat_kg, lean_kg} sorted asc."""
    end = datetime.now()
    start = end - timedelta(days=days)
    body = withings_post(tokens, "/measure", {
        "action": "getmeas",
        "meastype": "1,5,6,8",
        "startdate": int(start.timestamp()),
        "enddate": int(end.timestamp()),
        "category": "1",
    })
    if not body:
        return []
    out = []
    for grp in body.get("measuregrps", []):
        rec = {"ts": datetime.fromtimestamp(grp["date"])}
        for m in grp["measures"]:
            v = m["value"] * (10 ** m["unit"])
            if m["type"] == 1:
                rec["weight_kg"] = round(v, 2)
            elif m["type"] == 6:
                rec["bf_pct"] = round(v, 2)
            elif m["type"] == 5:
                rec["lean_kg"] = round(v, 2)
            elif m["type"] == 8:
                rec["fat_kg"] = round(v, 2)
        out.append(rec)
    out.sort(key=lambda r: r["ts"])
    return out


# ----------------------------------------------------------------------------
# Composition
# ----------------------------------------------------------------------------

def compose_snapshot(target_date: str, withings_body: list, athlete: dict) -> str:
    lines = ["## Snapshot"]

    # Filter morning fasted readings (06:00-10:00 local)
    target = datetime.fromisoformat(target_date).date()
    morning = [
        r for r in withings_body
        if r["ts"].date() == target and 6 <= r["ts"].hour < 10 and "weight_kg" in r
    ]
    later = [
        r for r in withings_body
        if r["ts"].date() == target and r["ts"].hour >= 10 and "weight_kg" in r
    ]

    if morning:
        m = morning[0]
        lines.append(f"- Weight: **{m['weight_kg']} kg** (Withings, {m['ts'].strftime('%H:%M')} local) — fasted morning")
        if "bf_pct" in m:
            lines.append(f"- Body composition (Withings, morning fasted): **{m['bf_pct']}% BF** / {m.get('fat_kg', '?')} kg fat / {m.get('lean_kg', '?')} kg lean — single-day reading; trust the weekly anchored fasted, not daily")
    else:
        lines.append("- Weight: _no morning Withings reading available_")

    if later:
        ls = later[-1]
        lines.append(f"- Latest reading: {ls['weight_kg']} kg (Withings, {ls['ts'].strftime('%H:%M')} local)")

    # 7-day morning trend
    morning_series = [r for r in withings_body if 6 <= r["ts"].hour < 10 and "weight_kg" in r]
    if len(morning_series) >= 2:
        arrow = " → ".join(f"{r['weight_kg']}" for r in morning_series[-7:])
        delta = morning_series[-1]["weight_kg"] - morning_series[0]["weight_kg"]
        days = (morning_series[-1]["ts"] - morning_series[0]["ts"]).days or 1
        lines.append(f"- 7-day morning trend: {arrow} — net **{delta:+.2f} kg** over {days} days")

    return "\n".join(lines)


def compose_recovery(recovery: dict) -> str:
    lines = ["## Recovery (Withings + Garmin)"]

    # Sleep
    sleep = recovery.get("sleep")
    if isinstance(sleep, dict) and "_error" not in sleep:
        dto = sleep.get("dailySleepDTO") or {}
        scores = dto.get("sleepScores") or {}
        overall = (scores.get("overall") or {}).get("value") if isinstance(scores.get("overall"), dict) else scores.get("overall")
        lines.append(
            f"- **Sleep (Garmin):** total {fmt_dur(dto.get('sleepTimeSeconds'))} "
            f"(Deep {fmt_dur(dto.get('deepSleepSeconds'))} · "
            f"Light {fmt_dur(dto.get('lightSleepSeconds'))} · "
            f"REM {fmt_dur(dto.get('remSleepSeconds'))} · "
            f"Awake {fmt_dur(dto.get('awakeSleepSeconds'))}) / score {overall or '—'}"
        )

    # RHR
    rhr = recovery.get("rhr")
    if isinstance(rhr, dict) and "_error" not in rhr:
        metrics = (rhr.get("allMetrics") or {}).get("metricsMap") or {}
        rhr_list = metrics.get("WELLNESS_RESTING_HEART_RATE") or []
        rhr_val = rhr_list[0].get("value") if rhr_list else rhr.get("restingHeartRate")
        if rhr_val is not None:
            lines.append(f"- **Resting HR (Garmin):** **{rhr_val} bpm**")

    # HRV
    hrv = recovery.get("hrv")
    if isinstance(hrv, dict) and "_error" not in hrv:
        summary = hrv.get("hrvSummary") or {}
        baseline = summary.get("baseline") or {}
        lines.append(
            f"- **HRV overnight RMSSD (Garmin):** {summary.get('lastNightAvg', '—')} ms last night / "
            f"{summary.get('weeklyAvg', '—')} ms weekly / "
            f"baseline {baseline.get('lowUpper', '—')}-{baseline.get('balancedUpper', '—')} ms / "
            f"**status {summary.get('status', '—')}**"
        )

    # Training Readiness
    tr = recovery.get("training_readiness")
    if isinstance(tr, list) and tr:
        tr = tr[0]
    if isinstance(tr, dict) and "_error" not in tr:
        lines.append(
            f"- **Training Readiness (Garmin):** **{tr.get('score', '—')}/100 {tr.get('level', '')}**"
        )

    # Body Battery
    bb = recovery.get("body_battery")
    if isinstance(bb, list) and bb:
        bb_entry = bb[0]
        values = bb_entry.get("bodyBatteryValuesArray") or []
        levels = [v[1] for v in values if isinstance(v, list) and len(v) >= 2 and v[1] is not None]
        current = (bb_entry.get("bodyBatteryDynamicFeedbackEvent") or {}).get("bodyBatteryLevel")
        lines.append(
            f"- **Body Battery (Garmin):** charged {bb_entry.get('charged', '—')} overnight / "
            f"drained {bb_entry.get('drained', '—')} today / "
            f"range {min(levels) if levels else '—'}-{max(levels) if levels else '—'} / "
            f"current {current or '—'}"
        )
        # Activity impacts
        for ev in bb_entry.get("bodyBatteryActivityEvent") or []:
            impact = ev.get("bodyBatteryImpact")
            fb = ev.get("shortFeedback", "")
            if impact is not None and ev.get("eventType"):
                sign = "+" if impact >= 0 else ""
                lines.append(f"  - {ev['eventType'].title()} impact: {sign}{impact}{f'  ({fb})' if fb and fb != 'NONE' else ''}")

    # Auto coach note based on TR + HRV cross-check (per saved memory)
    tr_score = tr.get("score") if isinstance(tr, dict) and "_error" not in tr else None
    hrv_status = (hrv.get("hrvSummary") or {}).get("status") if isinstance(hrv, dict) and "_error" not in hrv else None
    if tr_score is not None and hrv_status:
        if tr_score < 60 and hrv_status == "BALANCED":
            lines.append("- **Auto-interpretation:** low TR + BALANCED HRV = loaded by recent volume, not autonomic stress. Prescription is rest/easy spin, not nutrition or sleep intervention.")
        elif tr_score < 60 and hrv_status == "UNBALANCED":
            lines.append("- **Auto-interpretation:** low TR + UNBALANCED HRV = autonomic system also stressed. Prescription: rest + protein floor + sleep priority + de-load deeper than just volume cut.")
        elif tr_score >= 75:
            lines.append("- **Auto-interpretation:** high TR — body ready for harder work today.")

    return "\n".join(lines) if len(lines) > 1 else "## Recovery (Withings + Garmin)\n\n_No recovery data available._"


def compose_training(activities: list, target_date: str) -> str:
    """Build the 'last 7 days through D-1' section."""
    target = datetime.fromisoformat(target_date).date()
    # Filter to last 7 days strictly before target_date
    week_ago = target - timedelta(days=7)
    relevant = []
    for a in activities:
        d_str = (a.get("startTimeLocal") or "")[:10]
        if not d_str:
            continue
        try:
            d = datetime.fromisoformat(d_str).date()
        except ValueError:
            continue
        if week_ago <= d < target:
            relevant.append((d, a))
    relevant.sort(key=lambda x: x[0])

    lines = ["## Training from Garmin (through yesterday)"]
    if not relevant:
        lines.append("_No activity data for the last 7 days._")
        return "\n".join(lines)

    lines.append("")
    lines.append("| Date | Type | km | Elev | Avg HR | Notes |")
    lines.append("|---|---|---:|---:|---:|---|")
    for d, a in relevant:
        sport = (a.get("activityType") or {}).get("typeKey", "?")
        km = (a.get("distance") or 0) / 1000
        elev = a.get("elevationGain") or 0
        hr = a.get("averageHR") or "—"
        name = a.get("activityName", "")
        lines.append(f"| {d.isoformat()} | {sport} | {km:.1f} | {elev:.0f} | {hr} | {name} |")

    return "\n".join(lines)


def compose_today_session(today_ride: dict | None, ride_analysis: str | None) -> str:
    if not today_ride:
        return "## Today's session\n\n_No cycling activity on Garmin for this date._"
    name = today_ride.get("activityName", "?")
    aid = today_ride.get("activityId", "?")
    lines = [
        f"## Today's session (completed)",
        f"",
        f"**{name}** (Garmin activity {aid})",
        f"",
    ]
    if ride_analysis:
        lines.append("```")
        lines.append(ride_analysis.rstrip())
        lines.append("```")
    else:
        lines.append("_Ride analysis unavailable — FIT file could not be downloaded or analyzed._")
    return "\n".join(lines)


def compose_nutrition(athlete: dict) -> str:
    protein = (athlete.get("protein_target_g_per_day") or {})
    protein_mod = protein.get("moderate_deficit", [160, 180])
    return (
        "## Nutrition target for tomorrow\n\n"
        "_Auto-generated baseline — phase-specific adjustments from `ATHLETE.md` are not parsed by this script._\n\n"
        "- **Protein:** {pmin}-{pmax} g/day (per `athlete.json`)\n"
        "- **Carbs:** scale with training load — refer to ATHLETE.md operational defaults\n"
        "- **Hydration:** 2.5-3 L water (more on long ride days, +electrolytes)\n"
        "- **Refine in interactive session** for phase-specific deficit + carb-timing rules."
    ).format(pmin=protein_mod[0], pmax=protein_mod[1])


def compose_diary(target_date: str, athlete: dict, recovery: dict, activities: list,
                  withings_body: list, today_ride: dict | None, ride_analysis: str | None) -> str:
    sections = [
        f"# Training & Weight Diary — {target_date}",
        "",
        f"_Auto-generated by `scripts/daily.py`. Data sources: Garmin Connect + Withings + analyze_fit.py. Coach note + phase-specific guidance not auto-generated — refine in interactive Claude session if needed._",
        "",
        compose_snapshot(target_date, withings_body, athlete),
        "",
        compose_training(activities, target_date),
        "",
        compose_recovery(recovery),
        "",
        compose_today_session(today_ride, ride_analysis),
        "",
        compose_nutrition(athlete),
        "",
    ]
    return "\n".join(sections)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("date", nargs="?", default=date.today().isoformat(),
                    help="Target date YYYY-MM-DD (default today)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print to stdout instead of writing diary/<date>.md")
    ap.add_argument("--force", action="store_true",
                    help="Overwrite existing diary file")
    ap.add_argument("--no-ride", action="store_true",
                    help="Skip ride fetch + analysis (rest day)")
    args = ap.parse_args()

    target = args.date
    try:
        datetime.fromisoformat(target)
    except ValueError:
        sys.exit(f"Invalid date: {target}. Use YYYY-MM-DD.")

    diary_path = DIARY_DIR / f"{target}.md"
    if diary_path.exists() and not args.force and not args.dry_run:
        sys.exit(f"{diary_path} already exists. Use --force to overwrite or --dry-run to preview.")

    athlete = load_athlete()

    log(f"[1/5] Garmin login...")
    try:
        g = garmin_login()
    except Exception as e:
        sys.exit(f"Garmin login failed: {e}. Run scripts/garmin_auth.py interactively first.")

    log(f"[2/5] Garmin recovery for {target}...")
    recovery = fetch_recovery(g, target)

    log(f"[3/5] Garmin activities (last 7 days + today)...")
    activities = fetch_activities(g, n=20)
    today_ride = None if args.no_ride else find_today_ride(activities, target)

    log(f"[4/5] Withings body composition (last 7 days)...")
    w_tokens = load_withings_tokens()
    withings_body = []
    if w_tokens:
        w_tokens = refresh_withings(w_tokens)
        if w_tokens:
            withings_body = fetch_withings_body(w_tokens, days=7)
    else:
        log("    (Withings not configured — skipping body composition section)")

    ride_analysis = None
    if today_ride:
        aid = str(today_ride["activityId"])
        log(f"[5/5] Today's ride detected (id {aid}). Caching FIT + analyzing...")
        fit_path = ensure_fit_cached(aid)
        if fit_path:
            ride_analysis = analyze_ride(fit_path)
    else:
        log(f"[5/5] No ride for {target} (or --no-ride). Skipping analysis.")

    log("Composing diary entry...")
    md = compose_diary(target, athlete, recovery, activities, withings_body, today_ride, ride_analysis)

    if args.dry_run:
        print(md)
        return

    DIARY_DIR.mkdir(exist_ok=True)
    diary_path.write_text(md)
    log(f"Wrote {diary_path}")


if __name__ == "__main__":
    main()
