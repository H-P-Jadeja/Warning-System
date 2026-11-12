"""Train and evaluate the first GLOF risk classifier (handbook step A2).

Run from the repository root with either::

    python -m ml.train
    python ml/train.py

The saved ``ml/model.pkl`` is a joblib bundle containing the fitted classifier,
its fitted missing-value imputer, ordered feature names, and normal-data
statistics for the explainability step. All evaluation uses held-out episodes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split

try:  # Supports both `python -m ml.train` and `python ml/train.py`.
    from .simulator import SENSOR_COLUMNS, make_dataset
except ImportError:  # pragma: no cover - exercised by direct script invocation.
    from simulator import SENSOR_COLUMNS, make_dataset


LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
FEATURES = SENSOR_COLUMNS + ["water_level_d6", "seepage_d6", "tilt_d6"]
DEFAULT_EPISODES = 100
DEFAULT_SEED = 42
DEFAULT_TEST_SIZE = 0.20
MODEL_PATH = Path(__file__).resolve().parent / "model.pkl"


def build_features(dataset: pd.DataFrame) -> pd.DataFrame:
    """Add the three contract-defined six-hour changes within each episode."""
    required = {"episode_id", "hour", "label", "scenario", *SENSOR_COLUMNS}
    missing = sorted(required.difference(dataset.columns))
    if missing:
        raise ValueError(f"Dataset is missing required columns: {', '.join(missing)}")

    ordered = dataset.sort_values(["episode_id", "hour"], kind="stable").copy()
    grouped = ordered.groupby("episode_id", sort=False)
    ordered["water_level_d6"] = grouped["water_level_m"].diff(6).fillna(0.0)
    ordered["seepage_d6"] = grouped["seepage_rate"].diff(6).fillna(0.0)
    ordered["tilt_d6"] = grouped["dam_tilt_deg"].diff(6).fillna(0.0)
    return ordered


def train_and_evaluate(
    n_episodes: int = DEFAULT_EPISODES,
    seed: int = DEFAULT_SEED,
    test_size: float = DEFAULT_TEST_SIZE,
    model_path: str | Path = MODEL_PATH,
) -> dict[str, Any]:
    """Fit Gradient Boosting, report held-out class metrics, and save a bundle.

    The split is stratified on episode scenario and performed on episode IDs,
    so rows from the same episode cannot occur in both train and test sets.
    Missing sensor values are imputed using medians learned from training rows
    only. Normal reference statistics are computed from training normal episodes.
    """
    if not 0 < test_size < 1:
        raise ValueError("test_size must be between 0 and 1")
    if n_episodes < 10:
        raise ValueError("n_episodes must be at least 10 for an 80/20 episode split")

    dataset = make_dataset(n_episodes=n_episodes, seed=seed)
    featured = build_features(dataset)

    episode_info = (
        featured[["episode_id", "scenario"]]
        .drop_duplicates("episode_id")
        .sort_values("episode_id")
    )
    train_ids, test_ids = train_test_split(
        episode_info["episode_id"].to_numpy(),
        test_size=test_size,
        random_state=seed,
        stratify=episode_info["scenario"].to_numpy(),
    )

    train_rows = featured[featured["episode_id"].isin(train_ids)].copy()
    test_rows = featured[featured["episode_id"].isin(test_ids)].copy()

    imputer = SimpleImputer(strategy="median")
    x_train = imputer.fit_transform(train_rows[FEATURES])
    x_test = imputer.transform(test_rows[FEATURES])
    y_train = train_rows["label"].astype(int).to_numpy()
    y_test = test_rows["label"].astype(int).to_numpy()

    # This is the same model family used by the supplied single-file prototype.
    model = GradientBoostingClassifier(
        n_estimators=150,
        max_depth=3,
        random_state=seed,
    )
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    report = classification_report(
        y_test,
        predictions,
        labels=[0, 1, 2, 3],
        target_names=LEVELS,
        output_dict=True,
        zero_division=0,
    )

    normal_rows = train_rows.loc[train_rows["scenario"] == "normal", FEATURES]
    if normal_rows.empty:
        raise ValueError("Training split contains no normal episodes")
    normal_values = imputer.transform(normal_rows)
    normal_mean = pd.Series(normal_values.mean(axis=0), index=FEATURES)
    normal_std = pd.Series(normal_values.std(axis=0), index=FEATURES).replace(0, 1e-9)

    train_episode_count = int(train_rows["episode_id"].nunique())
    test_episode_count = int(test_rows["episode_id"].nunique())
    bundle = {
        "bundle_version": 1,
        "model_name": "GradientBoostingClassifier",
        "model": model,
        "imputer": imputer,
        "feature_names": FEATURES.copy(),
        "normal_mean": normal_mean.to_dict(),
        "normal_std": normal_std.to_dict(),
        "risk_levels": LEVELS.copy(),
        "training_config": {
            "n_episodes": int(n_episodes),
            "seed": int(seed),
            "test_size": float(test_size),
            "n_train_episodes": train_episode_count,
            "n_test_episodes": test_episode_count,
        },
        "held_out_classification_report": report,
    }

    destination = Path(model_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, destination)

    print(f"Model: GradientBoostingClassifier")
    print(
        f"Episode split: {train_episode_count} train / {test_episode_count} test "
        f"(test size {test_size:.0%})"
    )
    print("Held-out precision / recall by risk level:")
    for level in LEVELS:
        values = report[level]
        print(
            f"  {level:<8} precision={values['precision']:.3f} "
            f"recall={values['recall']:.3f}"
        )
    print(f"  Macro    precision={report['macro avg']['precision']:.3f} "
          f"recall={report['macro avg']['recall']:.3f}")
    print(f"Saved model bundle: {destination}")

    return bundle


if __name__ == "__main__":
    train_and_evaluate()
