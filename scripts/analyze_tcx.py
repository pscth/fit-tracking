#!/usr/bin/env python3
"""Analyze a Garmin TCX file.

FTP and weight are read from scripts/athlete.json (override with --ftp / --weight).
"""
import argparse, json, sys, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import statistics
from pathlib import Path

ATHLETE_FALLBACK = {"ftp": 210, "weight": 88.48}


def load_athlete():
    cfg = Path(__file__).parent / "athlete.json"
    if not cfg.exists():
        return ATHLETE_FALLBACK
    with open(cfg) as f:
        data = json.load(f)
    return {**ATHLETE_FALLBACK, **{k: v for k, v in data.items() if not k.startswith("_")}}


_ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
_ap.add_argument("path", help="Path to .tcx file")
_ap.add_argument("--ftp", type=int, help="Override FTP from athlete.json")
_ap.add_argument("--weight", type=float, help="Override weight (kg) from athlete.json")
_args = _ap.parse_args()

_athlete = load_athlete()
TCX = _args.path
FTP = _args.ftp if _args.ftp is not None else _athlete["ftp"]
WEIGHT = _args.weight if _args.weight is not None else _athlete["weight"]

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
moving_idx = [i for i, r in enumerate(records) if r.get("speed", 0) > 0.5]
moving_time = len(moving_idx)
print(f"Moving time: {timedelta(seconds=moving_time)}  ({moving_time/elapsed*100:.0f}% of elapsed)")

# Power
power = [r.get("power", 0) or 0 for r in records]
pmove = [power[i] for i in moving_idx]
nonzero_p = [p for p in pmove if p > 0]
avg_p = statistics.mean(pmove) if pmove else 0
avg_p_pedal = statistics.mean(nonzero_p) if nonzero_p else 0
max_p = max(pmove) if pmove else 0

# NP
rolling = []
win = 30
for i in range(len(pmove)):
    s = max(0, i - win + 1)
    seg = pmove[s:i+1]
    rolling.append(sum(seg) / len(seg))
np_val = (sum(p**4 for p in rolling) / len(rolling)) ** 0.25 if rolling else 0
IF = np_val / FTP
TSS = (moving_time * np_val * IF) / (FTP * 3600) * 100

# Best efforts
def best(series, win_s):
    if len(series) < win_s:
        return 0
    cs = [0]
    for v in series:
        cs.append(cs[-1] + v)
    b = 0
    for i in range(win_s, len(cs)):
        m = (cs[i] - cs[i-win_s]) / win_s
        if m > b:
            b = m
    return b

best_5s = best(pmove, 5)
best_1m = best(pmove, 60)
best_5m = best(pmove, 300)
best_20m = best(pmove, 1200)

# Total work
total_kj = sum(pmove) / 1000

# HR
hr_vals = [r.get("hr") for r in records if r.get("hr")]
avg_hr = statistics.mean(hr_vals) if hr_vals else 0
max_hr = max(hr_vals) if hr_vals else 0

# Cadence
cad_vals = [r.get("cadence") for r in records if r.get("cadence") and r.get("cadence") > 30]
avg_cad = statistics.mean(cad_vals) if cad_vals else 0

# HR drift in 130-170 W band
band = [i for i in moving_idx if power[i] and 130 <= power[i] <= 170]
hr_drift_msg = "(insufficient samples)"
if len(band) > 200:
    h = len(band) // 2
    bf = band[:h]; bs = band[h:]
    bf_p = statistics.mean([power[i] for i in bf])
    bs_p = statistics.mean([power[i] for i in bs])
    bf_h = statistics.mean([records[i].get("hr", 0) for i in bf if records[i].get("hr")])
    bs_h = statistics.mean([records[i].get("hr", 0) for i in bs if records[i].get("hr")])
    drift = bs_h - bf_h
    decoupling = ((bf_p / bf_h) - (bs_p / bs_h)) / (bf_p / bf_h) * 100
    hr_drift_msg = (f"In 130-170 W band ({len(band)} sec):\n"
                    f"    First half:  power {bf_p:.0f} W, HR {bf_h:.0f} bpm\n"
                    f"    Second half: power {bs_p:.0f} W, HR {bs_h:.0f} bpm\n"
                    f"    HR drift: {drift:+.1f} bpm  |  Pw:HR decoupling: {decoupling:+.1f}%")

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
