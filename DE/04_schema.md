# PostgreSQL schema

The [SQL definition](sql/01_schema.sql) is authoritative. [The ER diagram](02_er_diagram.md) lists columns and relationship cardinalities.

- Lakes use a stable text key. Settlements reference a lake. Deleting a settlement unlinks its recipients.
- Episodes are unique by scenario and seed. Readings are unique by episode and hour because distinct simulations can share timestamps. The hour count is the number of materialized rows.
- Predictions reference a single reading, model version and raw risk level. A unique reading reference makes the relationship one-to-one for stored predictions. Factors use a composite prediction and rank key.
- Alerts reference the lake and effective risk level, optionally linking a prediction. An alert's acknowledgment timestamp is present exactly when the status is acknowledged. The compatibility view exposes the eight legacy columns.
- Recipient and alert deletions cascade to their junction rows. Deleting an episode cascades to readings, predictions and factors, preserving linked alerts with a null prediction reference. Referenced lakes, levels and models use restricted deletion.
- Area observations use a timestamp to preserve the time on the post-outburst CSV record. A natural unique key combines lake, timestamp and source.
- `sqlite_alert_imports` records migration fingerprints to make a repeat import skip previously copied rows, including rows later cleared from the alert log.

## Indexes

- `sensor_lake_time_idx` supports per-lake timestamp scans.
- `prediction_level_idx` supports filtering by raw severity.
- `alert_created_idx` supports creation-date filtering and recent history.
- `alert_level_idx` supports effective-severity filtering and aggregation.
- `notification_recipient_idx` supports notification lookup and cascading deletes by recipient. The junction primary key already covers alert-first scans.

PostgreSQL enforces required values, coordinate and severity ranges, score bounds, unique keys and foreign keys. Lake level, area, seismic activity and rainfall have nonnegative checks where applicable. Optional readings missing in pandas become SQL NULL, which preserves the original missingness. Simulation duplicates are skipped at the episode key before dependent inserts. An invalid dependent insert rolls back the whole episode. Manual alerts have no prediction link, and missing settlement demographics are kept as NULL.
