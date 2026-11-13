# app/db.py - stores every alert raised
import os, sqlite3
from datetime import datetime
import pandas as pd

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alerts.db")


def _conn():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT, lake_id TEXT, sensor_time TEXT,
        level TEXT, score REAL, message TEXT, status TEXT)""")
    return con


def log_alert(lake_id, sensor_time, level, score, message, status):
    con = _conn()
    con.execute("INSERT INTO alerts (created_at, lake_id, sensor_time, level, score, message, status) "
                "VALUES (?,?,?,?,?,?,?)",
                (datetime.now().isoformat(timespec="seconds"), lake_id, str(sensor_time),
                 level, float(score), message, status))
    con.commit(); con.close()


def get_alerts():
    con = _conn()
    df = pd.read_sql_query("SELECT * FROM alerts ORDER BY id DESC", con)
    con.close()
    return df


def clear_alerts():
    con = _conn()
    con.execute("DELETE FROM alerts")
    con.commit(); con.close()