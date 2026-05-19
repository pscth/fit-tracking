"""Shared analytics for the FIT/TCX ride analyzers.

Format-specific parsers (analyze_fit.py, analyze_tcx.py) extract a canonical
set of series (power, hr, speed, altitude, ...) from a file and pass them to
these helpers. Anything that doesn't depend on the file format lives here.
"""
import argparse
import json
import statistics
import sys
from datetime import timedelta
from pathlib import Path


SCRIPTS_DIR = Path(__file__).parent
MOVING_SPEED_THRESHOLD = 0.5  # m/s — "moving" is anything above ~1.8 km/h


# --- athlete config + CLI -------------------------------------------------

def load_athlete(required=("ftp", "weight")):
    """Read scripts/athlete.json. Exit with a clear message if missing or incomplete."""
    cfg = SCRIPTS_DIR / "athlete.json"
    if not cfg.exists():
        sys.exit(
            "Missing scripts/athlete.json. Copy scripts/athlete.example.json to "
            "scripts/athlete.json and fill in your FTP / weight / hr_max_bpm_est."
        )
    with open(cfg) as f:
        data = json.load(f)
    athlete = {k: v for k, v in data.items() if not k.startswith("_")}
    missing = [k for k in required if athlete.get(k) is None]
    if missing:
        sys.exit(f"athlete.json missing required field(s): {', '.join(missing)}")
    return athlete


def build_argparser(description, path_help, with_hr_max=False):
    p = argparse.ArgumentParser(description=description)
    p.add_argument("path", help=path_help)
    p.add_argument("--ftp", type=int, help="Override FTP from athlete.json")
    p.add_argument("--weight", type=float, help="Override weight (kg) from athlete.json")
    if with_hr_max:
        p.add_argument("--hr-max", type=int, dest="hr_max",
                       help="Override hr_max_bpm_est from athlete.json")
    return p


# --- zones ---------------------------------------------------------------

def build_power_zones(athlete, ftp):
    """7-zone Coggan power table.

    Z2/Z3/Z4 come from athlete.json's `power_zones_w` when all three are
    present (the user's chosen breakpoints). Z1 sits below Z2; Z5/Z6/Z7
    above Z4 via standard Coggan FTP percentages (105/120/150%). Falls back
    to a fully FTP-derived table if `power_zones_w` is incomplete.
    """
    pzw = athlete.get("power_zones_w", {})
    z2, z3, z4 = pzw.get("z2_endurance"), pzw.get("z3_tempo"), pzw.get("z4_threshold")
    if z2 and z3 and z4:
        return [
            ("Z1 Active recovery", 0,                     z2[0] - 1),
            ("Z2 Endurance",       z2[0],                 z2[1]),
            ("Z3 Tempo",           z3[0],                 z3[1]),
            ("Z4 Threshold",       z4[0],                 z4[1]),
            ("Z5 VO2max",          z4[1] + 1,             int(1.20 * ftp)),
            ("Z6 Anaerobic",       int(1.20 * ftp) + 1,   int(1.50 * ftp)),
            ("Z7 Sprint",          int(1.50 * ftp) + 1,   99999),
        ]
    return [
        ("Z1 Active recovery", 0,                   int(0.55 * ftp)),
        ("Z2 Endurance",       int(0.55 * ftp) + 1, int(0.75 * ftp)),
        ("Z3 Tempo",           int(0.75 * ftp) + 1, int(0.90 * ftp)),
        ("Z4 Threshold",       int(0.90 * ftp) + 1, int(1.05 * ftp)),
        ("Z5 VO2max",          int(1.05 * ftp) + 1, int(1.20 * ftp)),
        ("Z6 Anaerobic",       int(1.20 * ftp) + 1, int(1.50 * ftp)),
        ("Z7 Sprint",          int(1.50 * ftp) + 1, 99999),
    ]


def build_hr_zones(hr_max):
    """5-zone %HRmax HR table. Returns None if HRmax is falsy."""
    if not hr_max:
        return None
    return [
        ("Z1 Recovery",  0,                       int(0.60 * hr_max)),
        ("Z2 Endurance", int(0.60 * hr_max) + 1,  int(0.70 * hr_max)),
        ("Z3 Tempo",     int(0.70 * hr_max) + 1,  int(0.80 * hr_max)),
        ("Z4 Threshold", int(0.80 * hr_max) + 1,  int(0.90 * hr_max)),
        ("Z5 VO2max",    int(0.90 * hr_max) + 1,  999),
    ]


# --- analytics -----------------------------------------------------------

def format_duration(seconds):
    return str(timedelta(seconds=int(seconds)))


def normalized_power(power_series, window=30):
    """NP: rolling-mean (30 s default) → 4th power → mean → 0.25 power."""
    if not power_series:
        return 0
    rolling = []
    for i in range(len(power_series)):
        s = max(0, i - window + 1)
        seg = power_series[s:i+1]
        rolling.append(sum(seg) / len(seg))
    return (sum(p**4 for p in rolling) / len(rolling)) ** 0.25


def intensity_factor(np_val, ftp):
    return np_val / ftp if ftp else 0


def training_stress(np_val, moving_time_s, ftp):
    """TSS = (moving_seconds * NP * IF) / (FTP * 3600) * 100."""
    if not ftp:
        return 0
    if_val = intensity_factor(np_val, ftp)
    return (moving_time_s * np_val * if_val) / (ftp * 3600) * 100


def best_mean_power(series, window_s):
    """Sliding-window best mean over `window_s` seconds. 0 if series shorter than window."""
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


def zone_distribution(values, zones, coast_bucket_name=None):
    """Time-in-zone (seconds) over a value series. Returns dict name → seconds.

    If `coast_bucket_name` is set, zero values are counted under that key
    instead of falling through to the zone table — used for power zones
    where 0 W means coasting, not "Z1".
    """
    counts = {z[0]: 0 for z in zones}
    if coast_bucket_name is not None:
        counts[coast_bucket_name] = 0
    for v in values:
        if coast_bucket_name is not None and v == 0:
            counts[coast_bucket_name] += 1
            continue
        for name, lo, hi in zones:
            if lo <= v <= hi:
                counts[name] += 1
                break
    return counts


def hr_drift(power_series, hr_series, moving_idx, band_low, band_high, min_samples=200):
    """Pw:HR decoupling test on a fixed power band.

    `power_series` and `hr_series` are same-length lists indexed by record.
    `moving_idx` is the subset of indices to consider (typically the moving
    mask). Values that are None / falsy in either series are skipped.

    Returns a dict of {n_samples, first_p, first_h, first_wh, second_p,
    second_h, second_wh, drift_bpm, drift_pct, decoupling} — or None if
    fewer than `min_samples` samples fall in the band.
    """
    band_idx = [
        i for i in moving_idx
        if power_series[i] is not None and band_low <= power_series[i] <= band_high
        and hr_series[i] is not None
    ]
    if len(band_idx) <= min_samples:
        return None
    h = len(band_idx) // 2
    first, second = band_idx[:h], band_idx[h:]
    bf_p = statistics.mean([power_series[i] for i in first])
    bs_p = statistics.mean([power_series[i] for i in second])
    bf_h = statistics.mean([hr_series[i] for i in first])
    bs_h = statistics.mean([hr_series[i] for i in second])
    drift_bpm = bs_h - bf_h
    drift_pct = drift_bpm / bf_h * 100
    bf_wh = bf_p / bf_h
    bs_wh = bs_p / bs_h
    decoupling = (bf_wh - bs_wh) / bf_wh * 100
    return {
        "n_samples": len(band_idx),
        "first_p": bf_p, "first_h": bf_h, "first_wh": bf_wh,
        "second_p": bs_p, "second_h": bs_h, "second_wh": bs_wh,
        "drift_bpm": drift_bpm, "drift_pct": drift_pct,
        "decoupling": decoupling,
    }


def format_hr_drift(drift, band_low, band_high):
    """Render a hr_drift() result for printing. None → '(insufficient samples)'."""
    if drift is None:
        return "(insufficient samples)"
    return (
        f"In {band_low}-{band_high} W band ({drift['n_samples']} sec):\n"
        f"    First half:  power {drift['first_p']:.0f} W, HR {drift['first_h']:.0f} bpm  →  W/HR {drift['first_wh']:.3f}\n"
        f"    Second half: power {drift['second_p']:.0f} W, HR {drift['second_h']:.0f} bpm  →  W/HR {drift['second_wh']:.3f}\n"
        f"    HR drift:    {drift['drift_bpm']:+.1f} bpm ({drift['drift_pct']:+.1f}%)\n"
        f"    Pw:HR decoupling: {drift['decoupling']:+.1f}%"
    )
