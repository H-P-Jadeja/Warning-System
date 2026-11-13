"""Contract-compatible risk inference for the GLOF early-warning prototype.

The trained bundle is loaded lazily and cached once per Python process. Risk
scores are returned on the 0-100 scale requested by the project operator.
All predictions are based on synthetic training data and are not operational
warnings.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd


MODEL_PATH = Path(__file__).resolve().with_name("model.pkl")
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


@lru_cache(maxsize=1)
def _load_bundle() -> dict[str, Any]:
    """Load and cache the joblib model bundle once per process."""
    bundle = joblib.load(MODEL_PATH)
    required_bundle_fields = {
        "model",
        "imputer",
        "feature_names",
        "normal_mean",
        "normal_std",
        "risk_levels",
    }
    missing = sorted(required_bundle_fields.difference(bundle))
    if missing:
        raise ValueError(
            "Model bundle is missing required fields: " + ", ".join(missing)
        )
    return bundle


def _history_records(history: Any) -> list[Mapping[str, Any]]:
    """Normalize a history list or DataFrame to oldest-first row mappings."""
    if history is None:
        return []
    if isinstance(history, pd.DataFrame):
        return history.to_dict(orient="records")
    if isinstance(history, (list, tuple)):
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
        return records
    raise ValueError("history must be None, a list of readings, or a pandas DataFrame")


def _numeric_or_nan(value: Any) -> float:
    """Convert numeric readings to float while preserving missing values."""
    if value is None or pd.isna(value):
        return float("nan")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Sensor values must be numeric or missing; got {value!r}") from exc


def _get_stat(statistics: Any, feature: str) -> float:
    """Read a stored normal statistic from the bundle's mapping or sequence."""
    if isinstance(statistics, Mapping):
        value = statistics[feature]
    else:
        value = statistics[list(_load_bundle()["feature_names"]).index(feature)]
    return float(value)


def predict_risk(reading: dict, history: list | None = None) -> dict:
    """Estimate risk for one hourly lake reading.

    Args:
        reading: Mapping containing the eight sensor values plus ``lake_id``
            and ISO ``timestamp``.
        history: Earlier hourly readings, oldest first. A list of mappings or
            a pandas DataFrame is accepted. With at least six prior readings,
            the reading at ``history[-6]`` is used for each 6-hour change;
            otherwise those changes are zero.

    Returns the handbook fields ``risk_score``, ``risk_level``, ``level_index``,
    ``top_factors``, and ``estimated_lead_time_hrs``. The user-requested score
    scale is 0-100; level is the class with the highest predicted probability.
    """
    if not isinstance(reading, Mapping):
        raise ValueError("reading must be a mapping containing the required fields")
    missing = [field for field in REQUIRED_READING_FIELDS if field not in reading]
    if missing:
        raise ValueError("reading is missing required fields: " + ", ".join(missing))

    bundle = _load_bundle()
    feature_names = list(bundle["feature_names"])
    base_features = (
        "water_level_m",
        "seepage_rate",
        "dam_tilt_deg",
        "inflow_rate",
        "seismic_activity",
        "rainfall_mm",
        "water_temp_c",
        "lake_area_km2",
    )
    values: dict[str, float] = {
        name: _numeric_or_nan(reading[name]) for name in base_features
    }

    records = _history_records(history)
    change_sources = {
        "water_level_d6": "water_level_m",
        "seepage_d6": "seepage_rate",
        "tilt_d6": "dam_tilt_deg",
    }
    if len(records) >= 6:
        six_hours_ago = records[-6]
        for feature, source in change_sources.items():
            if source not in six_hours_ago or six_hours_ago[source] is None:
                values[feature] = float("nan")
            else:
                current = values[source]
                previous = _numeric_or_nan(six_hours_ago[source])
                values[feature] = current - previous
    else:
        values.update({feature: 0.0 for feature in change_sources})

    unknown_features = [feature for feature in feature_names if feature not in values]
    if unknown_features:
        raise ValueError(
            "Model bundle contains unsupported features: " + ", ".join(unknown_features)
        )
    row = pd.DataFrame([[values[feature] for feature in feature_names]], columns=feature_names)
    transformed = bundle["imputer"].transform(row)

    model = bundle["model"]
    probabilities = np.asarray(model.predict_proba(transformed)[0], dtype=float)
    classes = np.asarray(model.classes_)
    best_position = int(np.argmax(probabilities))
    predicted_class = int(classes[best_position])
    levels = list(bundle["risk_levels"])
    if predicted_class < 0 or predicted_class >= len(levels):
        raise ValueError(f"Model predicted unsupported risk class {predicted_class}")
    risk_level = levels[predicted_class]

    # Map class probabilities to the 0-100 range, evenly spanning the four levels.
    class_scores = np.asarray([0.0, 100.0 / 3.0, 200.0 / 3.0, 100.0])
    score_by_class = {int(label): class_scores[int(label)] for label in classes}
    risk_score = float(sum(probability * score_by_class[int(label)]
                           for probability, label in zip(probabilities, classes)))

    normal_mean = bundle["normal_mean"]
    normal_std = bundle["normal_std"]
    # Use the imputed row here too, so missing inputs follow the same policy
    # for explanations as they do for the classifier.
    row_values = pd.Series(transformed[0], index=feature_names)
    z_scores = {}
    for feature in feature_names:
        value = _numeric_or_nan(row_values[feature])
        mean = _get_stat(normal_mean, feature)
        std = max(abs(_get_stat(normal_std, feature)), 1e-9)
        # Missing current values are imputed for inference and have no raw z-score.
        z_scores[feature] = abs((value - mean) / std) if np.isfinite(value) else 0.0

    importances = np.asarray(
        getattr(model, "feature_importances_", np.ones(len(feature_names))), dtype=float
    )
    if len(importances) != len(feature_names):
        importances = np.ones(len(feature_names), dtype=float)
    factor_scores = {
        feature: z_scores[feature] * importances[index]
        for index, feature in enumerate(feature_names)
    }
    top_factors = sorted(factor_scores, key=factor_scores.get, reverse=True)[:3]

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "level_index": predicted_class,
        "top_factors": top_factors,
        "estimated_lead_time_hrs": LEAD_TIME_HOURS[risk_level],
    }
