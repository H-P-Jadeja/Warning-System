# app/db.py - stores every alert raised
import os, sqlite3
from datetime import datetime
import pandas as pd

from app import postgres

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alerts.db")


def _conn():
    con = sqlite3.connect(DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT, lake_id TEXT, sensor_time TEXT,
        level TEXT, score REAL, message TEXT, status TEXT)""")
    return con


def log_alert(lake_id, sensor_time, level, score, message, status, *, episode=None):
    try:
        with postgres.ready_connection() as con:
            postgres.log_alert(con, lake_id, sensor_time, level, score, message, status, episode)
            return
    except postgres.Unavailable:
        pass
    con = _conn()
    con.execute("INSERT INTO alerts (created_at, lake_id, sensor_time, level, score, message, status) "
                "VALUES (?,?,?,?,?,?,?)",
                (datetime.now().isoformat(timespec="seconds"), lake_id, str(sensor_time),
                 level, float(score), message, status))
    con.commit(); con.close()


def get_alerts():
    try:
        with postgres.ready_connection() as con:
            return postgres.frame(con, "SELECT * FROM alert_history ORDER BY created_at DESC, id DESC")
    except postgres.Unavailable:
        pass
    con = _conn()
    df = pd.read_sql_query("SELECT * FROM alerts ORDER BY id DESC", con)
    con.close()
    return df


def clear_alerts():
    try:
        with postgres.ready_connection() as con:
            con.execute("DELETE FROM alerts")
            return
    except postgres.Unavailable:
        pass
    con = _conn()
    con.execute("DELETE FROM alerts")
    con.commit(); con.close()


persist_episode = postgres.persist_episode


def backend_name():
    return "PostgreSQL" if postgres.available() else "SQLite (legacy fallback)"


def get_alert_details(filters=None):
    filters = filters or {}
    with postgres.connect() as con:
        return postgres.frame(
            con,
            """
            SELECT h.*, a.prediction_id, a.ack_status, a.acknowledged_at
            FROM alert_history h JOIN alerts a ON a.alert_id = h.id
            WHERE (%(level)s::text IS NULL OR h.level = %(level)s)
              AND (%(start)s::date IS NULL OR h.created_at >= %(start)s::date)
              AND (%(end)s::date IS NULL OR h.created_at < %(end)s::date + 1)
            ORDER BY h.created_at DESC, h.id DESC
            """,
            {key: filters.get(key) for key in ("level", "start", "end")},
        )


def get_notifications(alert_id):
    with postgres.connect() as con:
        return postgres.frame(con, """
            SELECT r.name, n.channel, n.delivery_status, n.sent_at
            FROM alert_notifications n JOIN recipients r USING (recipient_id)
            WHERE n.alert_id = %s ORDER BY r.name, n.channel
        """, (alert_id,))


def acknowledge_alert(alert_id):
    with postgres.connect() as con:
        return con.execute("""
            UPDATE alerts SET ack_status = 'ACKNOWLEDGED', acknowledged_at = now()
            WHERE alert_id = %s AND ack_status = 'NEW'
        """, (alert_id,)).rowcount == 1


def get_recipients():
    with postgres.connect() as con:
        return postgres.frame(con, "SELECT recipient_id, name, role, telegram_chat_id, settlement_id, "
                                    "is_active FROM recipients ORDER BY recipient_id")


def get_settlements():
    with postgres.connect() as con:
        return postgres.frame(con, "SELECT settlement_id, name FROM settlements ORDER BY name")


def add_recipient(name, role, telegram_chat_id=None, settlement_id=None, is_active=True):
    with postgres.connect() as con:
        return con.execute("""
            INSERT INTO recipients (name, role, telegram_chat_id, settlement_id, is_active)
            VALUES (%s, %s, %s, %s, %s) RETURNING recipient_id
        """, (name, role, telegram_chat_id, settlement_id, is_active)).fetchone()["recipient_id"]


def update_recipient(recipient_id, name, role, telegram_chat_id=None, settlement_id=None, is_active=True):
    with postgres.connect() as con:
        return con.execute("""
            UPDATE recipients SET name = %s, role = %s, telegram_chat_id = %s, settlement_id = %s,
                                  is_active = %s WHERE recipient_id = %s
        """, (name, role, telegram_chat_id, settlement_id, is_active, recipient_id)).rowcount == 1


def delete_recipient(recipient_id):
    with postgres.connect() as con:
        return con.execute("DELETE FROM recipients WHERE recipient_id = %s", (recipient_id,)).rowcount == 1


def get_table_counts():
    from psycopg import sql

    with postgres.connect() as con:
        tables = con.execute("""
            SELECT tablename FROM pg_tables WHERE schemaname = current_schema() ORDER BY tablename
        """).fetchall()
        return {row["tablename"]: con.execute(
            sql.SQL("SELECT count(*) AS count FROM {}").format(sql.Identifier(row["tablename"]))
        ).fetchone()["count"] for row in tables}


def get_lake_area(lake_id="SL001"):
    with postgres.connect() as con:
        return postgres.frame(con, """
            SELECT observed_on AS date, area_km2::double precision AS area_km2, source, method, note
            FROM lake_area_observations WHERE lake_id = %s ORDER BY observed_on
        """, (lake_id,))


def run_named_query(name):
    from DE.queries import QUERIES

    query = QUERIES[name]
    with postgres.connect() as con:
        con.execute("SET TRANSACTION READ ONLY")
        return postgres.frame(con, query.preview or query.sql, query.params)
