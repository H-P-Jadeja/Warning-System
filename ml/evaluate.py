"""Evaluate the saved classifier; every metric here uses synthetic data only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)

from ml.train import (
    DEFAULT_EPISODES,
    DEFAULT_SEED,
    DEFAULT_TEST_SIZE,
    FEATURES,
    LEVELS,
    build_features,
    make_dataset,
    train_test_split,
)
from ml.simulator import GLOF_TYPES


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = PROJECT_ROOT / "ml" / "model.pkl"
RESULTS_DIR = PROJECT_ROOT / "ml" / "results"
CLASS_IDS = [0, 1, 2, 3]
SYNTHETIC_DATA_NOTE = (
    "All evaluation results are based on synthetic data and do not represent "
    "real-world model performance."
)


def _episode_split(dataset: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Recreate train.py's stratified episode-ID split using its imported settings."""
    episode_info = (
        dataset[["episode_id", "scenario"]]
        .drop_duplicates("episode_id")
        .sort_values("episode_id")
    )
    return train_test_split(
        episode_info["episode_id"].to_numpy(),
        test_size=DEFAULT_TEST_SIZE,
        random_state=DEFAULT_SEED,
        stratify=episode_info["scenario"].to_numpy(),
    )


def _compare_saved_metrics(current: dict[str, Any], saved: dict[str, Any]) -> None:
    """Stop before writing artifacts if the held-out report changed."""
    if not isinstance(saved, dict):
        raise SystemExit("STOP: model bundle has no held_out_classification_report.")
    comparisons: list[tuple[str, float, float]] = []
    for level in LEVELS:
        for metric in ("precision", "recall", "f1-score", "support"):
            comparisons.append((
                f"{level}.{metric}",
                float(current[level][metric]),
                float(saved[level][metric]),
            ))
    for metric in ("precision", "recall", "f1-score"):
        comparisons.append((
            f"macro avg.{metric}",
            float(current["macro avg"][metric]),
            float(saved["macro avg"][metric]),
        ))
    comparisons.append(("accuracy", float(current["accuracy"]), float(saved["accuracy"])))

    differences = [
        f"{name}: recreated={actual:.12g}, saved={expected:.12g}"
        for name, actual, expected in comparisons
        if not np.isclose(actual, expected, rtol=0.0, atol=1e-12)
    ]
    if differences:
        raise SystemExit(
            "STOP: held-out metrics differ from the saved model bundle; no result files written.\n"
            + "\n".join(differences)
        )


def _save_confusion_matrix(matrix: np.ndarray) -> None:
    fig, ax = plt.subplots(figsize=(7, 6))
    image = ax.imshow(matrix, cmap="Blues")
    fig.colorbar(image, ax=ax, label="Episode-row count")
    ax.set(
        xticks=CLASS_IDS,
        yticks=CLASS_IDS,
        xticklabels=LEVELS,
        yticklabels=LEVELS,
        xlabel="Predicted risk level",
        ylabel="True risk level",
        title="Held-out confusion matrix (synthetic episodes)",
    )
    threshold = matrix.max() / 2 if matrix.size else 0
    for row in range(matrix.shape[0]):
        for column in range(matrix.shape[1]):
            ax.text(
                column,
                row,
                f"{matrix[row, column]:,}",
                ha="center",
                va="center",
                color="white" if matrix[row, column] > threshold else "black",
            )
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "confusion_matrix.png", dpi=160)
    plt.close(fig)


def _save_feature_importance(model: Any, feature_names: list[str]) -> None:
    importances = np.asarray(model.feature_importances_, dtype=float)
    if len(importances) != len(feature_names):
        raise ValueError("model feature importance count does not match feature_names")
    order = np.argsort(importances)
    fig_height = max(5.5, 0.42 * len(feature_names))
    fig, ax = plt.subplots(figsize=(9, fig_height))
    ax.barh([feature_names[index] for index in order], importances[order], color="#4169a1")
    ax.set_xlabel("Model feature importance")
    ax.set_title("Gradient Boosting feature importance")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "feature_importance.png", dpi=160)
    plt.close(fig)


def _write_event_type_metrics(test_rows: pd.DataFrame, predictions: np.ndarray) -> None:
    scored = test_rows[["episode_id", "event_type", "label"]].copy()
    scored["prediction"] = predictions
    rows = []
    for event_type in GLOF_TYPES:
        group = scored.loc[scored["event_type"] == event_type]
        if group.empty:
            raise ValueError(f"no held-out GLOF episodes found for event_type={event_type!r}")
        precision, recall, f1, support = precision_recall_fscore_support(
            group["label"],
            group["prediction"],
            labels=CLASS_IDS,
            zero_division=0,
        )
        episode_count = int(group["episode_id"].nunique())
        for index, level in enumerate(LEVELS):
            rows.append({
                "event_type": event_type,
                "risk_level": level,
                "precision": float(precision[index]),
                "recall": float(recall[index]),
                "f1": float(f1[index]),
                "support": int(support[index]),
                "n_episodes": episode_count,
            })
    pd.DataFrame(rows).to_csv(RESULTS_DIR / "per_event_type_recall.csv", index=False)


def _write_warning_timing(test_rows: pd.DataFrame, predictions: np.ndarray) -> tuple[list[int], int]:
    scored = test_rows[["episode_id", "scenario", "event_type", "hour", "label"]].copy()
    scored["prediction"] = predictions
    timing_rows = []
    delays: list[int] = []
    never_warned = 0

    glof_rows = scored.loc[scored["scenario"] == "glof"]
    for episode_id, episode in glof_rows.groupby("episode_id", sort=True):
        episode = episode.sort_values("hour")
        true_warnings = episode.loc[episode["label"] >= 1, "hour"]
        predicted_warnings = episode.loc[episode["prediction"] >= 1, "hour"]
        if true_warnings.empty:
            raise ValueError(f"GLOF episode {episode_id} has no true warning label")
        first_true = int(true_warnings.iloc[0])
        if predicted_warnings.empty:
            first_predicted = None
            delay = None
            never_warned += 1
        else:
            first_predicted = int(predicted_warnings.iloc[0])
            delay = first_predicted - first_true
            delays.append(delay)

        timing_rows.append({
            "episode_id": int(episode_id),
            "event_type": str(episode["event_type"].iloc[0]),
            "episode_length_hours": int(len(episode)),
            "first_true_warning_hour": first_true,
            "first_model_warning_hour": first_predicted,
            "warning_delay_hours": delay,
        })

    pd.DataFrame(timing_rows).to_csv(RESULTS_DIR / "warning_timing.csv", index=False)
    return delays, never_warned


def main() -> int:
    bundle = joblib.load(MODEL_PATH)
    training_config = bundle["training_config"]
    if (
        int(training_config["n_episodes"]) != DEFAULT_EPISODES
        or int(training_config["seed"]) != DEFAULT_SEED
        or not np.isclose(float(training_config["test_size"]), DEFAULT_TEST_SIZE)
    ):
        raise SystemExit(
            "STOP: saved model training settings do not match ml/train.py defaults; "
            "cannot recreate the same held-out set."
        )

    dataset = make_dataset(n_episodes=DEFAULT_EPISODES, seed=DEFAULT_SEED)
    featured = build_features(dataset)
    train_ids, test_ids = _episode_split(featured)
    train_rows = featured.loc[featured["episode_id"].isin(train_ids)].copy()
    test_rows = featured.loc[featured["episode_id"].isin(test_ids)].copy()

    feature_names = list(bundle["feature_names"])
    if feature_names != list(FEATURES):
        raise SystemExit("STOP: saved model feature order differs from ml/train.py.FEATURES.")
    x_test = bundle["imputer"].transform(test_rows[feature_names])
    y_true = test_rows["label"].astype(int).to_numpy()
    y_pred = np.asarray(bundle["model"].predict(x_test), dtype=int)
    report = classification_report(
        y_true,
        y_pred,
        labels=CLASS_IDS,
        target_names=LEVELS,
        output_dict=True,
        zero_division=0,
    )
    _compare_saved_metrics(report, bundle.get("held_out_classification_report"))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    confusion = confusion_matrix(y_true, y_pred, labels=CLASS_IDS)
    metrics = {
        "data_note": SYNTHETIC_DATA_NOTE,
        "model": bundle.get("model_name", "unknown"),
        "split_sizes": {
            "train_episodes": int(train_rows["episode_id"].nunique()),
            "test_episodes": int(test_rows["episode_id"].nunique()),
            "train_rows": int(len(train_rows)),
            "test_rows": int(len(test_rows)),
        },
        "per_class": {
            level: {
                "precision": float(report[level]["precision"]),
                "recall": float(report[level]["recall"]),
                "f1": float(report[level]["f1-score"]),
                "support": int(report[level]["support"]),
            }
            for level in LEVELS
        },
        "macro_avg": {
            "precision": float(report["macro avg"]["precision"]),
            "recall": float(report["macro avg"]["recall"]),
            "f1": float(report["macro avg"]["f1-score"]),
        },
        "accuracy": float(report["accuracy"]),
    }

    (RESULTS_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    _save_confusion_matrix(confusion)
    _save_feature_importance(bundle["model"], feature_names)
    _write_event_type_metrics(test_rows, y_pred)
    delays, never_warned = _write_warning_timing(test_rows, y_pred)

    normal = test_rows["scenario"] == "normal"
    normal_predictions = y_pred[normal.to_numpy()]
    above_low = int(np.count_nonzero(normal_predictions > 0))
    false_alarms = {
        "data_note": SYNTHETIC_DATA_NOTE,
        "normal_episodes": int(test_rows.loc[normal, "episode_id"].nunique()),
        "normal_rows": int(normal.sum()),
        "rows_predicted_above_low": above_low,
        "fraction_of_normal_rows_predicted_above_low": (
            float(above_low / int(normal.sum())) if int(normal.sum()) else 0.0
        ),
    }
    (RESULTS_DIR / "false_alarms.json").write_text(
        json.dumps(false_alarms, indent=2) + "\n"
    )

    warned_episode_count = int(test_rows.loc[test_rows["scenario"] == "glof", "episode_id"].nunique())
    never_fraction = never_warned / warned_episode_count if warned_episode_count else 0.0
    mean_delay = float(np.mean(delays)) if delays else None
    worst_delay = int(max(delays)) if delays else None
    print(SYNTHETIC_DATA_NOTE)
    print(
        f"Held-out split: {metrics['split_sizes']['train_episodes']} train / "
        f"{metrics['split_sizes']['test_episodes']} test episodes; "
        f"{metrics['split_sizes']['test_rows']} test rows."
    )
    print(
        "GLOF warning delay among warned episodes: "
        f"mean={mean_delay if mean_delay is not None else 'n/a'} hours, "
        f"worst-case={worst_delay if worst_delay is not None else 'n/a'} hours."
    )
    print(
        f"GLOF episodes never warned: {never_warned}/{warned_episode_count} "
        f"({never_fraction:.1%})."
    )
    print(
        f"Normal rows predicted above LOW: {above_low}/{int(normal.sum())} "
        f"({false_alarms['fraction_of_normal_rows_predicted_above_low']:.1%})."
    )
    print("Saved evaluation files:")
    for filename in (
        "metrics.json",
        "confusion_matrix.png",
        "feature_importance.png",
        "per_event_type_recall.csv",
        "warning_timing.csv",
        "false_alarms.json",
    ):
        print(f"  {RESULTS_DIR / filename}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
