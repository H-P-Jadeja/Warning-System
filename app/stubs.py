# app/stubs.py (temporary fakes that follow the contract in Part 3)
import numpy as np, pandas as pd

LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def predict_risk(reading, history=None):
    wl = max(0, reading["water_level_m"] - 12.5) / 4
    sp = max(0, reading["seepage_rate"] - 1.4) / 3
    tl = max(0, reading["dam_tilt_deg"] - 0.4) / 1.2
    s = float(min(1.0, (wl + sp + tl) / 3 * 1.5))
    idx = 0 if s < .25 else 1 if s < .5 else 2 if s < .75 else 3
    return {"risk_score": round(s, 3), "risk_level": LEVELS[idx], "level_index": idx,
            "top_factors": ["water_level_m", "seepage_rate", "dam_tilt_deg"],
            "estimated_lead_time_hrs": [None, 36, 18, 6][idx]}


def simulate_episode(scenario="glof", seed=0, hours=240):
    rng = np.random.default_rng(seed); n = hours; t = np.arange(n)
    r = np.clip((t - (n - 72)) / 72, 0, 1) if scenario == "glof" else np.zeros(n)
    df = pd.DataFrame({"lake_id": "SL001", "hour": t,
                       "timestamp": pd.date_range("2024-08-01", periods=n, freq="h").astype(str),
                       "water_level_m": 12 + rng.normal(0, .15, n) + 4 * r,
                       "seepage_rate": 1.2 + rng.normal(0, .1, n) + 3 * r,
                       "dam_tilt_deg": 0.3 + rng.normal(0, .03, n) + 1.2 * r,
                       "inflow_rate": 8 + rng.normal(0, .8, n) + 10 * r,
                       "seismic_activity": abs(rng.normal(.02, .01, n)) + .1 * r,
                       "rainfall_mm": rng.gamma(1, 2, n) + 10 * r,
                       "water_temp_c": 3 + rng.normal(0, .2, n) + r,
                       "lake_area_km2": 1.3 + .0002 * t + .15 * r})
    df["label"] = (r * 3.99).astype(int)
    df["hours_to_event"] = (n - 1 - t).astype(float) if scenario == "glof" else np.nan
    return df


def get_lake_area_series():
    d = pd.date_range("2016-01-01", "2023-09-01", freq="QS")
    return pd.DataFrame({"date": d, "area_km2": np.linspace(.9, 1.4, len(d)), "source": "stub"})