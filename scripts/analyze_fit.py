#!/usr/bin/env python3
"""Comprehensive analysis of a cycling FIT file.

FTP and weight are read from scripts/athlete.json (override with --ftp / --weight).
"""

import argparse
import json
import sys
from datetime import timedelta
import statistics
from pathlib import Path
from fitparse import FitFile

ATHLETE_FALLBACK = {"ftp": 210, "weight": 88.48}


def load_athlete():
    cfg = Path(__file__).parent / "athlete.json"
    if not cfg.exists():
        return ATHLETE_FALLBACK
    with open(cfg) as f:
        data = json.load(f)
    return {**ATHLETE_FALLBACK, **{k: v for k, v in data.items() if not k.startswith("_")}}


_ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
_ap.add_argument("path", nargs="?", default="/Users/lluis.diaz/Downloads/Morning_Ride.fit",
                 help="Path to .fit file")
_ap.add_argument("--ftp", type=int, help="Override FTP from athlete.json")
_ap.add_argument("--weight", type=float, help="Override weight (kg) from athlete.json")
_args = _ap.parse_args()

_athlete = load_athlete()
FIT_PATH = _args.path
FTP = _args.ftp if _args.ftp is not None else _athlete["ftp"]
WEIGHT = _args.weight if _args.weight is not None else _athlete["weight"]

POWER_ZONES = [
    ("Z1 Active recovery", 0, 110),
    ("Z2 Endurance", 111, 150),
    ("Z3 Tempo", 151, 180),
    ("Z4 Threshold", 181, 210),
    ("Z5 VO2max", 211, 240),
    ("Z6 Anaerobic", 241, 300),
    ("Z7 Sprint", 301, 99999),
]
HR_ZONES = [
    ("Z1 Recovery", 0, 117),
    ("Z2 Endurance", 118, 146),
    ("Z3 Tempo", 147, 161),
    ("Z4 Threshold", 162, 176),
    ("Z5 VO2max", 177, 999),
]

def fmt(s):
    return str(timedelta(seconds=int(s)))

fit = FitFile(FIT_PATH)
records = []
for rec in fit.get_messages("record"):
    d = {f.name: f.value for f in rec}
    records.append(d)

# Parse session (summary)
session = None
for rec in FitFile(FIT_PATH).get_messages("session"):
    session = {f.name: f.value for f in rec}
    break

# Parse laps
laps = []
for rec in FitFile(FIT_PATH).get_messages("lap"):
    laps.append({f.name: f.value for f in rec})

n = len(records)
start_ts = records[0]["timestamp"]
end_ts = records[-1]["timestamp"]
elapsed = (end_ts - start_ts).total_seconds()

power = [r.get("power") for r in records]
hr = [r.get("heart_rate") for r in records]
cad = [r.get("cadence") for r in records]
spd = [r.get("enhanced_speed") for r in records]
alt = [r.get("enhanced_altitude") for r in records]
dist = [r.get("distance") for r in records]
acc_pwr = [r.get("accumulated_power") for r in records]

# Moving = speed > 0.5 m/s (~1.8 km/h)
moving_mask = [s is not None and s > 0.5 for s in spd]
moving_idx = [i for i, m in enumerate(moving_mask) if m]
moving_time = len(moving_idx)

# Power stats over moving time (zero-fill missing)
pmove = [power[i] if power[i] is not None else 0 for i in moving_idx]
pall = [p if p is not None else 0 for p in power]
avg_p = statistics.mean(pmove) if pmove else 0
max_p = max(pmove) if pmove else 0
nonzero_p = [p for p in pmove if p > 0]
avg_p_pedaling = statistics.mean(nonzero_p) if nonzero_p else 0

# NP: 30s rolling mean → 4th power → mean → 0.25 power
rolling = []
win = 30
for i in range(len(pmove)):
    s = max(0, i - win + 1)
    seg = pmove[s:i+1]
    rolling.append(sum(seg) / len(seg))
np_val = (sum(p**4 for p in rolling) / len(rolling)) ** 0.25 if rolling else 0
IF = np_val / FTP
TSS = (moving_time * np_val * IF) / (FTP * 3600) * 100

# Best efforts (sliding window mean power)
def best_mean(series, window_s):
    if len(series) < window_s:
        return 0
    cumsum = [0]
    for v in series:
        cumsum.append(cumsum[-1] + v)
    best = 0
    for i in range(window_s, len(cumsum)):
        m = (cumsum[i] - cumsum[i-window_s]) / window_s
        if m > best:
            best = m
    return best

best_5s = best_mean(pmove, 5)
best_1m = best_mean(pmove, 60)
best_5m = best_mean(pmove, 300)
best_20m = best_mean(pmove, 1200) if len(pmove) >= 1200 else 0
best_60m = best_mean(pmove, 3600) if len(pmove) >= 3600 else 0

# Total work from accumulated_power (last - first)
acc_valid = [a for a in acc_pwr if a is not None]
total_kj = (acc_valid[-1] - acc_valid[0]) / 1000 if len(acc_valid) >= 2 else sum(pmove) / 1000

# Power zones (moving time)
pz_time = {z[0]: 0 for z in POWER_ZONES}
pz_time["Coasting (0W)"] = 0
for p in pmove:
    if p == 0:
        pz_time["Coasting (0W)"] += 1
        continue
    for name, lo, hi in POWER_ZONES:
        if lo <= p <= hi:
            pz_time[name] += 1
            break

# HR stats
hr_vals = [h for h in hr if h is not None]
avg_hr = statistics.mean(hr_vals)
max_hr = max(hr_vals)
hz_time = {z[0]: 0 for z in HR_ZONES}
for h in hr_vals:
    for name, lo, hi in HR_ZONES:
        if lo <= h <= hi:
            hz_time[name] += 1
            break

# HR drift / decoupling at fixed-power band
band_idx = [i for i in moving_idx if power[i] is not None and 130 <= power[i] <= 160]
hr_drift_msg = "(insufficient samples)"
if len(band_idx) > 200:
    h = len(band_idx) // 2
    first_band = band_idx[:h]
    second_band = band_idx[h:]
    bf_p = statistics.mean([power[i] for i in first_band])
    bs_p = statistics.mean([power[i] for i in second_band])
    bf_h = statistics.mean([hr[i] for i in first_band if hr[i] is not None])
    bs_h = statistics.mean([hr[i] for i in second_band if hr[i] is not None])
    drift_bpm = bs_h - bf_h
    drift_pct = drift_bpm / bf_h * 100
    bf_wh = bf_p / bf_h
    bs_wh = bs_p / bs_h
    decoupling = (bf_wh - bs_wh) / bf_wh * 100
    hr_drift_msg = (
        f"In 130-160 W band ({len(band_idx)} sec):\n"
        f"    First half:  power {bf_p:.0f} W, HR {bf_h:.0f} bpm  →  W/HR {bf_wh:.3f}\n"
        f"    Second half: power {bs_p:.0f} W, HR {bs_h:.0f} bpm  →  W/HR {bs_wh:.3f}\n"
        f"    HR drift:    {drift_bpm:+.1f} bpm ({drift_pct:+.1f}%)\n"
        f"    Pw:HR decoupling: {decoupling:+.1f}%"
    )

# Cadence
cad_vals = [c for c in cad if c is not None and c > 30]
avg_cad = statistics.mean(cad_vals) if cad_vals else 0
pedaling_sec = len(cad_vals)
freewheel_sec = sum(1 for c in cad if c is not None and c <= 30)

# Elevation gain via 1m threshold smoothed
asc = 0
alt_clean = [a for a in alt if a is not None]
if alt_clean:
    smoothed = []
    w = 5
    for i in range(len(alt_clean)):
        s = max(0, i - w + 1)
        smoothed.append(sum(alt_clean[s:i+1]) / (i - s + 1))
    for i in range(1, len(smoothed)):
        d = smoothed[i] - smoothed[i-1]
        if d > 0.2:
            asc += d
total_dist_m = dist[-1] if dist[-1] else 0

# Stops
stops = []
in_stop = False
stop_start = 0
for i, m in enumerate(moving_mask):
    if not m and not in_stop:
        stop_start = i
        in_stop = True
    elif m and in_stop:
        dur = i - stop_start
        if dur > 30:
            stops.append((stop_start, dur))
        in_stop = False
if in_stop:
    dur = len(moving_mask) - stop_start
    if dur > 30:
        stops.append((stop_start, dur))

# Climb detection — find sustained ascent segments (>30s, gain >25m, gradient >3%)
# Smooth altitude first
sm_alt = []
w = 30
for i in range(len(alt)):
    s = max(0, i - w + 1)
    e = i + 1
    vals = [a for a in alt[s:e] if a is not None]
    sm_alt.append(sum(vals)/len(vals) if vals else None)

# Walk forward, identify climb segments
climbs = []
i = 0
while i < len(sm_alt) - 60:
    if sm_alt[i] is None:
        i += 1
        continue
    # Check next 60s — is it generally rising?
    start = i
    while i < len(sm_alt) - 1 and sm_alt[i+1] is not None and sm_alt[i+1] >= sm_alt[i] - 1:
        i += 1
    if i - start > 60 and sm_alt[i] - sm_alt[start] > 25:
        # Compute averages over this segment
        seg_p = [power[k] for k in range(start, i+1) if power[k] is not None]
        seg_h = [hr[k] for k in range(start, i+1) if hr[k] is not None]
        seg_dist = (dist[i] - dist[start]) if dist[i] and dist[start] else 0
        seg_gain = sm_alt[i] - sm_alt[start]
        seg_dur = i - start
        if seg_dist > 200:
            climbs.append({
                "start_idx": start,
                "duration": seg_dur,
                "distance": seg_dist,
                "gain": seg_gain,
                "gradient": seg_gain / seg_dist * 100,
                "vam": seg_gain / seg_dur * 3600,
                "avg_p": statistics.mean(seg_p) if seg_p else 0,
                "avg_h": statistics.mean(seg_h) if seg_h else 0,
            })
    i += 1

# Sort climbs by gain, keep top 3
climbs.sort(key=lambda c: -c["gain"])
top_climbs = climbs[:3]

# Output
print("=" * 72)
print(f"  RIDE ANALYSIS — {start_ts.strftime('%Y-%m-%d %H:%M')} (FIT UTC)")
print(f"  Distance {total_dist_m/1000:.2f} km  Elev gain {asc:.0f} m  Weight {WEIGHT} kg")
print("=" * 72)

print(f"\nElapsed:     {fmt(elapsed)}    Moving: {fmt(moving_time)}    Stops: {fmt(elapsed-moving_time)} ({len(stops)} stops >30s)")
if stops:
    print(f"             Longest stop: {fmt(max(s[1] for s in stops))}    "
          f"Total stop time / elapsed: {(elapsed-moving_time)/elapsed*100:.0f}%")

print(f"\n-- POWER (FTP ref {FTP} W = {FTP/WEIGHT:.2f} W/kg) --")
print(f"Avg (moving):           {avg_p:5.1f} W   ({avg_p/FTP*100:.0f}% FTP, {avg_p/WEIGHT:.2f} W/kg)")
print(f"Avg (pedaling only):    {avg_p_pedaling:5.1f} W   ({avg_p_pedaling/FTP*100:.0f}% FTP)")
print(f"Normalized Power (NP):  {np_val:5.1f} W   ({np_val/FTP*100:.0f}% FTP, {np_val/WEIGHT:.2f} W/kg)")
print(f"Max power:              {max_p:5.0f} W")
print(f"Intensity Factor (IF):  {IF:.2f}     {'(endurance)' if IF<0.75 else '(tempo)' if IF<0.85 else '(threshold)' if IF<0.95 else '(over-threshold)'}")
print(f"Training Stress (TSS):  {TSS:.0f}")
print(f"Total work:             {total_kj:.0f} kJ  ≈ {total_kj:.0f} kcal (from power, ~25% efficiency)")

print(f"\n-- BEST EFFORTS (mean power over rolling window) --")
print(f"  5 sec:    {best_5s:5.0f} W")
print(f"  1 min:    {best_1m:5.0f} W")
print(f"  5 min:    {best_5m:5.0f} W")
print(f"  20 min:   {best_20m:5.0f} W   (95% of best-20 ≈ FTP proxy: {best_20m*0.95:.0f} W)")
print(f"  60 min:   {best_60m:5.0f} W")

print(f"\n-- POWER ZONES (moving time only) --")
for name in [z[0] for z in POWER_ZONES] + ["Coasting (0W)"]:
    secs = pz_time[name]
    pct = secs / moving_time * 100 if moving_time else 0
    bar = "█" * int(pct/2)
    print(f"  {name:24s} {fmt(secs):>9s}  {pct:5.1f}%  {bar}")

print(f"\n-- HEART RATE --")
print(f"Avg HR:                 {avg_hr:.0f} bpm")
print(f"Max HR:                 {max_hr} bpm")

print(f"\n-- HR ZONES (all records) --")
for name in [z[0] for z in HR_ZONES]:
    secs = hz_time[name]
    pct = secs / len(hr_vals) * 100 if hr_vals else 0
    bar = "█" * int(pct/2)
    print(f"  {name:18s} {fmt(secs):>9s}  {pct:5.1f}%  {bar}")

print(f"\n-- HR DRIFT (aerobic decoupling) --")
print(f"  {hr_drift_msg}")
print(f"  Interpretation: <3% = aerobic resilience intact, 3-5% = adequate, >5% = under-fueled/under-recovered")

print(f"\n-- CADENCE --")
print(f"Avg pedaling cadence:   {avg_cad:.1f} rpm")
print(f"Pedaling time:          {fmt(pedaling_sec)} ({pedaling_sec/elapsed*100:.0f}% of elapsed)")
print(f"Freewheeling time:      {fmt(freewheel_sec)} ({freewheel_sec/elapsed*100:.0f}% of elapsed)")

print(f"\n-- TOP CLIMBS (sorted by gain) --")
if top_climbs:
    for i, c in enumerate(top_climbs, 1):
        print(f"  #{i}  {fmt(c['duration'])}  {c['distance']/1000:.2f} km  "
              f"+{c['gain']:.0f}m  {c['gradient']:.1f}% avg  "
              f"VAM {c['vam']:.0f} m/h  "
              f"avg power {c['avg_p']:.0f} W ({c['avg_p']/WEIGHT:.2f} W/kg)  "
              f"avg HR {c['avg_h']:.0f}")
else:
    print("  (no significant climbs detected)")

print()
