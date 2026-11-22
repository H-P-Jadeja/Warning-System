CREATE TABLE IF NOT EXISTS lakes (
    lake_id text PRIMARY KEY, name text NOT NULL, state text NOT NULL,
    latitude double precision NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude double precision NOT NULL CHECK (longitude BETWEEN -180 AND 180)
);
CREATE TABLE IF NOT EXISTS settlements (
    settlement_id text PRIMARY KEY,
    lake_id text NOT NULL REFERENCES lakes ON DELETE RESTRICT,
    name text NOT NULL,
    latitude double precision CHECK (latitude BETWEEN -90 AND 90),
    longitude double precision CHECK (longitude BETWEEN -180 AND 180),
    distance_km numeric CHECK (distance_km >= 0), population integer CHECK (population >= 0)
);
CREATE TABLE IF NOT EXISTS simulation_episodes (
    episode_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scenario text NOT NULL CHECK (scenario IN ('glof', 'normal')),
    seed integer NOT NULL CHECK (seed >= 0), hours integer NOT NULL CHECK (hours > 0),
    created_at timestamptz NOT NULL DEFAULT now(), UNIQUE (scenario, seed)
);
CREATE TABLE IF NOT EXISTS sensor_readings (
    reading_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lake_id text NOT NULL REFERENCES lakes ON DELETE RESTRICT,
    episode_id bigint NOT NULL REFERENCES simulation_episodes ON DELETE CASCADE,
    hour integer NOT NULL CHECK (hour >= 0), recorded_at timestamp NOT NULL,
    water_level_m double precision CHECK (water_level_m >= 0),
    seepage_rate double precision, dam_tilt_deg double precision, inflow_rate double precision,
    seismic_activity double precision CHECK (seismic_activity >= 0),
    rainfall_mm double precision CHECK (rainfall_mm >= 0), water_temp_c double precision,
    lake_area_km2 double precision CHECK (lake_area_km2 >= 0),
    UNIQUE (episode_id, hour)
);
CREATE TABLE IF NOT EXISTS risk_levels (
    level_id smallint PRIMARY KEY CHECK (level_id BETWEEN 0 AND 3),
    level_name text NOT NULL UNIQUE, colour text NOT NULL, action text NOT NULL,
    lead_time_hrs integer,
    CHECK ((level_id = 0 AND lead_time_hrs IS NULL) OR
           (level_id > 0 AND lead_time_hrs IS NOT NULL AND lead_time_hrs > 0))
);
CREATE TABLE IF NOT EXISTS ml_models (
    model_id text PRIMARY KEY, name text NOT NULL, version text NOT NULL,
    macro_f1 double precision NOT NULL CHECK (macro_f1 BETWEEN 0 AND 1),
    trained_on_note text NOT NULL
);
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    reading_id bigint NOT NULL UNIQUE REFERENCES sensor_readings ON DELETE CASCADE,
    model_id text NOT NULL REFERENCES ml_models ON DELETE RESTRICT,
    level_id smallint NOT NULL REFERENCES risk_levels ON DELETE RESTRICT,
    risk_score double precision NOT NULL CHECK (risk_score BETWEEN 0 AND 1)
);
CREATE TABLE IF NOT EXISTS prediction_factors (
    prediction_id bigint REFERENCES predictions ON DELETE CASCADE,
    rank integer CHECK (rank > 0), feature_name text NOT NULL,
    PRIMARY KEY (prediction_id, rank)
);
CREATE TABLE IF NOT EXISTS alerts (
    alert_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    prediction_id bigint REFERENCES predictions ON DELETE SET NULL,
    lake_id text NOT NULL REFERENCES lakes ON DELETE RESTRICT,
    level_id smallint NOT NULL REFERENCES risk_levels ON DELETE RESTRICT,
    sensor_time text NOT NULL, risk_score double precision NOT NULL CHECK (risk_score BETWEEN 0 AND 1),
    message text NOT NULL, status text NOT NULL,
    ack_status text NOT NULL DEFAULT 'NEW' CHECK (ack_status IN ('NEW', 'ACKNOWLEDGED')),
    acknowledged_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((ack_status = 'ACKNOWLEDGED') = (acknowledged_at IS NOT NULL))
);
CREATE TABLE IF NOT EXISTS recipients (
    recipient_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL CHECK (btrim(name) <> ''), role text NOT NULL CHECK (btrim(role) <> ''),
    telegram_chat_id text, settlement_id text REFERENCES settlements ON DELETE SET NULL,
    is_active boolean NOT NULL, seed_key text UNIQUE
);
CREATE TABLE IF NOT EXISTS alert_notifications (
    alert_id bigint REFERENCES alerts ON DELETE CASCADE,
    recipient_id bigint REFERENCES recipients ON DELETE CASCADE,
    channel text CHECK (btrim(channel) <> ''), delivery_status text NOT NULL,
    sent_at timestamptz, PRIMARY KEY (alert_id, recipient_id, channel)
);
CREATE TABLE IF NOT EXISTS lake_area_observations (
    obs_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lake_id text NOT NULL REFERENCES lakes ON DELETE RESTRICT,
    observed_on timestamp NOT NULL, area_km2 numeric NOT NULL CHECK (area_km2 > 0),
    source text NOT NULL, method text NOT NULL, note text, UNIQUE (lake_id, observed_on, source)
);
CREATE TABLE IF NOT EXISTS sqlite_alert_imports (
    source_key text PRIMARY KEY
);
CREATE INDEX IF NOT EXISTS sensor_lake_time_idx ON sensor_readings (lake_id, recorded_at);
CREATE INDEX IF NOT EXISTS prediction_level_idx ON predictions (level_id);
CREATE INDEX IF NOT EXISTS alert_created_idx ON alerts (created_at DESC);
CREATE INDEX IF NOT EXISTS alert_level_idx ON alerts (level_id);
CREATE INDEX IF NOT EXISTS notification_recipient_idx ON alert_notifications (recipient_id);

CREATE OR REPLACE VIEW alert_history AS
SELECT a.alert_id AS id, a.created_at, a.lake_id, a.sensor_time, l.level_name AS level,
       a.risk_score AS score, a.message, a.status
FROM alerts a JOIN risk_levels l USING (level_id);
