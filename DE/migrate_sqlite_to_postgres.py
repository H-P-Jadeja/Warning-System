"""Copy legacy alerts in a transaction from a read-only SQLite connection."""

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from app.db import DB_PATH
from app.postgres import connect


def migrate(path):
    uri = Path(path).resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as source, connect() as target:
        records = source.execute("""
            SELECT id, created_at, lake_id, sensor_time, level, score, message, status
            FROM alerts ORDER BY id
        """)
        inserted = skipped = 0
        for row in records:
            key = hashlib.sha256(json.dumps(row).encode()).hexdigest()
            marker = target.execute("""
                INSERT INTO sqlite_alert_imports (source_key) VALUES (%s)
                ON CONFLICT DO NOTHING RETURNING source_key
            """, (key,)).fetchone()
            if marker is None:
                skipped += 1
                continue
            try:
                target.execute("""
                    INSERT INTO alerts (created_at, lake_id, sensor_time, level_id, risk_score, message, status)
                    VALUES (%s, %s, %s, (SELECT level_id FROM risk_levels WHERE level_name = %s), %s, %s, %s)
                """, row[1:])
            except Exception as exc:
                raise ValueError(f"Cannot import legacy alert ID {row[0]}; migration rolled back") from exc
            inserted += 1
    return inserted, skipped


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=DB_PATH)
    inserted, skipped = migrate(parser.parse_args().path)
    print(f"Imported {inserted} legacy alerts. Skipped {skipped} previously imported alerts.")
