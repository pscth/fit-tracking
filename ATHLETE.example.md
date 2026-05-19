# Athlete Profile — Template

Copy this file to `ATHLETE.md` (which is gitignored) and replace placeholders
with your own values. Claude reads `ATHLETE.md` at session start when it's
present alongside `CLAUDE.md`.

## Active fitness plan

- **Key event:** [event name, location, date — e.g. "Multi-day cycling block, Provence, 2026-05-29 to 2026-06-01"]
- **Schedule:**
  - YYYY-MM-DD — Day 1: distance / elevation / focus
  - YYYY-MM-DD — Day 2: ...
- **Primary goal:** [e.g. fat loss while protecting cycling performance / pure performance / event finish]
- **Long-term weight target:** [kg, with sustainability note]
- **Phase logic** (anchored on first event day):
  - More than 10 days out: [strategy]
  - 4-10 days out: [strategy]
  - Final 3 days out: [strategy]
  - Event days: [strategy]
  - Recovery: [strategy]

## Athlete baseline

- Age:
- Height: cm
- Current weight: kg ([source, date])
- BMI: ([category])
- Body composition: [BF%, fat mass, lean mass — if tracked]
- BF% historical anchors: [dates + values, for trend reference]
- Resting HR: bpm ([source, date — pull via `scripts/garmin_recovery.py`])
- Protein target: g/day ([range and conditions])
- Known medical constraints: [list or _none recorded_]
- Fitness anchor: [biggest similar ride completed, used to calibrate event picks]

## Equipment & power data

- Power meter: [brand, model, single/dual-sided, date acquired]
- Working FTP: W ([how determined, date])
- Power zones (at current FTP):
  - Z2 endurance: -W
  - Z3 tempo: -W
  - Z4 threshold: -W

## Operational defaults

**TDEE by day type** (computed for your weight/age/height — use Mifflin-St Jeor):

| Day type | TDEE | Eat for -X cut | Eat for -Y aggressive |
|---|---:|---:|---:|
| Sedentary, no walk | | | |
| Sedentary + 10k walk | | | |
| + 1 h Z2 ride | | | |
| + 2 h Z2 ride | | | |
| + 3-4 h ride | | | |
| + Block long ride | | | |

**Daily carb targets** (within calorie budget):
- Rest day: g
- Light training: g
- Long ride day: g (eat to fuel)
- Carb-load: g/kg

**On-bike hydration rule:** [ml/h target, with condition adjustments]

**On-bike carb-fuel rule:** [g/h target, with timing notes]

**Tracking protocol:**
- Weight: [frequency, conditions]
- BF%: [frequency, conditions]
- Other: [hip circumference, RHR, etc.]

## Reference rides

Each entry: date / route / NP / IF / TSS / RPE / decoupling / what it proves.

- YYYY-MM-DD ([ride name]): km / m / NP W / IF / TSS / RPE / → [conclusion]
