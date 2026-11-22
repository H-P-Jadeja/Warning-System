# Normalization

## Starting point

The old SQLite table stores `(id, created_at, lake_id, sensor_time, level, score, message, status)`. Its columns are scalar, but a message embeds a list of factors and repeats formatted lake and level information. The unnormalized extension needed for database integration would also place repeated readings, prediction factors and recipient deliveries in the same alert-centric record.

An insert anomaly arises when recording a reading that never raises an alert, or a recipient who has yet to receive one. An update anomaly arises when changing level guidance across repeated alert rows. A delete anomaly arises when the last alert for a reading or recipient is removed and the only structured copy disappears.

## First normal form

Give each rank one row in `prediction_factors`. Give each alert, recipient and channel combination one row in `alert_notifications`. Store sensor attributes in typed columns. Keep the rendered message as an atomic historical artifact, with factors available to query independently.

## Second normal form

Move alert attributes out of the notification rows because they depend only on `alert_id`. Move the recipient's identity and routing attributes out because they depend only on `recipient_id`. Delivery status and time depend on the complete junction key. Similarly, a factor name depends on both prediction and rank.

## Third normal form

Move reusable lake, episode, risk-level, model and settlement attributes to their own tables. References identify those facts once. Representative functional dependencies include:

- `lake_id → name, latitude, longitude, state`
- `settlement_id → lake_id, name, coordinates, distance_km, population`
- `episode_id → scenario, seed, hours, created_at`, with `(scenario, seed)` a candidate key
- `reading_id → lake_id, episode_id, hour, recorded_at, sensor values`, with `(episode_id, hour)` a candidate key
- `level_id → level_name, colour, action, lead_time_hrs`
- `model_id → name, version, macro_f1, trained_on_note`
- `prediction_id → reading_id, model_id, level_id, risk_score`, with `reading_id` also unique
- `(prediction_id, rank) → feature_name`
- `alert_id → prediction_id, lake_id, effective level, score, sensor_time, message, status, acknowledgment, created_at`
- `recipient_id → name, role, telegram_chat_id, settlement_id, is_active, seed_key`
- `(alert_id, recipient_id, channel) → delivery_status, sent_at`
- `obs_id → lake_id, observed_on, area_km2, source, method, note`, with `(lake_id, observed_on, source)` also unique

Alerts intentionally retain a send-time snapshot of score, lake, sensor time and message. That snapshot survives the deletion of a prediction, and supports manual and imported alerts without a reading. The alert's effective risk level is a separate fact from the raw model level. This archival choice accounts for overlap with the otherwise normalized model.

The [final schema](sql/01_schema.sql) includes all 12 domain tables, an import ledger and the compatibility view.
