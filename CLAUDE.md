# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project context

This repo is a personal training diary toolkit. The `training-diary` skill
(`.claude/skills/training-diary/SKILL.md`) governs the daily diary workflow.
The user's specific goal (event prep, weight loss, performance, hypertrophy,
etc.) is defined in `ATHLETE.md`.

## Setup

Python 3.12+ required. Install deps once:

```bash
python3 -m pip install --user -r requirements.txt
```

Each data source (Garmin / Strava / Withings) has its own one-time auth flow — see README for details. All three are independent; analyzers run standalone with no integration.

## Architecture

Three orthogonal data integrations feed one orchestrator:

- **Garmin Connect** (`garminconnect` library) — recovery (`garmin_recovery.py`) + activity FITs (`garmin_fetch.py`); first-time auth via `garmin_auth.py`. Tokens at `~/.garminconnect/`.
- **Strava** (`stravalib`) — `strava_fetch.py`, fallback / cross-check. Tokens at `~/.fit-tracking/strava_tokens.json`.
- **Withings** — REST API direct via `requests` (no library — pydantic 2.x conflict with stravalib). `withings_fetch.py`. Tokens at `~/.fit-tracking/withings_tokens.json`.

`daily.py` is the unattended orchestrator (cron-safe): pulls from each source, runs `analyze_fit.py` on the day's ride via `subprocess`, composes Markdown, writes `diary/YYYY-MM-DD.md`. Per-source failures degrade gracefully via `safe_call` — missing sources just elide their section, they don't abort the run. Analyzers (`analyze_fit.py`, `analyze_tcx.py`) have no integration dependency and work on any FIT/TCX file.

Interactive flow (Claude session via the `training-diary` skill) is the "ceiling"; cron-driven `daily.py` is the "floor." Both write to the same `diary/` archive.

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

## Interaction & coaching conventions

Behavioral rules calibrated from prior sessions. Apply in any session in this repo.

- **Defend numerical positions.** When the user pushes back on a number, triage the challenge first: new data / preference / disagreement. Only **new data** automatically warrants moving the number; **preference** shifts the path (sources, ordering, timing), not the target; **disagreement** gets defended with reasoning or honest "I don't know what's missing." Reflexive lowering reads as low-trust. Cite this rule back when holding a position so the user knows the filter is working.
- **Define jargon inline on first use.** RPE / NP / IF / TSS / VAM / Pw:HR decoupling each need a one-line plain-language gloss the first time they appear in a session. Verbal answers ("fresh", "fading", "felt easier") are valid substitutes for a numerical RPE — don't insist on the number.
- **Verify past-performance claims against the data.** Before scaling plans to "I've done X before," pull Withings / Strava for the cited window. Memory of past weight loss tends to overstate the rate (peak-to-trough swing conflated with sustained loss). If the recall is off, surface the actual numbers — data-grounded honesty over generic coaching.
- **Carb density over plate volume.** When proposing carb-load or high-carb days, default to dense sources (bread / dates / honey / banana) and spread across many small windows. Stomach capacity, not willingness, is the constraint. 3-4 g/kg/day is "good enough" for sub-event rides — don't push past comfort.
- **Lifting recommendations are nuanced — never "skip lifting."** Split upper / core / light accessories (low cycling interference, fine almost any day) from heavy lower-body (DOMS lingers 24-48 h and trashes legs on subsequent rides). Apply a 48 h no-heavy-legs window before key rides. Strength work is baseline, not optional.
- **Garmin Training Readiness reads cumulative load, not autonomic state.** A low TR score paired with BALANCED HRV means "loaded, not stressed" — prescription is rest from accumulated volume, not nutrition or sleep intervention. Cross-check HRV before interpreting a low TR: HRV BALANCED → volume; HRV UNBALANCED LOW → autonomic also stressed (deeper de-load + protein floor + sleep priority); HRV UNBALANCED HIGH → over-reaching, full rest + watch for illness.

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

`garmin_auth.py` is the one-time interactive Garmin login (handles MFA). Must run in a real TTY — not via Claude's `!` prefix or any non-interactive subshell. Reads `GARMIN_CONNECT_USER` / `GARMIN_CONNECT_PWD` env vars.

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
