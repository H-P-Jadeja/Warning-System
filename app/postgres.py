"""PostgreSQL storage and connection handling for the dashboard."""

import os

import pandas as pd

MODEL_ID = "capstone-v1"
SENSORS = (
    "water_level_m", "seepage_rate", "dam_tilt_deg", "inflow_rate",
    "seismic_activity", "rainfall_mm", "water_temp_c", "lake_area_km2",
)


class Unavailable(RuntimeError):
    """The PostgreSQL backend could not be opened."""


def connect():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise Unavailable("PostgreSQL not configured")
    try:
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(url, connect_timeout=5, row_factory=dict_row)
    except ImportError as exc:
        raise Unavailable("PostgreSQL driver unavailable") from exc
    except (psycopg.OperationalError, psycopg.ProgrammingError) as exc:
        raise Unavailable("PostgreSQL connection unavailable") from exc


def ready_connection():
    con = connect()
    try:
        if con.execute("SELECT to_regclass('alert_history') AS history").fetchone()["history"] is None:
            raise Unavailable("PostgreSQL schema not configured")
    except BaseException:
        con.close()
        raise
    return con


def available():
    try:
        with ready_connection():
            return True
    except Unavailable:
        return False


def frame(con, sql, params=None):
    cursor = con.execute(sql, params)
    return pd.DataFrame(cursor.fetchall(), columns=[column.name for column in cursor.description])


def log_alert(con, lake_id, sensor_time, level, score, message, status, episode):
    scenario, seed, hour = episode if episode is not None else (None, None, None)
    alert = con.execute(
        """
        INSERT INTO alerts (prediction_id, lake_id, level_id, sensor_time, risk_score, message, status)
        VALUES ((SELECT p.prediction_id FROM predictions p
                 JOIN sensor_readings r USING (reading_id)
                 JOIN simulation_episodes e USING (episode_id)
                 WHERE e.scenario = %s AND e.seed = %s AND r.hour = %s AND r.lake_id = %s),
                %s, (SELECT level_id FROM risk_levels WHERE level_name = %s), %s, %s, %s, %s)
        RETURNING alert_id
        """,
        (scenario, seed, hour, lake_id, lake_id, level, str(sensor_time), float(score), message, status),
    ).fetchone()
    con.execute(
        """
        INSERT INTO alert_notifications (alert_id, recipient_id, channel, delivery_status, sent_at)
        SELECT %s, recipient_id, 'telegram', %s, CASE WHEN %s THEN now() END
        FROM recipients WHERE is_active
        """,
        (alert["alert_id"], status, status == "Sent to Telegram"),
    )


def persist_episode(scenario, seed, readings, results):
    if len(readings) != len(results) or readings.empty:
        raise ValueError("Expected a nonempty episode with one prediction per reading")
    with connect() as con, con.cursor() as cursor:
        episode = cursor.execute(
            """
            INSERT INTO simulation_episodes (scenario, seed, hours)
            VALUES (%s, %s, %s) ON CONFLICT (scenario, seed) DO NOTHING RETURNING episode_id
            """, (scenario, seed, len(readings)),
        ).fetchone()
        if episode is None:
            return
        episode_id = episode["episode_id"]
        records = readings.to_dict("records")
        cursor.executemany(
            """
            INSERT INTO sensor_readings
            (lake_id, episode_id, hour, recorded_at, water_level_m, seepage_rate, dam_tilt_deg,
             inflow_rate, seismic_activity, rainfall_mm, water_temp_c, lake_area_km2)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [(row["lake_id"], episode_id, row["hour"], row["timestamp"],
              *(None if pd.isna(row[key]) else float(row[key]) for key in SENSORS))
             for row in records],
        )
        cursor.executemany(
            """
            INSERT INTO predictions (reading_id, model_id, level_id, risk_score)
            SELECT reading_id, %s, %s, %s FROM sensor_readings WHERE episode_id = %s AND hour = %s
            """,
            [(MODEL_ID, result["level_index"], result["risk_score"], episode_id, row["hour"])
             for row, result in zip(records, results)],
        )
        cursor.executemany(
            """
            INSERT INTO prediction_factors (prediction_id, rank, feature_name)
            SELECT p.prediction_id, %s, %s FROM predictions p JOIN sensor_readings r USING (reading_id)
            WHERE r.episode_id = %s AND r.hour = %s
            """,
            [(rank, feature, episode_id, row["hour"])
             for row, result in zip(records, results)
             for rank, feature in enumerate(result["top_factors"], 1)],
        )
