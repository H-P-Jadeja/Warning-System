"""Plain-script contract checks for ``ml.predict.predict_risk``.

Run from the repository root with::

    python -m ml.check_contract
    python -m ml.check_contract --stub

This script does not train or modify the model. It exits with status 1 if any
contract check fails.
"""

from __future__ import annotations

import math
import re
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from ml.simulator import simulate_episode


LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
EXPECTED_KEYS = {
    "risk_score",
    "risk_level",
    "level_index",
    "top_factors",
    "estimated_lead_time_hrs",
}
READING_FIELDS = [
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
]
FACTOR_NAMES = {
    "water_level_m",
    "seepage_rate",
    "dam_tilt_deg",
    "inflow_rate",
    "seismic_activity",
    "rainfall_mm",
    "water_temp_c",
    "lake_area_km2",
    "water_level_d6",
    "seepage_d6",
    "tilt_d6",
}
LEAD_TIMES = {"LOW": None, "MEDIUM": 36, "HIGH": 18, "CRITICAL": 6}


def _reading_from_row(row: pd.Series) -> dict[str, Any]:
    """Keep only contract reading fields from a simulator row."""
    return {field: row[field] for field in READING_FIELDS}


def _assert_result(result: Any) -> None:
    """Assert the returned keys, types, ranges, and level mappings."""
    assert isinstance(result, dict), "result must be a dict"
    assert set(result) == EXPECTED_KEYS, (
        f"return keys must be {sorted(EXPECTED_KEYS)}, got {sorted(result)}"
    )

    score = result["risk_score"]
    assert type(score) is float and math.isfinite(score), "risk_score must be a finite float"
    assert 0.0 <= score <= 100.0, "risk_score must be in the 0-100 range"

    level = result["risk_level"]
    assert isinstance(level, str) and level in LEVELS, "risk_level is invalid"
    index = result["level_index"]
    assert type(index) is int and 0 <= index <= 3, "level_index must be an int from 0 to 3"
    assert index == LEVELS.index(level), "level_index does not match risk_level"

    factors = result["top_factors"]
    assert isinstance(factors, list) and len(factors) == 3, "top_factors must be a list of 3 names"
    assert all(isinstance(name, str) for name in factors), "top_factors entries must be strings"
    assert all(name in FACTOR_NAMES for name in factors), "top_factors contains an unknown feature"

    lead_time = result["estimated_lead_time_hrs"]
    assert lead_time == LEAD_TIMES[level], (
        f"estimated_lead_time_hrs for {level} must be {LEAD_TIMES[level]!r}"
    )
    assert lead_time is None or type(lead_time) is int, (
        "estimated_lead_time_hrs must be None or an int"
    )


def _history_for_rows(episode: pd.DataFrame, end_index: int, count: int = 12) -> list[dict[str, Any]]:
    start_index = max(0, end_index - count)
    return [
        _reading_from_row(row)
        for _, row in episode.iloc[start_index:end_index].iterrows()
    ]


def _expected_sklearn_version() -> str | None:
    requirements = Path(__file__).resolve().parents[1] / "requirements.txt"
    if not requirements.exists():
        return None
    match = re.search(r"^scikit-learn==([^\s]+)\s*$", requirements.read_text(), re.MULTILINE)
    return match.group(1) if match else None


def _print_sklearn_version() -> None:
    try:
        installed = version("scikit-learn")
    except PackageNotFoundError:
        print("WARNING: scikit-learn is not installed.")
        return
    print(f"scikit-learn installed version: {installed}")
    expected = _expected_sklearn_version()
    if expected and installed != expected:
        print(
            f"WARNING: installed scikit-learn {installed} differs from "
            f"requirements.txt pin {expected}."
        )


def _run_case(name: str, check: Callable[[], None]) -> bool:
    try:
        check()
    except Exception as exc:
        print(f"FAIL: {name} — {type(exc).__name__}: {exc}")
        return False
    print(f"PASS: {name}")
    return True


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Check the risk prediction interface")
    parser.add_argument(
        "--stub",
        action="store_true",
        help="run applicable contract cases against the threshold dashboard stub",
    )
    args = parser.parse_args(argv)

    if args.stub:
        from ml.predict_stub import predict_risk
    else:
        from ml.predict import predict_risk

    _print_sklearn_version()

    normal_episode = simulate_episode("normal", seed=3)
    base_reading = _reading_from_row(normal_episode.iloc[20])
    history_12 = [
        _reading_from_row(row)
        for _, row in normal_episode.iloc[8:20].iterrows()
    ]
    history_frame = pd.DataFrame(history_12)
    short_history = history_12[:5]

    def case_1() -> None:
        _assert_result(predict_risk(base_reading))

    def case_2() -> None:
        _assert_result(predict_risk(base_reading, history=history_12))

    def case_3() -> None:
        _assert_result(predict_risk(base_reading, history=history_frame))

    def case_4() -> None:
        _assert_result(predict_risk(base_reading, history=short_history))

    def case_5() -> None:
        reading = dict(base_reading)
        reading["rainfall_mm"] = None
        reading["water_temp_c"] = np.nan
        _assert_result(predict_risk(reading))

    def case_6() -> None:
        reading = dict(base_reading)
        del reading["lake_id"]
        try:
            predict_risk(reading)
        except ValueError:
            return
        raise AssertionError("missing lake_id did not raise ValueError")

    def case_7() -> None:
        reading = dict(base_reading)
        reading["water_level_m"] = "abc"
        try:
            predict_risk(reading)
        except ValueError:
            return
        raise AssertionError("non-numeric sensor value did not raise ValueError")

    def case_8_glof_monotonic() -> None:
        glof_episode = simulate_episode("glof", seed=11)
        early_indices = glof_episode.index[glof_episode["label"] == 0]
        middle_indices = glof_episode.index[glof_episode["label"] == 1]
        late_indices = glof_episode.index[glof_episode["label"] == 3]
        assert len(early_indices) and len(middle_indices) and len(late_indices), (
            "GLOF episode must contain label 0, label 1, and label 3 rows"
        )

        early_index = int(early_indices[0])
        middle_index = int(middle_indices[len(middle_indices) // 2])
        late_index = int(late_indices[-1])

        early_score = predict_risk(
            _reading_from_row(glof_episode.iloc[early_index]),
            history=_history_for_rows(glof_episode, early_index),
        )["risk_score"]
        middle_score = predict_risk(
            _reading_from_row(glof_episode.iloc[middle_index]),
            history=_history_for_rows(glof_episode, middle_index),
        )["risk_score"]
        late_score = predict_risk(
            _reading_from_row(glof_episode.iloc[late_index]),
            history=_history_for_rows(glof_episode, late_index),
        )["risk_score"]
        assert late_score > early_score, (
            f"late GLOF score ({late_score:.2f}) must exceed early score ({early_score:.2f}); "
            f"mid-warning score was {middle_score:.2f}"
        )

    def case_8_normal_low() -> None:
        normal_middle_index = len(normal_episode) // 2
        normal_result = predict_risk(
            _reading_from_row(normal_episode.iloc[normal_middle_index]),
            history=_history_for_rows(normal_episode, normal_middle_index),
        )
        assert normal_result["risk_level"] == "LOW", (
            f"normal middle-row risk level was {normal_result['risk_level']}"
        )

    def case_8() -> None:
        case_8_glof_monotonic()
        case_8_normal_low()

    def case_9() -> None:
        first = predict_risk(base_reading, history=history_12)
        second = predict_risk(base_reading, history=history_12)
        assert first == second, "identical calls returned different values"

    common_cases = [
        ("normal reading without history returns contract fields and types", case_1),
        ("12-row list history", case_2),
        ("pandas DataFrame history", case_3),
        ("history shorter than six rows", case_4),
        ("None and NaN sensor values", case_5),
        ("missing required field raises ValueError", case_6),
        ("non-numeric sensor value raises ValueError", case_7),
    ]
    if args.stub:
        print(
            "SKIP: GLOF monotonic episode check (threshold stub has no trained "
            "model; this model-behavior check is not applicable)."
        )
        cases = common_cases + [
            ("normal middle row stays LOW", case_8_normal_low),
            ("deterministic repeated prediction", case_9),
        ]
        skipped = 1
    else:
        cases = common_cases + [
            ("GLOF risk rises and normal middle row stays LOW", case_8),
            ("deterministic repeated prediction", case_9),
        ]
        skipped = 0

    passed = sum(_run_case(name, check) for name, check in cases)
    failed = len(cases) - passed
    if args.stub:
        print(f"Summary: {passed} passed, {failed} failed, {skipped} skipped")
    else:
        print(f"Summary: {passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
