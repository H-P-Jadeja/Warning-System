"""Fake, threshold-based stand-in for dashboard development.

The outputs from this module are NOT model predictions. The real prediction
function is ``ml/predict.py``; this stub exists only to let dashboard work
proceed without loading the trained model.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import pandas as pd


LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
REQUIRED_READING_FIELDS = (
    "lake_id",
    "timestamp",
    "water_level_m",
    "seepage_rate",
    "dam_tilt_deg",
    "inflow_rate",
    "seismic_activity",
    "rainfall_mm",
    "water_temp_c",
    "lake_area_km2",
)
LEAD_TIME_HOURS = {
    "LOW": None,
    "MEDIUM": 36,
    "HIGH": 18,
    "CRITICAL": 6,
}

# Each sensor's medium, high, and critical thresholds, in its native units.
SENSOR_THRESHOLDS = {
    "water_level_m": (14.0, 15.5, 17.0),
    "seepage_rate": (2.0, 2.8, 3.6),
    "dam_tilt_deg": (0.6, 0.9, 1.2),
    "inflow_rate": (12.0, 15.0, 18.0),
    "seismic_activity": (0.08, 0.15, 0.25),
}


def _numeric_or_missing(value: Any, field: str) -> float | None:
    """Convert sensor input to float, mapping None and NaN to missing."""
    if value is None or pd.isna(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Sensor field {field!r} must be numeric or missing") from exc
    if not math.isfinite(number):
        raise ValueError(f"Sensor field {field!r} must be finite or missing")
    return number


def _history_records(history: Any) -> list[Mapping[str, Any]]:
    """Validate and normalize optional history like the real function does."""
    if history is None:
        return []
    if isinstance(history, pd.DataFrame):
        records = history.to_dict(orient="records")
    elif isinstance(history, (list, tuple)):
        records = []
        for index, row in enumerate(history):
            if isinstance(row, pd.Series):
                records.append(row.to_dict())
            elif isinstance(row, Mapping):
                records.append(row)
            else:
                raise ValueError(
                    f"history item {index} must be a mapping or pandas Series"
                )
    else:
        raise ValueError("history must be None, a list of readings, or a pandas DataFrame")

    # The real predictor reads these three fields from the six-hour reference.
    if len(records) >= 6:
        six_hours_ago = records[-6]
        for field in ("water_level_m", "seepage_rate", "dam_tilt_deg"):
            if field in six_hours_ago:
                _numeric_or_missing(six_hours_ago[field], field)
    return records


def predict_risk(reading: dict, history: list | None = None) -> dict:
    """Return a deterministic, threshold-based dashboard stand-in result.

    ``history`` accepts the same optional oldest-first list or DataFrame as the
    real predictor. It is validated for compatibility but does not affect this
    fake threshold calculation.
    """
    if not isinstance(reading, Mapping):
        raise ValueError("reading must be a mapping containing the required fields")
    missing = [field for field in REQUIRED_READING_FIELDS if field not in reading]
    if missing:
        raise ValueError("reading is missing required fields: " + ", ".join(missing))

    _history_records(history)
    sensor_values = {
        field: _numeric_or_missing(reading[field], field)
        for field in REQUIRED_READING_FIELDS[2:]
    }

    level_index = 0
    factor_scores: dict[str, float] = {}
    for field, (medium, high, critical) in SENSOR_THRESHOLDS.items():
        value = sensor_values[field]
        if value is None:
            factor_scores[field] = 0.0
            continue

        severity = 0
        if value >= medium:
            severity = 1
        if value >= high:
            severity = 2
        if value >= critical:
            severity = 3
        level_index = max(level_index, severity)
        factor_scores[field] = max(0.0, (value - medium) / (critical - medium))

    risk_level = LEVELS[level_index]
    risk_score = float(level_index / 3.0)
    top_factors = sorted(
        factor_scores,
        key=lambda field: factor_scores[field],
        reverse=True,
    )[:3]

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "level_index": int(level_index),
        "top_factors": top_factors,
        "estimated_lead_time_hrs": LEAD_TIME_HOURS[risk_level],
    }


if __name__ == "__main__":
    normal_reading = {
        "lake_id": "SL001",
        "timestamp": "2024-08-01T10:00:00",
        "water_level_m": 12.2,
        "seepage_rate": 1.4,
        "dam_tilt_deg": 0.32,
        "inflow_rate": 8.3,
        "seismic_activity": 0.03,
        "rainfall_mm": 2.0,
        "water_temp_c": 3.0,
        "lake_area_km2": 1.31,
    }
    extreme_reading = {
        **normal_reading,
        "timestamp": "2024-08-01T11:00:00",
        "water_level_m": 18.0,
        "seepage_rate": 4.2,
        "dam_tilt_deg": 1.4,
        "inflow_rate": 21.0,
        "seismic_activity": 0.32,
    }

    print("Normal reading (fake dashboard stub):")
    print(predict_risk(normal_reading))
    print("Extreme reading (fake dashboard stub):")
    print(predict_risk(extreme_reading))
