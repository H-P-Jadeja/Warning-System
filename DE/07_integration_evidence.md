# Application integration evidence

The dashboard calls [the app database API](../app/db.py). Psycopg 3 opens PostgreSQL connections using `DATABASE_URL` and binds values as SQL parameters. Connections close after each operation. The alert API uses the compatibility view for reads and uses legacy SQLite when the PostgreSQL connection or schema is unavailable.

- **Live Monitor** calls `persist_episode` after cached inference to insert the episode, readings, predictions and ranked factors. Triggered alerts use the unchanged Telegram sender and log the alert plus active-recipient notification records.
- **Lake Growth** selects published areas in chronological order and uses the CSV when the PostgreSQL view of these data is unavailable.
- **Alerts Log** selects recent records, optionally filters by level and date, and joins recipients for notification details. **Send test alert** inserts a manual alert. **Acknowledge** updates its status and timestamp. **Clear log** deletes alerts and cascades to notifications.
- **Recipients** selects, inserts, updates and deletes recipient rows.
- **Query Lab** uses a read-only transaction for allowlisted queries. **Database** selects counts and shows the relationship summary.

## CRUD demonstration

`python -m DE.demo_integration` uses the same recipient database functions as the dashboard. It inserts a disposable inactive recipient, reads it, changes its role and verifies deletion. Captured on an isolated PostgreSQL database with Telegram disabled.

```text
Backend: PostgreSQL
After INSERT and SELECT:
 recipient_id                   name     role telegram_chat_id settlement_id  is_active
            5 Illustrative CRUD demo Observer             None          None      False
After UPDATE and SELECT:
 recipient_id                   name        role telegram_chat_id settlement_id  is_active
            5 Illustrative CRUD demo Coordinator             None          None      False
After DELETE and SELECT, matching rows: 0
```

UI evidence for these operations is shown in the project demo video: *(link will be added)*.

## Verification

- Before changes, the alert check passed 5 cases, the real model contract passed 9 cases and `bash check_all.sh` passed.
- After changes, the same checks passed, including the stub contract with its existing skipped model-only case.
- Python 3.14 loaded Psycopg 3.3.3 with the binary implementation. A local PostgreSQL 17 server executed the schema, seed, query suite and app CRUD demo.
- The setup ran twice on the test database with equal row counts. Reopening GLOF seed 7 kept the same counts after saving its 191 readings and their predictions and factors. PostgreSQL and CSV lake-area frames matched.
- Streamlit AppTest loaded all eight pages in PostgreSQL, with the environment variable unset, and with a refused PostgreSQL connection. In PostgreSQL it also exercised playback, linked and manual alerts, acknowledgment, recipient records, alerts clearing and all 12 Query Lab choices. In SQLite it exercised the original test and clear buttons and checked the eight legacy columns.
- The SQLite migration copied one fixture row, skipped it on rerun and preserved the source file's SHA-256 hash.
