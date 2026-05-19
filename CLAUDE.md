# Fit Tracking — Project Context

This repo is a personal training diary toolkit. The `training-diary` skill
(`.claude/skills/training-diary/SKILL.md`) governs the daily diary workflow.
The user's specific goal (event prep, weight loss, performance, hypertrophy,
etc.) is defined in `ATHLETE.md`.

## Personal context lives in ATHLETE.md

**The repo owner's active fitness plan, biometric baseline, equipment, computed
operational defaults (TDEE / carb / hydration), and reference rides are in
[ATHLETE.md](./ATHLETE.md) (gitignored — never committed).** Claude should read
it at session start whenever it exists.

If `ATHLETE.md` is missing (fresh clone, fork), see `ATHLETE.example.md` for
the expected structure and `scripts/athlete.example.json` for the numeric-config
template.

## Diary archive

Daily entries live in `diary/` and follow this naming convention:
- `YYYY-MM-DD.md` — training + weight diary (primary entry for the day)
- `YYYY-MM-DD-food.md` — food log (when food is tracked separately)
- `YYYY-MM-DD-ride.md` — long-form ride analysis (when a ride warrants a dedicated file)

The `training-diary` skill governs entry structure — read it before
authoring a diary day from scratch. Treat existing entries as historical
record — don't rewrite past days unless explicitly asked.

`diary/` is gitignored — entries are per-user personal logs.

## Repo layout

- `CLAUDE.md` — this file. Generic project context (tooling, conventions).
- `ATHLETE.md` — personal profile + active plan + biometric baseline (gitignored). See `ATHLETE.example.md` for structure.
- `README.md` — user-facing setup + usage docs.
- `diary/` — daily entries (gitignored). See "Diary archive" above for naming convention.
- `scripts/` — Python analysis + Garmin Connect tooling. See "Analysis scripts" below.
- `scripts/athlete.json` — numeric athlete config consumed by analysis scripts (gitignored). See `scripts/athlete.example.json` for structure.
- `kotr26/` — git submodule pinned to the event repo (route data). Authoritative route stats in `kotr26/js/main.js` ROUTES config; submodule README is outdated.
- `requirements.txt` — pinned Python deps (`fitparse`, `garminconnect`, `stravalib`). Garmin used to be a submodule; now installed from PyPI.
- `.claude/skills/training-diary/SKILL.md` — the daily diary workflow skill.

## Analysis scripts

`analyze_fit.py` and `analyze_tcx.py` take one positional arg (file path) and print NP / IF / TSS / best efforts / power & HR zone distribution / HR drift / Pw:HR decoupling / climb profile.

```bash
# FIT files (Garmin native, richer data) — requires fitparse
python3 -m pip install --user fitparse
python3 scripts/analyze_fit.py /path/to/ride.fit

# TCX files (XML, stdlib only, no install)
python3 scripts/analyze_tcx.py /path/to/ride.tcx
```

`garmin_fetch.py` downloads activity files (FIT or TCX) directly from Garmin Connect using `garminconnect` (pip). Caches to `scripts/cache/` (gitignored). Credentials from `GARMIN_CONNECT_USER` / `GARMIN_CONNECT_PWD` env vars (passed to library at fresh-login time via `scripts/garmin_auth.py`); tokens cached to `~/.garminconnect/garmin_tokens.json`.

```bash
python3 scripts/garmin_fetch.py latest                    # latest 1 activity as FIT
python3 scripts/garmin_fetch.py latest --n 5 --format tcx # latest 5 as TCX
python3 scripts/garmin_fetch.py 18564719760               # specific activity ID
```

`garmin_recovery.py` pulls the daily morning-readiness snapshot: Training Readiness (composite 0-100 + level), HRV (RMSSD + baseline + status), Sleep, RHR, Body Battery.

```bash
python3 scripts/garmin_recovery.py              # today
python3 scripts/garmin_recovery.py 2026-05-19   # specific date
python3 scripts/garmin_recovery.py --raw        # dump full JSON for debugging
```

`strava_fetch.py` lists recent activities or fetches one by ID via `stravalib`. Requires one-time OAuth (see README). Tokens at `~/.fit-tracking/strava_tokens.json`.

```bash
python3 scripts/strava_fetch.py --auth          # one-time OAuth
python3 scripts/strava_fetch.py recent --n 10
python3 scripts/strava_fetch.py 18564719760
```

`withings_fetch.py` reads weight / body composition / sleep from the Withings REST API directly (no third-party Withings library — none compatible with stravalib's pydantic 2.x). Requires one-time OAuth. Tokens at `~/.fit-tracking/withings_tokens.json`.

```bash
python3 scripts/withings_fetch.py --auth        # one-time OAuth
python3 scripts/withings_fetch.py weight --days 7
python3 scripts/withings_fetch.py body --days 7
python3 scripts/withings_fetch.py sleep [YYYY-MM-DD]
```

`daily.py` chains recovery + fetch latest + analyze ride in a single command — see `README.md` for usage and the scheduled (cron) pattern.

**Athlete config:** both analysis scripts read FTP and weight from `scripts/athlete.json`. Edit the JSON to update — both scripts pick it up next run. Override per-run with `--ftp` / `--weight` CLI flags.

**Strava stream NP is unreliable.** The value Strava returns in activity stream stats can be ~15% below true NP because of how downsampling + zero-power stops are handled. Always run the script on the raw FIT/TCX for canonical NP/IF/TSS. Observed 2026-05-19: Strava stream NP 166 W vs script NP 192 W on the same ride.
