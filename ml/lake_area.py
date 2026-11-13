"""Load approximate published South Lhonak Lake area observations.

The values combine NRSC radar-based observations and a secondary Planet Labs
report. They are approximate published values, not measurements computed from
Sentinel-2 NDWI by this project.
"""

from pathlib import Path

import pandas as pd


_CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "lake_area_south_lhonak.csv"


def get_lake_area_series():
    """Return published lake-area observations in dashboard-compatible form."""
    if not _CSV_PATH.is_file():
        raise FileNotFoundError(f"South Lhonak lake-area CSV not found: {_CSV_PATH}")

    series = pd.read_csv(_CSV_PATH)
    # The published dates use both date-only and date-time forms.
    series["date"] = pd.to_datetime(series["date"], format="mixed")
    series["area_km2"] = series["area_km2"].astype(float)
    series["source"] = series["source"].astype(str)
    columns = ["date", "area_km2", "source"]
    if "method" in series.columns:
        columns.append("method")
    if "note" in series.columns:
        columns.append("note")

    return series.loc[:, columns].sort_values("date").reset_index(drop=True)
