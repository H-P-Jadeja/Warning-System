"""Synthetic hourly sensor episodes for the GLOF early-warning prototype.

Sensor data are simulated, not measurements from South Lhonak Lake. The
scenario and label conventions follow Part 3.3 of the project handbook.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

LAKE_ID = "SL001"
SENSOR_COLUMNS = [
    "water_level_m",
    "seepage_rate",
    "dam_tilt_deg",
    "inflow_rate",
    "seismic_activity",
    "rainfall_mm",
    "water_temp_c",
    "lake_area_km2",
]
EPISODE_COLUMNS = [
    "lake_id", "timestamp", "hour", *SENSOR_COLUMNS, "label", "hours_to_event"
]
GLOF_TYPES = ("rain", "seepage", "seismic")


def _normal_readings(rng: np.random.Generator, hours: int) -> pd.DataFrame:
    """Generate baseline sensor readings with per-episode offsets and noise."""
    t = np.arange(hours)
    # Fixed per-episode offsets make the model encounter different lakes/sensors.
    water_offset = rng.normal(0, 0.45)
    seepage_offset = rng.normal(0, 0.08)
    tilt_offset = rng.normal(0, 0.025)
    inflow_offset = rng.normal(0, 0.5)
    temp_offset = rng.normal(0, 0.12)
    area_offset = rng.normal(0, 0.015)
    return pd.DataFrame({
        "water_level_m": 12 + water_offset + 0.35 * np.sin(t * 2 * np.pi / 24) + rng.normal(0, 0.16, hours),
        "seepage_rate": 1.2 + seepage_offset + rng.normal(0, 0.10, hours),
        "dam_tilt_deg": 0.3 + tilt_offset + rng.normal(0, 0.025, hours),
        "inflow_rate": 8 + inflow_offset + rng.normal(0, 0.65, hours),
        "seismic_activity": np.abs(rng.normal(0.02, 0.012, hours)),
        "rainfall_mm": rng.gamma(shape=1.2, scale=1.6, size=hours),
        "water_temp_c": 3 + temp_offset + rng.normal(0, 0.18, hours),
        "lake_area_km2": 1.3 + area_offset + 0.0002 * t + rng.normal(0, 0.004, hours),
    })


def _add_sensor_faults(rng: np.random.Generator, df: pd.DataFrame) -> None:
    """Add sparse missing readings and implausible spikes as false-alarm traps."""
    # Faults are deliberately confined to otherwise normal episodes.
    for column in SENSOR_COLUMNS:
        if rng.random() < 0.30:
            i = int(rng.integers(0, len(df)))
            df.loc[i, column] = np.nan
        if rng.random() < 0.24:
            i = int(rng.integers(0, len(df)))
            spike = {
                "water_level_m": 2.3,
                "seepage_rate": 1.8,
                "dam_tilt_deg": 0.65,
                "inflow_rate": 5.0,
                "seismic_activity": 0.18,
                "rainfall_mm": 18.0,
                "water_temp_c": 1.2,
                "lake_area_km2": 0.08,
            }[column]
            df.loc[i, column] += spike


def simulate_episode(scenario: str = "glof", seed: int = 0, hours: int = 240) -> pd.DataFrame:
    """Return one reproducible hourly episode of simulated sensor readings.

    Args:
        scenario: ``"glof"`` for a precursor event, or ``"normal"``.
        seed: Seed for deterministic generation.
        hours: Requested number of hours; must be at least 72.

    A GLOF episode includes the outburst hour as its final row. Its event type
    is selected reproducibly from rain, seepage/piping, and seismic/landslide.
    Labels are 0 before the 48-hour warning window, 1 below 48 hours, 2 below
    24 hours, and 3 below 12 hours to the event.
    """
    scenario = scenario.lower().strip()
    if scenario not in {"glof", "normal"}:
        raise ValueError("scenario must be 'glof' or 'normal'")
    if not isinstance(hours, (int, np.integer)) or hours < 72:
        raise ValueError("hours must be an integer >= 72")

    rng = np.random.default_rng(seed)
    df = _normal_readings(rng, int(hours))
    event_hour: int | None = None
    labels = np.zeros(hours, dtype=np.int64)
    hours_to_event = np.full(hours, np.nan, dtype=float)

    if scenario == "normal":
        _add_sensor_faults(rng, df)
    else:
        # Keep a useful baseline period and vary the event location by seed.
        event_hour = int(rng.integers(max(60, hours - 120), hours))
        t = np.arange(hours)
        remaining = event_hour - t
        ramp = np.clip(1 - remaining / 72.0, 0, 1)
        event_type = GLOF_TYPES[int(rng.integers(0, len(GLOF_TYPES)))]

        if event_type == "rain":
            # Heavy rain and increased inflow lead; lake/dam response follows.
            df["rainfall_mm"] += 19 * ramp**1.25 * rng.uniform(0.65, 1.0, hours)
            df["inflow_rate"] += 13 * ramp**1.4
            df["water_level_m"] += 3.6 * ramp**1.7
            df["lake_area_km2"] += 0.13 * ramp
            df["seepage_rate"] += 1.8 * ramp**2
            df["dam_tilt_deg"] += 0.65 * ramp**2
        elif event_type == "seepage":
            # Progressive piping indicators without an early rain signal.
            df["seepage_rate"] += 4.0 * ramp**1.7
            df["dam_tilt_deg"] += 1.4 * ramp**1.8
            df["water_level_m"] += 2.8 * ramp**1.6
            df["inflow_rate"] += 4.5 * ramp
            df["lake_area_km2"] += 0.10 * ramp
        else:
            # A relatively sudden trigger followed by a fast hydrological rise.
            trigger = (t >= event_hour - 10).astype(float)
            df["seismic_activity"] += 0.22 * trigger * rng.uniform(0.65, 1.0, hours)
            fast_rise = np.clip((t - (event_hour - 8)) / 8.0, 0, 1)
            df["water_level_m"] += 3.6 * fast_rise
            df["inflow_rate"] += 11 * fast_rise
            df["seepage_rate"] += 2.2 * fast_rise
            df["dam_tilt_deg"] += 0.8 * fast_rise
            df["lake_area_km2"] += 0.10 * fast_rise

        labels[remaining < 48] = 1
        labels[remaining < 24] = 2
        labels[remaining < 12] = 3
        hours_to_event[:] = remaining.astype(float)

        # Event occurs at the final sample; no post-outburst observations.
        df = df.iloc[: event_hour + 1].copy()
        labels = labels[: event_hour + 1]
        hours_to_event = hours_to_event[: event_hour + 1]

    n = len(df)
    out = df.copy()
    out.insert(0, "hour", np.arange(n, dtype=int))
    out.insert(0, "timestamp", pd.date_range("2024-08-01", periods=n, freq="h").astype(str))
    out.insert(0, "lake_id", LAKE_ID)
    out["label"] = labels
    out["hours_to_event"] = hours_to_event
    return out[EPISODE_COLUMNS].reset_index(drop=True)


def make_dataset(n_episodes: int = 100, seed: int = 0, hours: int = 240) -> pd.DataFrame:
    """Generate a balanced dataset, half normal and half GLOF episodes.

    The returned frame combines episodes and adds ``episode_id`` and
    ``scenario`` columns for safe episode-wise train/test splitting.
    An odd requested count produces one extra normal episode.
    """
    if not isinstance(n_episodes, (int, np.integer)) or n_episodes < 2:
        raise ValueError("n_episodes must be an integer >= 2")
    rng = np.random.default_rng(seed)
    glof_count = n_episodes // 2
    normal_count = n_episodes - glof_count
    scenarios = ["glof"] * glof_count + ["normal"] * normal_count
    rng.shuffle(scenarios)
    episodes = []
    for episode_id, scenario in enumerate(scenarios):
        episode_seed = int(rng.integers(0, np.iinfo(np.int32).max))
        episode = simulate_episode(scenario, seed=episode_seed, hours=hours)
        episode.insert(0, "scenario", scenario)
        episode.insert(0, "episode_id", episode_id)
        episodes.append(episode)
    return pd.concat(episodes, ignore_index=True)
