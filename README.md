# fit-tracking

**A daily training diary for athletes who don't want to juggle apps.**

Every night, this repo pulls today's data from Garmin, Strava, and Withings;
runs proper power analysis on the day's ride (Normalized Power, IF, TSS, HR
drift, Pw:HR decoupling); composes a structured diary entry; and writes it
to `diary/YYYY-MM-DD.md`. The day's training picture lands in one file
before you go to bed — settled metrics, no morning copy-paste.

Designed to pair with [Claude Code](https://claude.com/claude-code) — the
included `training-diary` skill turns a "write today's diary" message into a
tailored coaching session backed by all the same data. The scripts also run
fully standalone for unattended use (cron / launchd / Raspberry Pi).

---

## What a daily entry looks like

A real entry, abridged for the README. `scripts/daily.py` writes this whole
thing to `diary/2026-05-19.md` with no manual entry — every number is pulled
from a data source.

```markdown
# Training & Weight Diary — 2026-05-19

## Snapshot
- Weight: 88.48 kg (Withings, 07:05 local) — fasted morning
- Body composition: 17.42% BF / 15.4 kg fat / 73.1 kg lean
- 7-day morning trend: 89.56 → 89.26 → 88.91 → 89.31 → 89.08 → 89.33 → 88.48
  — net -1.08 kg over 5 days

## Recovery (Garmin)
- Sleep: 7h04m / score 84 (Deep 1h57m · REM 1h42m · Awake 20m)
- Resting HR: 43 bpm
- HRV: 63 ms last night / weekly 61 / baseline 53-66 / BALANCED
- Training Readiness: 50/100 MODERATE
- Auto-interpretation: low TR + BALANCED HRV = loaded by recent volume,
  not autonomic stress. Prescription is rest, not nutrition intervention.

## Today's session — Coll de Sant Bartomeu (383 m)
- 49.83 km / 820 m / 2h18m moving
- NP 192 W / IF 0.91 / TSS 192 (threshold)
- 20-min best: 220 W → FTP confirmed at 210 W (0.95 rule)
- HR drift +12.9 bpm / Pw:HR decoupling +7.6%
- Fueling: 31 g C/h (vs 60-80 target), 564 ml/h (vs ≥600 target)
```

---

## What's inside

```
scripts/
├── daily.py           # The unattended end-of-day diary — orchestrates everything below
├── garmin_recovery.py # Today's RHR / HRV / Sleep / Body Battery / Training Readiness
├── garmin_fetch.py    # Download activity FITs from Garmin Connect
├── garmin_auth.py     # First-time Garmin auth (handles MFA)
├── analyze_fit.py     # Power analysis: NP, IF, TSS, HR drift, Pw:HR decoupling
├── analyze_tcx.py     # Same, for TCX files (stdlib only)
├── strava_fetch.py    # Strava activity list / detail (fallback or cross-check)
└── withings_fetch.py  # Weight, body comp, sleep summary
```

Three data integrations (Garmin, Strava, Withings). All optional, all
independent. Use any combination — or none, in which case the FIT/TCX
analyzers still work standalone.

---

## 60-second quick start (analysis only, no integrations)

```bash
git clone --recurse-submodules <your-fork-url> fit-tracking
cd fit-tracking
python3 -m pip install --user -r requirements.txt

cp scripts/athlete.example.json scripts/athlete.json
# Edit scripts/athlete.json — at minimum set your FTP (watts) and weight (kg)

python3 scripts/analyze_fit.py /path/to/any/ride.fit
```

You'll see a multi-section ride analysis printed to your terminal. Done — the
analysis pipeline works for any FIT or TCX file from any device, no
integrations required.

Want the data pulled automatically? Wire up one or more sources below.

---

## Wiring up data sources

Each source is **optional and independent**. Pick the ones you use.

### Garmin Connect — recommended if you own a Garmin

Gives you sleep, HRV, RHR, Training Readiness, Body Battery, plus your
activity FITs. No OAuth app registration — just your account credentials.

```bash
# 1. Credentials in ~/.zshenv (namespaced — no collision with other tools)
export GARMIN_CONNECT_USER="your-email@example.com"
export GARMIN_CONNECT_PWD="your-password"

# 2. First-time auth (interactive — real terminal, handles MFA prompt)
python3 scripts/garmin_auth.py

# 3. Verify
python3 scripts/garmin_recovery.py
python3 scripts/daily.py --dry-run
```

Tokens cache to `~/.garminconnect/` and auto-refresh. After the first auth,
everything's unattended.

### Withings — for weight + body composition

Withings doesn't sync body comp to Garmin by default, so wire it up directly if
you have a Withings scale.

```bash
# 1. Register a dev app at https://developer.withings.com/dashboard/
#    - Callback URI: http://localhost:8765/callback
#    - Copy the Client ID + Consumer Secret

# 2. Credentials in ~/.zshenv
export WITHINGS_CLIENT_ID="..."
export WITHINGS_CLIENT_SECRET="..."

# 3. OAuth dance (browser opens, you approve)
python3 scripts/withings_fetch.py --auth

# 4. Use it
python3 scripts/withings_fetch.py weight --days 7
python3 scripts/withings_fetch.py body --days 7
```

### Nutrition logging — manual (for now)

Food intake doesn't have a clean automated source — none of Garmin, Strava, or
Withings tracks what you eat. It's a **Claude-assisted manual flow**: tell
Claude what you ate, Claude estimates macros from common-foods knowledge,
appends a row to `diary/YYYY-MM-DD-food.md` with running totals, and flags
when you're over or under target.

No standalone script. The Claude session does the calculation interactively,
and the file naming convention stays consistent with the rest of the diary.

> **TODO:** wire up **MyFitnessPal** integration when their API becomes
> approachable for individual developers (they currently gate full API access
> behind a partnership program). The `-food.md` file convention will stay the
> same — only the data source changes.

### Strava — fallback / cross-check

If your data only lives in Strava (no Garmin device), this is your primary
activity source. If you have Garmin too, it's a useful cross-check.

```bash
# 1. Register an app at https://www.strava.com/settings/api
#    Authorization Callback Domain: localhost

# 2. Credentials in ~/.zshenv
export STRAVA_CLIENT_ID="..."
export STRAVA_CLIENT_SECRET="..."

# 3. OAuth + use it
python3 scripts/strava_fetch.py --auth
python3 scripts/strava_fetch.py recent --n 10
```

---

## The daily diary

Once at least one integration is wired up:

```bash
python3 scripts/daily.py
```

Writes `diary/YYYY-MM-DD.md` for today. With more sources configured, more
sections fill in. With none, the script errors out clearly telling you what's
missing.

The diary always covers *today* — there's no date selector. For ad-hoc or
backfill cases (regenerate a missed day, mid-day status check), use the
interactive Claude flow via the `training-diary` skill instead.

Common variants:

```bash
python3 scripts/daily.py --dry-run    # preview, don't write
python3 scripts/daily.py --force      # overwrite existing entry
python3 scripts/daily.py --no-ride    # rest day (skip ride fetch + analysis)
```

### Schedule it

Run end-of-day so the day's metrics are settled by the time the entry is
written (steps, intensity minutes, ride totals all final):

```cron
# 23:30 local — write today's settled briefing
30 23 * * *  cd /path/to/fit-tracking && /usr/bin/python3 scripts/daily.py 2>> diary/.daily.log
```

After the one-time interactive auth, every refresh is automatic. `daily.py`
runs unattended forever.

---

## Make it yours

Two files hold your personal config (both gitignored — never committed):

| File | What's in it |
|---|---|
| `scripts/athlete.json` | **Machine-readable:** FTP (watts), weight (kg), height, age, power zones, protein targets. Used by analysis scripts to compute W/kg, IF, TSS. |
| `ATHLETE.md` | **Human-readable:** active fitness plan, biometric baseline, equipment, computed TDEE table, goal rules, reference rides. Read by Claude (interactive) for context. |

Copy the `.example` templates as starting points:

```bash
cp scripts/athlete.example.json scripts/athlete.json
cp ATHLETE.example.md ATHLETE.md
# Edit both with your numbers + plan
```

The scripts, skill, and `CLAUDE.md` are generic — they work for any athlete
with any goal once your personal layer is filled in.

---

## Pairing with Claude Code

The included `training-diary` skill
(`.claude/skills/training-diary/SKILL.md`) turns an interactive Claude session
into a coach:

- Reads `ATHLETE.md` for your goal, plan, and rules
- Pulls fresh data from all configured sources
- Composes a diary entry tailored to your current phase (taper, build,
  recovery, event week, etc.)
- Goes deeper than unattended `daily.py`: interprets cross-source signals,
  generates a real coach note in your tone

**`daily.py` is the unattended floor. The Claude skill is the ceiling.** Both
work; they don't conflict. Most people will use cron for the daily floor and
Claude for ad-hoc deeper sessions (race-week planning, weekly review, race
report).

---

## Scripts reference

| Script | What it does |
|---|---|
| `daily.py` | Full end-of-day diary → writes `diary/YYYY-MM-DD.md` |
| `garmin_recovery.py` | Today's recovery (TR / HRV / Sleep / RHR / Body Battery) |
| `garmin_fetch.py` | Download activity FIT or TCX by date / ID |
| `garmin_auth.py` | First-time Garmin OAuth (MFA handled) |
| `analyze_fit.py` | Power analysis from a FIT file |
| `analyze_tcx.py` | Same, for TCX files (stdlib only — no extra deps) |
| `strava_fetch.py` | List recent / activity detail / OAuth setup |
| `withings_fetch.py` | Weight / body comp / sleep / OAuth setup |

All scripts have `--help`. The two analyzers read FTP and weight from
`scripts/athlete.json`; override per-run with `--ftp` / `--weight` flags.

---

## Token storage

OAuth tokens are stored outside the repo so they never get committed:

| Provider | Location |
|---|---|
| Garmin | `~/.garminconnect/garmin_tokens.json` |
| Strava | `~/.fit-tracking/strava_tokens.json` |
| Withings | `~/.fit-tracking/withings_tokens.json` |

Static credentials (client IDs, secrets, your Garmin user/pwd) live in
`~/.zshenv`. If you ever need to re-authenticate (revoked access, account
change), rerun the relevant `--auth` flow.

---

## Repository layout

```
fit-tracking/
├── README.md                  # this file
├── CLAUDE.md                  # generic project context (tracked)
├── ATHLETE.md                 # your personal profile + plan (gitignored)
├── ATHLETE.example.md         # template for ATHLETE.md
├── requirements.txt           # Python deps
├── .gitignore                 # excludes per-user data
│
├── scripts/                   # the tools (see "Scripts reference" above)
│   ├── athlete.example.json   # numeric config template (tracked)
│   ├── athlete.json           # your numeric config (gitignored)
│   ├── *.py                   # scripts
│   └── cache/                 # downloaded FITs (gitignored)
│
├── diary/                     # your daily entries (gitignored)
├── .claude/skills/training-diary/  # diary workflow skill
└── kotr26/                    # submodule: event route data (this repo's owner's event)
```

---

## Dependencies

All managed via `requirements.txt`. **Python 3.12+ required.**

```bash
python3 -m pip install --user -r requirements.txt
```

- `fitparse` — FIT parsing (`analyze_fit.py`)
- `garminconnect` — Garmin Connect API
- `stravalib` — Strava API
- `requests` — used by the Withings client (transitive via other deps)

No virtualenv strictly required. If you prefer isolation, create one before
the pip install.

---

## Troubleshooting

**`Token login failed`** (any provider) — auth hasn't been completed. Run the
corresponding `--auth` flow.

**`EOFError: EOF when reading a line`** during a `*_auth.py` script — running
in a non-TTY subshell (or via the `!` prefix inside Claude). Open a regular
terminal window and rerun.

**`ModuleNotFoundError: No module named 'X'`** — `pip install -r
requirements.txt` didn't succeed or the wrong Python is being used. Check
`which python3`.

**Withings `redirect_uri_mismatch`** — the URI in your Withings developer app
doesn't include `http://localhost:8765/callback`. Add it in the Withings
developer dashboard alongside any existing URIs.

**`Already authenticated`** when running `garmin_auth.py` — tokens are valid,
nothing to do. Skip to using `daily.py`.

---

That's the whole thing. Three steps to a working daily diary — then
forget about it and let cron deliver every night.
