-- 01
WITH reading AS (
    INSERT INTO sensor_readings (lake_id, episode_id, hour, recorded_at, water_level_m)
    VALUES ('SL001', %(episode)s, 0, '2024-08-01 00:00', 12.5)
    ON CONFLICT (episode_id, hour) DO NOTHING RETURNING reading_id
), prediction AS (
    INSERT INTO predictions (reading_id, model_id, level_id, risk_score)
    SELECT reading_id, 'capstone-v1', 2, 0.7 FROM reading RETURNING prediction_id
)
INSERT INTO prediction_factors (prediction_id, rank, feature_name)
SELECT prediction_id, factors.rank, factors.feature_name
FROM prediction CROSS JOIN (VALUES (1, 'water_level_m'), (2, 'rainfall_mm')) factors(rank, feature_name)
RETURNING prediction_id, rank, feature_name;
-- 02
WITH acknowledged AS (
    UPDATE alerts SET ack_status = 'ACKNOWLEDGED', acknowledged_at = now()
    WHERE alert_id = %(alert)s AND ack_status = 'NEW' RETURNING alert_id, ack_status
), delivery AS (
    UPDATE alert_notifications SET delivery_status = 'Illustrative failed delivery'
    WHERE alert_id = %(alert)s RETURNING alert_id, recipient_id, delivery_status
)
SELECT * FROM acknowledged JOIN delivery USING (alert_id) ORDER BY recipient_id;
-- 03
WITH removed_episode AS (
    DELETE FROM simulation_episodes WHERE episode_id = %(episode)s RETURNING episode_id
), cleared_alerts AS (
    DELETE FROM alerts WHERE alert_id = %(alert)s RETURNING alert_id
)
SELECT (SELECT count(*) FROM removed_episode) AS episodes_deleted,
       (SELECT count(*) FROM cleared_alerts) AS demo_alerts_cleared;
-- 04
SELECT id, lake_id, sensor_time, level, score, status
FROM alert_history WHERE level IN ('HIGH', 'CRITICAL')
ORDER BY created_at DESC, id DESC LIMIT 20;
-- 05
SELECT l.level_name, count(a.alert_id) AS alert_count
FROM risk_levels l LEFT JOIN alerts a USING (level_id)
GROUP BY l.level_id, l.level_name ORDER BY l.level_id;
-- 06
SELECT e.episode_id, e.scenario, e.seed, count(*) AS elevated_predictions
FROM simulation_episodes e JOIN sensor_readings r USING (episode_id)
JOIN predictions p USING (reading_id) WHERE p.level_id >= 2
GROUP BY e.episode_id HAVING count(*) > %(minimum)s
ORDER BY elevated_predictions DESC, e.episode_id LIMIT 50;
-- 07
SELECT a.alert_id, l.name AS lake, a.level_id AS effective_level_id,
       p.level_id AS predicted_level_id, r.recorded_at, r.water_level_m
FROM alerts a LEFT JOIN predictions p USING (prediction_id)
LEFT JOIN sensor_readings r USING (reading_id) JOIN lakes l ON l.lake_id = a.lake_id
ORDER BY a.alert_id DESC LIMIT 20;
-- 08
SELECT n.alert_id, r.name AS recipient, n.channel, n.delivery_status,
       n.delivery_status ~* '(failed|error)' AS failed
FROM alerts a JOIN alert_notifications n USING (alert_id) JOIN recipients r USING (recipient_id)
ORDER BY n.alert_id DESC, failed DESC, r.recipient_id LIMIT 30;
-- 09
SELECT r.lake_id, r.episode_id, r.hour, r.water_level_m
FROM sensor_readings r
WHERE r.water_level_m > (SELECT avg(s.water_level_m) FROM sensor_readings s WHERE s.lake_id = r.lake_id)
ORDER BY r.water_level_m DESC, r.episode_id, r.hour LIMIT 15;
-- 10
WITH changes AS (
    SELECT episode_id, hour, water_level_m, lag(hour, 6) OVER episode AS prior_hour,
           water_level_m - lag(water_level_m, 6) OVER episode AS water_level_d6
    FROM sensor_readings WINDOW episode AS (PARTITION BY episode_id ORDER BY hour)
)
SELECT episode_id, hour, water_level_m, water_level_d6 FROM changes
WHERE hour - prior_hour = 6 AND water_level_d6 IS NOT NULL ORDER BY episode_id, hour LIMIT 15;
-- 11
WITH ends AS (
    SELECT episode_id, max(recorded_at) AS end_time FROM sensor_readings GROUP BY episode_id
), first_alerts AS (
    SELECT r.episode_id, min(r.recorded_at) AS first_alert_time
    FROM alerts a JOIN predictions p USING (prediction_id) JOIN sensor_readings r USING (reading_id)
    GROUP BY r.episode_id
), lead AS (
    SELECT e.episode_id, e.seed,
           extract(epoch FROM (ends.end_time - f.first_alert_time)) / 3600 AS lead_hours
    FROM simulation_episodes e JOIN ends USING (episode_id)
    LEFT JOIN first_alerts f USING (episode_id) WHERE e.scenario = 'glof'
)
SELECT episode_id, seed, lead_hours, avg(lead_hours) OVER () AS mean_warned_lead_hours
FROM lead ORDER BY episode_id LIMIT 50;
-- 12
SELECT source, method, count(*) AS observations, min(area_km2) AS min_area_km2,
       max(area_km2) AS max_area_km2, max(area_km2) - min(area_km2) AS area_range_km2
FROM lake_area_observations WHERE lake_id = 'SL001'
GROUP BY source, method ORDER BY source, method;
