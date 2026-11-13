"""Check pure alert persistence logic without Streamlit or database access.

Run from the repository root with ``python -m app.check_alert_logic``.
"""

from app.alerts import PERSISTENCE_HOURS, effective_level, should_alert


def _replay(levels, k=PERSISTENCE_HOURS):
    """Replay dashboard level handling using only the pure alert helpers."""
    alert_hours = []
    last_alerted_level = 0
    last_alert_hour = -999
    for hour in range(len(levels)):
        effective = effective_level(levels[: hour + 1], k=k)
        if should_alert(last_alerted_level, effective, hour - last_alert_hour):
            alert_hours.append((hour, effective))
            last_alerted_level = effective
            last_alert_hour = hour
        elif effective < last_alerted_level:
            last_alerted_level = effective
    return alert_hours


def main():
    cases = [
        (
            "single-hour MEDIUM blip raises no alert",
            _replay([0, 1, 0]) == [],
        ),
        (
            "two consecutive MEDIUM hours raise one alert",
            _replay([0, 1, 1, 1]) == [(2, 1)],
        ),
        (
            "sustained HIGH repeats only after 12 hours",
            _replay([2] * 25) == [(0, 2), (12, 2), (24, 2)],
        ),
        (
            "remembered level steps down after a drop",
            _replay([0, 2, 2, 0, 0, 1, 1]) == [(2, 2), (6, 1)],
        ),
        (
            "effective_level handles short and empty lists",
            effective_level([2]) == 2
            and effective_level([]) == 0
            and effective_level([0, 2, 2]) == 2,
        ),
    ]

    failures = 0
    for description, passed in cases:
        print(f"{'PASS' if passed else 'FAIL'}: {description}")
        failures += not passed
    print(f"Summary: {len(cases) - failures}/{len(cases)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
