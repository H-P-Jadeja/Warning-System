# Loaded sample records

Captured from a freshly seeded PostgreSQL database. Chungthang coordinates are from the dashboard. The settlement row and both recipients are illustrative. Distance and population are unknown. Chat IDs are fake. The lake-area rows preserve the five published approximations in the CSV.

```text
lake_id              name  state  latitude  longitude
  SL001 South Lhonak Lake Sikkim     27.92      88.18
```
```text
settlement_id lake_id                             name  latitude  longitude distance_km population
   CHUNGTHANG   SL001 Chungthang (illustrative record)      27.6      88.64        None       None
```
```text
 level_id level_name colour                                                                             action  lead_time_hrs
        0        LOW  Green                                                                  Normal monitoring            NaN
        1     MEDIUM Yellow                          Watch: increase monitoring frequency, notify control room           36.0
        2       HIGH Orange              Warning: alert authorities, prepare evacuation of downstream villages           18.0
        3   CRITICAL    Red Danger: evacuate immediately, notify all downstream settlements and infrastructure            6.0
```
```text
   model_id                       name version  macro_f1                                                                                       trained_on_note
capstone-v1 GradientBoostingClassifier      v1  0.862635 All evaluation results are based on synthetic data and do not represent real-world model performance.
```
```text
 recipient_id                            name        role telegram_chat_id settlement_id  is_active
            1       Illustrative control room Coordinator     fake-control          None       True
            2 Illustrative settlement liaison     Liaison     fake-liaison    CHUNGTHANG       True
```
```text
               date  area_km2                                                                                                                     source                method                                                           note
2023-09-17 00:00:00     1.627                                                                 NRSC/ISRO map ID 2023/FL/SIK/03-VAP/04-Oct-2023 (RISAT-1A) approximate_published                            approximate, radar-based, pre-event
2023-09-27 00:00:00     1.700 Planet Labs optical analysis by a researcher, reported by Down To Earth (9 Oct 2023) and EGU Cryospheric blog (2 Nov 2023) approximate_published secondary source, approximate; different sensor from NRSC rows
2023-09-28 00:00:00     1.674                                                              NRSC/ISRO map ID 2023/FL/SIK/03-VAP/04-Oct-2023 (Sentinel-1A) approximate_published                            approximate, radar-based, pre-event
2023-10-04 06:00:00     0.603                                                                 NRSC/ISRO map ID 2023/FL/SIK/03-VAP/04-Oct-2023 (RISAT-1A) approximate_published                                     approximate, post-outburst
2023-10-07 00:00:00     1.500 Planet Labs optical analysis by a researcher, reported by Down To Earth (9 Oct 2023) and EGU Cryospheric blog (2 Nov 2023) approximate_published                                  secondary source, approximate
```
## Row counts

- `alert_notifications` has 0 rows.
- `alerts` has 0 rows.
- `lake_area_observations` has 5 rows.
- `lakes` has 1 row.
- `ml_models` has 1 row.
- `prediction_factors` has 0 rows.
- `predictions` has 0 rows.
- `recipients` has 2 rows.
- `risk_levels` has 4 rows.
- `sensor_readings` has 0 rows.
- `settlements` has 1 row.
- `simulation_episodes` has 0 rows.
- `sqlite_alert_imports` has 0 rows.
