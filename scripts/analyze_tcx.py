#!/usr/bin/env python3
"""Analyze a Garmin TCX file.

FTP and weight are read from scripts/athlete.json (override with --ftp / --weight).
"""
import statistics
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from ride_analysis import (
    MOVING_SPEED_THRESHOLD,
    best_mean_power,
    build_argparser,
    build_power_zones,
    format_duration,
    format_hr_drift,
    hr_drift,
    intensity_factor,
    load_athlete,
    normalized_power,
    training_stress,
)

_args = build_argparser(__doc__.splitlines()[0], "Path to .tcx file").parse_args()
_athlete = load_athlete()
TCX = _args.path
FTP = _args.ftp if _args.ftp is not None else _athlete.get("ftp")
WEIGHT = _args.weight if _args.weight is not None else _athlete.get("weight")

# HR-drift / decoupling test band = Z2 endurance from athlete.json's
# power_zones_w (or FTP-derived if absent). Scales with FTP.
_POWER_ZONES = build_power_zones(_athlete, FTP)
HR_DRIFT_BAND = (_POWER_ZONES[1][1], _POWER_ZONES[1][2])

NS = {
    "tcd": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2",
    "ns3": "http://www.garmin.com/xmlschemas/ActivityExtension/v2",
}

tree = ET.parse(TCX)
root = tree.getroot()

records = []
for tp in root.iter(f"{{{NS['tcd']}}}Trackpoint"):
    rec = {}
    t = tp.find(f"{{{NS['tcd']}}}Time")
    if t is not None:
        rec["time"] = datetime.fromisoformat(t.text.replace("Z", "+00:00"))
    d = tp.find(f"{{{NS['tcd']}}}DistanceMeters")
    if d is not None:
        rec["distance"] = float(d.text)
    alt = tp.find(f"{{{NS['tcd']}}}AltitudeMeters")
    if alt is not None:
        rec["altitude"] = float(alt.text)
    hr = tp.find(f"{{{NS['tcd']}}}HeartRateBpm")
    if hr is not None:
        v = hr.find(f"{{{NS['tcd']}}}Value")
        if v is not None:
            rec["hr"] = int(v.text)
    cad = tp.find(f"{{{NS['tcd']}}}Cadence")
    if cad is not None:
        rec["cadence"] = int(cad.text)
    ext = tp.find(f"{{{NS['tcd']}}}Extensions")
    if ext is not None:
        tpx = ext.find(f"{{{NS['ns3']}}}TPX")
        if tpx is not None:
            sp = tpx.find(f"{{{NS['ns3']}}}Speed")
            if sp is not None:
                rec["speed"] = float(sp.text)
            wt = tpx.find(f"{{{NS['ns3']}}}Watts")
            if wt is not None:
                rec["power"] = int(wt.text)
    records.append(rec)

print(f"Records parsed: {len(records)}")
if not records:
    sys.exit(1)

start = records[0]["time"]
end = records[-1]["time"]
elapsed = (end - start).total_seconds()
total_dist = records[-1].get("distance", 0)
print(f"Elapsed: {timedelta(seconds=int(elapsed))}")
print(f"Distance: {total_dist/1000:.2f} km")

# Moving filter
moving_idx = [i for i, r in enumerate(records) if r.get("speed", 0) > MOVING_SPEED_THRESHOLD]
moving_time = len(moving_idx)
print(f"Moving time: {timedelta(seconds=moving_time)}  ({moving_time/elapsed*100:.0f}% of elapsed)")

# Series for shared analytics
power = [r.get("power", 0) or 0 for r in records]
hr_full = [r.get("hr") for r in records]
pmove = [power[i] for i in moving_idx]
nonzero_p = [p for p in pmove if p > 0]
avg_p = statistics.mean(pmove) if pmove else 0
avg_p_pedal = statistics.mean(nonzero_p) if nonzero_p else 0
max_p = max(pmove) if pmove else 0

np_val = normalized_power(pmove)
IF = intensity_factor(np_val, FTP)
TSS = training_stress(np_val, moving_time, FTP)

best_5s = best_mean_power(pmove, 5)
best_1m = best_mean_power(pmove, 60)
best_5m = best_mean_power(pmove, 300)
best_20m = best_mean_power(pmove, 1200)

total_kj = sum(pmove) / 1000

hr_vals = [h for h in hr_full if h]
avg_hr = statistics.mean(hr_vals) if hr_vals else 0
max_hr = max(hr_vals) if hr_vals else 0

cad_vals = [r.get("cadence") for r in records if r.get("cadence") and r.get("cadence") > 30]
avg_cad = statistics.mean(cad_vals) if cad_vals else 0

_drift = hr_drift(power, hr_full, moving_idx, *HR_DRIFT_BAND)
if _drift is None:
    hr_drift_msg = "(insufficient samples)"
else:
    hr_drift_msg = (
        f"In {HR_DRIFT_BAND[0]}-{HR_DRIFT_BAND[1]} W band ({_drift['n_samples']} sec):\n"
        f"    First half:  power {_drift['first_p']:.0f} W, HR {_drift['first_h']:.0f} bpm\n"
        f"    Second half: power {_drift['second_p']:.0f} W, HR {_drift['second_h']:.0f} bpm\n"
        f"    HR drift: {_drift['drift_bpm']:+.1f} bpm  |  Pw:HR decoupling: {_drift['decoupling']:+.1f}%"
    )

print(f"\n-- POWER (FTP {FTP}) --")
print(f"Avg (moving):      {avg_p:.0f} W ({avg_p/FTP*100:.0f}% FTP, {avg_p/WEIGHT:.2f} W/kg)")
print(f"Avg (pedaling):    {avg_p_pedal:.0f} W")
print(f"NP:                {np_val:.0f} W ({np_val/FTP*100:.0f}% FTP)")
print(f"Max:               {max_p} W")
print(f"IF:                {IF:.2f}")
print(f"TSS:               {TSS:.0f}")
print(f"Total work:        {total_kj:.0f} kJ ≈ {total_kj:.0f} kcal")

print(f"\n-- BEST EFFORTS --")
print(f"5 sec:   {best_5s:.0f} W")
print(f"1 min:   {best_1m:.0f} W")
print(f"5 min:   {best_5m:.0f} W")
print(f"20 min:  {best_20m:.0f} W (FTP proxy via 0.95 rule: {best_20m*0.95:.0f} W)")

print(f"\n-- HEART RATE --")
print(f"Avg: {avg_hr:.0f} bpm, Max: {max_hr} bpm")
print(f"\n-- CADENCE --")
print(f"Avg pedaling: {avg_cad:.1f} rpm")
print(f"\n-- HR DRIFT --")
print(f"  {hr_drift_msg}")
