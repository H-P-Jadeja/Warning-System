"""Study persistence smoothing for the dashboard alert rule on synthetic data.

Run from the repository root with ``python -m ml.alert_rule_study``. This is
an offline analysis; it does not send alerts or change the trained model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ml.evaluate import RESULTS_DIR, load_held_out_predictions
from ml.simulator import GLOF_TYPES


PERSISTENCE_VALUES = (1, 2, 3, 4)
REPEAT_HOURS = 12
DATA_NOTE = (
    "All results are on synthetic data and do not represent real-world model performance."
)
TRADEOFF_NOTE = (
    "The recommended persistence k is a trade-off between suppressing brief false alerts "
    "and preserving timely warnings; it is not a validated operational setting."
)


def _replay_episode(predictions: np.ndarray, persistence: int) -> list[tuple[int, int]]:
    """Return alert (hour, level) pairs after persistence and repeat logic."""
    # At hour h use the minimum predicted risk level over the last k rows,
    # including h. For k=1 this is the model's unfiltered current level.
    levels = (
        pd.Series(predictions, dtype="int64")
        .rolling(window=persistence, min_periods=1)
        .min()
        .astype(int)
        .to_numpy()
    )

    alerts: list[tuple[int, int]] = []
    last_alerted_level = 0
    last_alert_hour: int | None = None
    for hour, level in enumerate(levels):
        hours_since_last = (
            hour - last_alert_hour if last_alert_hour is not None else REPEAT_HOURS
        )

        # Mirrors app/alerts.should_alert: alert on an upward level change,
        # or repeat at HIGH/CRITICAL after 12 hours since the prior alert.
        should_alert = level >= 1 and (
            level > last_alerted_level
            or (level >= 2 and hours_since_last >= REPEAT_HOURS)
        )
        if should_alert:
            alerts.append((hour, int(level)))
            last_alerted_level = int(level)
            last_alert_hour = hour
        elif level < last_alerted_level:
            # The dashboard lowers its remembered level when risk falls.
            last_alerted_level = int(level)

    return alerts


def _lead_summary(lead_times: list[int]) -> dict[str, Any]:
    return {
        "episodes_with_alert": len(lead_times),
        "median_lead_time_hours": float(np.median(lead_times)) if lead_times else None,
        "mean_lead_time_hours": float(np.mean(lead_times)) if lead_times else None,
        "minimum_lead_time_hours": int(min(lead_times)) if lead_times else None,
    }


def _glof_metrics(
    glof_episodes: list[tuple[int, str, int, list[tuple[int, int]]]],
) -> dict[str, Any]:
    total = len(glof_episodes)
    all_leads: list[int] = []
    high_leads: list[int] = []
    for event_hour, _event_type, _episode_id, alerts in glof_episodes:
        before_event = [(hour, level) for hour, level in alerts if hour < event_hour]
        first_any = next((hour for hour, _level in before_event), None)
        first_high = next((hour for hour, level in before_event if level >= 2), None)
        if first_any is not None:
            all_leads.append(event_hour - first_any)
        if first_high is not None:
            high_leads.append(event_hour - first_high)

    return {
        "episodes": total,
        "episodes_with_alert_before_event": len(all_leads),
        "fraction_with_alert_before_event": len(all_leads) / total if total else 0.0,
        "first_alert_lead_time": _lead_summary(all_leads),
        "episodes_with_high_alert_before_event": len(high_leads),
        "fraction_with_high_alert_before_event": len(high_leads) / total if total else 0.0,
        "first_high_alert_lead_time": _lead_summary(high_leads),
    }


def _csv_row(
    persistence: int,
    scope: str,
    normal_metrics: dict[str, Any],
    glof_metrics: dict[str, Any],
) -> dict[str, Any]:
    any_leads = glof_metrics["first_alert_lead_time"]
    high_leads = glof_metrics["first_high_alert_lead_time"]
    return {
        "persistence_k": persistence,
        "scope": scope,
        "glof_episodes": glof_metrics["episodes"],
        "episodes_with_alert_before_event": glof_metrics["episodes_with_alert_before_event"],
        "fraction_with_alert_before_event": glof_metrics["fraction_with_alert_before_event"],
        "first_alert_median_lead_hours": any_leads["median_lead_time_hours"],
        "first_alert_mean_lead_hours": any_leads["mean_lead_time_hours"],
        "first_alert_minimum_lead_hours": any_leads["minimum_lead_time_hours"],
        "episodes_with_high_alert_before_event": glof_metrics["episodes_with_high_alert_before_event"],
        "fraction_with_high_alert_before_event": glof_metrics[
            "fraction_with_high_alert_before_event"
        ],
        "first_high_alert_median_lead_hours": high_leads["median_lead_time_hours"],
        "first_high_alert_mean_lead_hours": high_leads["mean_lead_time_hours"],
        "first_high_alert_minimum_lead_hours": high_leads["minimum_lead_time_hours"],
        "normal_episodes": normal_metrics["episodes"],
        "normal_hours": normal_metrics["hours"],
        "false_alerts_total": normal_metrics["false_alerts_total"],
        "false_alerts_per_episode": normal_metrics["false_alerts_per_episode"],
        "false_alerts_per_1000_hours": normal_metrics["false_alerts_per_1000_hours"],
    }


def main() -> int:
    _bundle, _train_rows, test_rows, predictions, _report, _feature_names = (
        load_held_out_predictions()
    )
    scored = test_rows[["episode_id", "scenario", "event_type", "hour"]].copy()
    scored["prediction"] = predictions

    if scored["episode_id"].nunique() != 60:
        raise ValueError("Expected the recreated held-out split to contain 60 episodes.")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {
        "data_note": DATA_NOTE,
        "recommended_k_note": TRADEOFF_NOTE,
        "alert_rule": {
            "description": (
                "Alert when the risk level rises above the last alerted level (level >= 1), "
                "or when level >= HIGH and at least 12 hours have elapsed since the last alert. "
                "The remembered level steps down when the risk level falls."
            ),
            "persistence": "At hour h, use the minimum predicted level over the last k rows.",
            "repeat_hours": REPEAT_HOURS,
        },
        "held_out_episodes": int(scored["episode_id"].nunique()),
        "results_by_persistence": {},
    }
    csv_rows: list[dict[str, Any]] = []

    for persistence in PERSISTENCE_VALUES:
        episode_results: list[tuple[int, str | None, int, str, list[tuple[int, int]]]] = []
        for episode_id, episode in scored.groupby("episode_id", sort=True):
            episode = episode.sort_values("hour", kind="stable")
            scenario = str(episode["scenario"].iloc[0])
            event_type_value = episode["event_type"].iloc[0]
            event_type = None if pd.isna(event_type_value) else str(event_type_value)
            levels = episode["prediction"].astype(int).to_numpy()
            alerts = _replay_episode(levels, persistence)
            event_hour = int(episode["hour"].max()) if scenario == "glof" else -1
            episode_results.append((int(episode_id), event_type, event_hour, scenario, alerts))

        normal_episodes = [item for item in episode_results if item[3] == "normal"]
        normal_alert_count = sum(len(item[4]) for item in normal_episodes)
        normal_hours = sum(
            int(scored.loc[scored["episode_id"] == item[0], "hour"].count())
            for item in normal_episodes
        )
        normal_metrics = {
            "episodes": len(normal_episodes),
            "hours": normal_hours,
            "false_alerts_total": normal_alert_count,
            "false_alerts_per_episode": (
                normal_alert_count / len(normal_episodes) if normal_episodes else 0.0
            ),
            "false_alerts_per_1000_hours": (
                normal_alert_count * 1000 / normal_hours if normal_hours else 0.0
            ),
        }

        glof_tuples = [
            (event_hour, event_type or "unknown", episode_id, alerts)
            for episode_id, event_type, event_hour, scenario, alerts in episode_results
            if scenario == "glof"
        ]
        overall = _glof_metrics(glof_tuples)
        by_event_type = {
            event_type: _glof_metrics([item for item in glof_tuples if item[1] == event_type])
            for event_type in GLOF_TYPES
        }
        results["results_by_persistence"][str(persistence)] = {
            "normal_false_alerts": normal_metrics,
            "glof_overall": overall,
            "glof_by_event_type": by_event_type,
        }
        csv_rows.append(_csv_row(persistence, "overall", normal_metrics, overall))
        for event_type, metrics in by_event_type.items():
            csv_rows.append(_csv_row(persistence, event_type, normal_metrics, metrics))

    csv_path = RESULTS_DIR / "alert_persistence.csv"
    json_path = RESULTS_DIR / "alert_persistence.json"
    pd.DataFrame(csv_rows).to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")

    summary_rows = []
    for persistence in PERSISTENCE_VALUES:
        item = results["results_by_persistence"][str(persistence)]
        overall = item["glof_overall"]
        first = overall["first_alert_lead_time"]
        high = overall["first_high_alert_lead_time"]
        summary_rows.append({
            "k": persistence,
            "normal false alerts": item["normal_false_alerts"]["false_alerts_total"],
            "false alerts/episode": item["normal_false_alerts"]["false_alerts_per_episode"],
            "false alerts/1000h": item["normal_false_alerts"]["false_alerts_per_1000_hours"],
            "GLOF warned": f"{overall['episodes_with_alert_before_event']}/{overall['episodes']}",
            "first lead median/mean/min": (
                f"{first['median_lead_time_hours']}/"
                f"{first['mean_lead_time_hours']}/"
                f"{first['minimum_lead_time_hours']}"
            ),
            "HIGH warned": (
                f"{overall['episodes_with_high_alert_before_event']}/{overall['episodes']}"
            ),
            "HIGH lead median/mean/min": (
                f"{high['median_lead_time_hours']}/"
                f"{high['mean_lead_time_hours']}/"
                f"{high['minimum_lead_time_hours']}"
            ),
        })

    print(DATA_NOTE)
    print(TRADEOFF_NOTE)
    print(pd.DataFrame(summary_rows).to_string(index=False))
    print(f"Saved: {csv_path}")
    print(f"Saved: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
