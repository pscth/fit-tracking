---
name: training-diary
description: daily training diary workflow for athletes. Pulls data from configured sources (Strava, Withings, Garmin) into a structured daily entry, applying goal-specific rules read from ATHLETE.md (event prep, weight loss, performance, hypertrophy, etc.). Use when the user asks to log daily training, summarize activities, track body composition or weight trends, estimate recovery/readiness, plan nutrition, or write a diary entry for any target date.
---

# Training Diary

## Purpose
Maintain a practical daily training diary that combines training data, body-weight or composition trend, nutrition targets, and readiness. The athlete's specific goal, plan, phase logic, and prescriptive rules live in **`ATHLETE.md`** at the repo root — read it first; the skill applies whatever is defined there.

## Read these before writing an entry

1. **`ATHLETE.md`** — the active fitness plan, biometric baseline, equipment, operational defaults (TDEE, carb/hydration rules, tracking protocol), and reference rides. Defines what "the goal" is for this athlete and which rules apply. **If `ATHLETE.md` is missing, ask the user to copy `ATHLETE.example.md` and fill it in before proceeding.**
2. **`scripts/athlete.json`** — numeric constants (FTP, weight, power zones, protein targets) consumed by analysis scripts.
3. **Recent entries in `diary/`** — historical context for trends, recovery, and what was prescribed.

## Data sources
Use available connectors / scripts in this priority order:

1. **Garmin Connect** (via `scripts/garmin_fetch.py` / `scripts/garmin_recovery.py`) for activities + recovery (RHR, HRV, sleep, Body Battery, Training Readiness).
2. **Strava MCP** for activities, distance, moving time, elevation, power, HR, calories, perceived effort, activity links.
3. **Withings MCP** for weight, body fat %, muscle mass, RHR, sleep, blood pressure, trend.
4. **Ride analysis scripts** (`analyze_fit.py` / `analyze_tcx.py`) for canonical NP / IF / TSS / HR drift / decoupling from a Garmin file when richer numbers are needed.
5. **User-provided manual entries** when automated sources are unavailable or incomplete (see `references/manual-entry-template.md`).

Never invent missing metrics. Mark unavailable values as `not available` and continue with a useful partial diary.

## Diary entry temporal structure
A diary entry written on date **D** is anchored as follows. This is the rule — do not collapse these together:

- **Lookback (training):** report exercise data **up to and including D-1 (yesterday)**. D's training has not happened yet, so it does not belong in the training/recovery sections of D's diary. (Exception: if the user asks for a same-day diary *after* a workout, treat D's session as already completed and log it under "Today's session (completed)".)
- **Today (D):** report only data already captured by end of morning — the **latest morning weigh-in**, today's recovery snapshot (Garmin RHR / HRV / sleep / Training Readiness), and the event countdown derived from `ATHLETE.md`'s active plan.
- **Lookforward:** state the **expectation for D+1 onward** — nutrition target for tomorrow, planned session(s), next actions. This is the only forward-looking content in the entry.

This structure means D's diary is the "morning briefing": yesterday's training is settled, today's weight + recovery are the freshest reads, and tomorrow's plan is set before it starts.

## Diary file naming convention
Persist entries to `diary/` at the repo root (create the directory if missing):

- `YYYY-MM-DD.md` — training + weight diary (primary entry for the day)
- `YYYY-MM-DD-food.md` — food log, when food is tracked separately
- `YYYY-MM-DD-ride.md` — long-form ride analysis, when a ride warrants a dedicated file

If a file already exists for the target date, overwrite only with explicit user permission — historical entries are immutable by default.

## Food log workflow

Food intake lives in a separate file from the main training diary:
`diary/YYYY-MM-DD-food.md`. The training entry (`YYYY-MM-DD.md`) does not
duplicate the food log; it references it when nutrition is relevant (e.g.
"see [2026-05-19-food.md](./2026-05-19-food.md) for fueling details").

**No automated source** for nutrition data exists yet (none of Garmin /
Strava / Withings tracks food intake). The food log is a Claude-assisted
manual flow:

1. **Trigger:** user describes a meal or snack in natural language
   ("150 g chicken, 100 g rice cooked, salad with AOVE for lunch").
2. **Estimate macros** from known-foods knowledge (typical kcal / P / C / F
   per 100 g of common foods). When weight is missing, assume sensible
   defaults (banana medium ≈ 120 g, tbsp oil ≈ 15 g, slice of bread ≈ 30 g).
3. **Append a meal block** in the standard format below.
4. **Update running totals** against the daily target read from
   `ATHLETE.md`'s "Operational defaults" — flag if a macro is running short
   with meals remaining, or over with the day still open.
5. **At end of day**, close the file with a "Final day total" block and a
   short Notes section (hunger, energy, GI tolerance on ride days, what
   worked / didn't).

### Standard food-log format

```markdown
# Food Log — YYYY-MM-DD (Day descriptor, e.g. "Mon, rest day + swim")

**Daily target (per ATHLETE.md):** ~X kcal · X g P · X g C · X g F · X L water
**TDEE today:** ~X kcal. **Target deficit:** -X kcal.

## Meals

### Breakfast (HH:MM)
| Item | Qty | kcal | P (g) | C (g) | F (g) |
|---|---:|---:|---:|---:|---:|
| Oats (raw) | 40 g | 155 | 6 | 27 | 3 |
| ... | ... | ... | ... | ... | ... |
| **Breakfast subtotal** | | **n** | **n** | **n** | **n** |

### Lunch (HH:MM)
| ... |

## Running totals (after <last meal logged>)
|  | Eaten | Target | Remaining | % of target |
|---|---:|---:|---:|---:|
| Calories (kcal) | n | n | n | n% |
| Protein (g) | n | n | n | n% |
| Carbs (g) | n | n | n | n% |
| Fat (g) | n | n | n | n% |

## Notes
- (energy, hunger, GI, food choices that worked / didn't)
```

At end of day, rename the "Running totals" block to "Final day total" with
the day's actual deficit + macro deltas vs. target.

### Macro estimation guidance

- Always use weights stated by the user. When weight isn't given, assume
  sensible defaults (banana 120 g, slice of bread 30 g, tbsp oil 15 g,
  yogurt cup 125 g) and note the assumption inline.
- For cooked meats, distinguish raw vs cooked (e.g., "200 g chicken raw →
  ~160 g cooked"). Use whichever the user reported.
- For composite shared meals (e.g., "I cooked 500 g of fish; two people
  ate"), divide proportionally and document the split assumption.
- Round kcal to nearest 5, protein/carbs/fat to nearest gram.
- When a label is ambiguous (e.g., "queso fresco" — Burgos proteic vs.
  standard), pick the most likely interpretation and flag the assumption so
  the user can correct.

### When to recommend adjustments

After each meal's running-totals block, if any macro is meaningfully off
target (>20% under at end-of-day-projected, or >10% over), suggest specific
food swaps for remaining meals — don't moralize, just propose options that
close the gap. On ride days, prioritize closing the protein gap first
(structural risk), then the carb gap (performance risk on next-day session).

## Daily workflow
For each diary request:

1. Determine the target date D. If unspecified, use today in the user's timezone.
2. Read `ATHLETE.md` to identify the active goal, current phase (per the phase logic), and applicable rules.
3. Pull activity data for **D-7 through D-1** (do not include D unless explicitly told a workout already happened today).
4. Pull morning body-composition metrics for D and D-7..D-1.
5. Pull recovery metrics for D (RHR / HRV / sleep / Training Readiness / Body Battery if available).
6. Compare today's weight against:
   - yesterday
   - 7-day average
   - lowest weight in the last 14 days, if available
7. Summarize training load using available metrics (activity type, distance, duration, elevation, avg/normalized power, avg/max HR, RPE if provided).
8. Estimate the day type (rest / recovery / easy endurance / moderate / hard / long / event day).
9. Give a nutrition target for the next 24 hours **using the rules + targets defined in `ATHLETE.md`** (calories, protein, carbs, fat, hydration). Don't invent generic numbers when `ATHLETE.md` defines specific ones.
10. Produce the diary entry in the standard format below.
11. Persist to `diary/YYYY-MM-DD.md`.

## Standard output format
Use this format for the daily training diary:

```markdown
# Training & Weight Diary — YYYY-MM-DD

## Snapshot
- Weight: X kg (source, time)
- Post-ride weight: X kg (if applicable)
- Change vs yesterday: ±X kg
- 7-day trend: X → ... → X (net Δ, slope)
- Body composition (when available): BF% / fat mass / lean mass
- Event countdown: X days to [active goal from ATHLETE.md]

## Training from <source> (through yesterday)
[Yesterday's session detail + last-7-days summary table]

## Recovery (Withings + Garmin)
- Sleep: X (stages + score)
- Resting HR: X bpm
- HRV overnight RMSSD: X / weekly avg / baseline / status
- Training Readiness: X/100 [LEVEL]
- Body Battery: charged X / drained X / activity impact
- BF% (when available): X% — flag single-day noise vs weekly anchor

## Today's session (only if completed)
[Same-day session detail with link to <date>-ride.md if a deep analysis exists]

## Nutrition target for tomorrow
- Calories: X-X kcal (per ATHLETE.md TDEE table + phase rule)
- Protein: X-X g
- Carbs: X-X g
- Fat: X-X g
- Hydration: X
[Pre/during/post specific guidance if a key session is scheduled]

## Coach note
Short, direct advice tied to the active goal and current phase from ATHLETE.md.

## Next actions (look-forward)
1. [training action]
2. [nutrition action]
3. [recovery action]
```

When data is sparse, still output the same structure with `not available` values and ask for the single most useful missing item at the end.

## Weekly review format
When the user asks for a weekly review, include:

- Weekly weight trend + 7-day average movement
- Total training volume by sport (km, hours, TSS if available)
- Longest ride/run
- Hard-session count
- Recovery warning signs (high RHR, low HRV, poor sleep, etc.)
- Adherence score 1-10
- Adjustment for the next week
- Event-readiness or goal-progress note (from `ATHLETE.md`)

## Tone
Be direct, practical, and slightly coach-like. Match the user's language preference (e.g., informal Spanish/Catalan if that's their default). Keep medical/safety boundaries clear.

## Safety boundaries
Recommend medical supervision for very-low-calorie diets, rapid weight-loss attempts, symptoms such as dizziness/fainting/chest pain, or any known medical constraint noted in `ATHLETE.md`. Do not provide unsafe weight-cutting, training, or supplementation advice. Defer to `ATHLETE.md`'s "Known medical constraints" field when present.
