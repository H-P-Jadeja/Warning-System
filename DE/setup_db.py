"""Create and seed the PostgreSQL schema. Run with python -m DE.setup_db."""

import csv
import json
from pathlib import Path

from app.alerts import LEVEL_INFO
from app.postgres import MODEL_ID, connect
from ml.predict import LEAD_TIME_HOURS

ROOT = Path(__file__).resolve().parents[1]


def setup():
    with connect() as con, con.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(610296)")
        cursor.execute((ROOT / "DE/sql/01_schema.sql").read_text())
        cursor.execute("""
            INSERT INTO lakes (lake_id, name, latitude, longitude, state)
            VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING
        """, ("SL001", "South Lhonak Lake", 27.92, 88.18, "Sikkim"))
        cursor.execute("""
            INSERT INTO settlements (settlement_id, lake_id, name, latitude, longitude)
            VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING
        """, ("CHUNGTHANG", "SL001", "Chungthang (illustrative record)", 27.60, 88.64))
        cursor.executemany("""
            INSERT INTO risk_levels (level_id, level_name, colour, action, lead_time_hrs)
            VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING
        """, [(i, level, info["colour"], info["action"], LEAD_TIME_HOURS[level])
              for i, (level, info) in enumerate(LEVEL_INFO.items())])
        metrics = json.loads((ROOT / "ml/results/metrics.json").read_text())
        cursor.execute("""
            INSERT INTO ml_models (model_id, name, version, macro_f1, trained_on_note)
            VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING
        """, (MODEL_ID, metrics["model"], "v1", metrics["macro_avg"]["f1"], metrics["data_note"]))
        cursor.executemany("""
            INSERT INTO recipients (seed_key, name, role, telegram_chat_id, settlement_id, is_active)
            VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING
        """, [
            ("demo-control", "Illustrative control room", "Coordinator", "fake-control", None, True),
            ("demo-liaison", "Illustrative settlement liaison", "Liaison", "fake-liaison", "CHUNGTHANG", True),
        ])
        with (ROOT / "data/lake_area_south_lhonak.csv").open(newline="") as source:
            cursor.executemany("""
                INSERT INTO lake_area_observations (lake_id, observed_on, area_km2, source, method, note)
                VALUES ('SL001', %(date)s, %(area_km2)s, %(source)s, %(method)s, %(note)s)
                ON CONFLICT DO NOTHING
            """, list(csv.DictReader(source)))


if __name__ == "__main__":
    setup()
    print("PostgreSQL schema and seed ready.")
