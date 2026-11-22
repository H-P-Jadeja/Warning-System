# PostgreSQL data engineering submission

Demo video: *(link will be added)*

Run from the repository root with the project's Python environment active. The PostgreSQL driver was installed and tested on Python 3.14.

1. Install the pinned dependencies with `python -m pip install -r requirements.txt`.
2. Install and start PostgreSQL locally, or provision a PostgreSQL database with a cloud provider. Create a project database and use a role with schema creation and read/write permissions there.
3. Set `DATABASE_URL` in your shell. Use `cp .env.example .env` if you prefer a local file, edit the placeholders, then run `source .env`. The app reads its environment. Use your provider's connection parameters and TLS settings.
4. Run `python -m DE.setup_db` to create the schema, load the lookup values and import the five published area observations. It is safe to rerun. Use a separate database for demonstrations.
5. Optional legacy import. Run `python -m DE.migrate_sqlite_to_postgres` to copy existing `app/alerts.db` entries, or supply a different SQLite path. The source is opened read-only, PostgreSQL IDs are assigned afresh, and imported rows remain unlinked to predictions. A legacy wall-clock timestamp is interpreted in the PostgreSQL session timezone, so set that timezone to match the original app before migrating. Invalid rows roll back the import with the source row ID.
6. For preview-only demos, run `unset TG_TOKEN TG_CHAT`. Start the dashboard with `python -m streamlit run app/dashboard.py`.
7. Run `python -m DE.run_queries` to regenerate the query evidence and `python -m DE.demo_integration` to exercise CRUD through the app API. The query runner rolls back its fixtures and writes; identity sequences may still advance. The CRUD demo commits changes to a disposable inactive recipient and deletes it afterward.
8. Run `python -m app.check_alert_logic`, `python -m ml.check_contract` and `bash check_all.sh`. Unset `DATABASE_URL` and relaunch to use legacy SQLite.

The submission covers [database choice](01_database_selection.md), [ER model](02_er_diagram.md), [normalization](03_normalization.md), [schema](04_schema.md), [loaded records](05_sample_data.md), [queries](06_queries.md), [query outputs](06_query_outputs.md), [integration evidence](07_integration_evidence.md), [architecture](08_architecture_notes.md) and [viva questions](09_viva_qna.md).
