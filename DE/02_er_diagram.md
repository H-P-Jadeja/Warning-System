# Entity relationship diagram

Open the [rendered SVG](02_er_diagram.svg) for the full-size diagram. It shows the logical model. The view and import ledger are described in [the schema notes](04_schema.md). The SQL schema defines all attributes and constraints.

```mermaid
erDiagram
    LAKES ||--o{ SETTLEMENTS : has
    LAKES ||--o{ SENSOR_READINGS : supplies
    LAKES ||--o{ ALERTS : concerns
    LAKES ||--o{ LAKE_AREA_OBSERVATIONS : has
    SIMULATION_EPISODES ||--o{ SENSOR_READINGS : groups
    SENSOR_READINGS ||--o| PREDICTIONS : has
    ML_MODELS ||--o{ PREDICTIONS : produces
    RISK_LEVELS ||--o{ PREDICTIONS : classifies
    RISK_LEVELS ||--o{ ALERTS : classifies
    PREDICTIONS ||--o{ PREDICTION_FACTORS : ranks
    PREDICTIONS o|--o{ ALERTS : explains
    SETTLEMENTS o|--o{ RECIPIENTS : hosts
    ALERTS ||--o{ ALERT_NOTIFICATIONS : records
    RECIPIENTS ||--o{ ALERT_NOTIFICATIONS : receives

    LAKES {
        text lake_id PK
        text name
        float latitude
        float longitude
        text state
    }
    SETTLEMENTS {
        text settlement_id PK
        text lake_id FK
        text name
        float latitude
        float longitude
        numeric distance_km
        integer population
    }
    SIMULATION_EPISODES {
        bigint episode_id PK
        text scenario
        integer seed
        integer hours
        timestamptz created_at
    }
    SENSOR_READINGS {
        bigint reading_id PK
        text lake_id FK
        bigint episode_id FK
        integer hour
        timestamp recorded_at
        float water_level_m
        float seepage_rate
        float dam_tilt_deg
        float inflow_rate
        float seismic_activity
        float rainfall_mm
        float water_temp_c
        float lake_area_km2
    }
    RISK_LEVELS {
        smallint level_id PK
        text level_name UK
        text colour
        text action
        integer lead_time_hrs
    }
    ML_MODELS {
        text model_id PK
        text name
        text version
        float macro_f1
        text trained_on_note
    }
    PREDICTIONS {
        bigint prediction_id PK
        bigint reading_id FK, UK
        text model_id FK
        smallint level_id FK
        float risk_score
    }
    PREDICTION_FACTORS {
        bigint prediction_id PK, FK
        integer rank PK
        text feature_name
    }
    ALERTS {
        bigint alert_id PK
        bigint prediction_id FK
        text lake_id FK
        smallint level_id FK
        text sensor_time
        float risk_score
        text message
        text status
        text ack_status
        timestamptz acknowledged_at
        timestamptz created_at
    }
    RECIPIENTS {
        bigint recipient_id PK
        text name
        text role
        text telegram_chat_id
        text settlement_id FK
        boolean is_active
        text seed_key UK
    }
    ALERT_NOTIFICATIONS {
        bigint alert_id PK, FK
        bigint recipient_id PK, FK
        text channel PK
        text delivery_status
        timestamptz sent_at
    }
    LAKE_AREA_OBSERVATIONS {
        bigint obs_id PK
        text lake_id FK
        timestamp observed_on
        numeric area_km2
        text source
        text method
        text note
    }
```

Alerts and recipients have a many-to-many relationship through `alert_notifications`. Prediction references are optional so manual alerts and retained historical alerts can exist independently. To export an image with Mermaid CLI, extract the fenced source with `sed -n '/^```mermaid$/,/^```$/p' DE/02_er_diagram.md | sed '1d;$d' > /tmp/warning-er.mmd`, then run `mmdc -i /tmp/warning-er.mmd -o DE/02_er_diagram.svg`.
