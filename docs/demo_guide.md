# Dashboard Demo Guide

This guide is for a short judge-facing walkthrough of the Warning-System prototype. The episode facts below were computed from the repository's real `ml.simulator.simulate_episode`, `ml.predict.predict_risk` (with up to 12 previous rows, oldest first), and the `effective_level` / `should_alert` logic used by `app/dashboard.py`. They are results on synthetic data. The Streamlit UI was not launched to prepare this guide.

## Before the demo

From the repository root, install dependencies and start the dashboard:

```bash
pip install -r requirements.txt
streamlit run app/dashboard.py
```

Check the sidebar's **Backend:** caption. For the model-backed demo, it should say `real ML package` and should not show the STUB MODE warning. The chosen GLOF and normal episodes both use seed `7`, which is the dashboard's default and is within the `Random seed` input's offered range.

If `Alerts Log` already contains old local demo records and you want a clean demonstration, use **Clear log** before starting. This removes rows from the local SQLite alert history.

## Expected synthetic episode facts

The GLOF run uses the dashboard option **GLOF precursor (South Lhonak-like)**; seed `7` produces a seepage episode. The normal run uses **Normal behaviour**, also with seed `7`. Episode length is the number of hourly rows; event hour is the final GLOF row's `hour` value. Alert hours and counts below follow the dashboard's two-hour persistence and alert-repeat state logic.

| Scenario option | Seed | Event type | Episode length (hourly rows) | Event hour | First alert (hour, level) | First HIGH alert hour | First-alert lead before event | Alerts on normal episode |
|---|---:|---|---:|---:|---|---:|---:|---:|
| GLOF precursor (South Lhonak-like) | 7 | Seepage | 191 | 190 | 146, MEDIUM | 168 | 44 hours | — |
| Normal behaviour | 7 | None | 240 | None | None | None | None | 0 |

The GLOF run also produces later alert levels during the episode; the table records the first alert and first HIGH alert requested for the demonstration. The normal episode produces no alert rows under the same logic.

## Five-minute demo script

### 0:00–0:30 — Introduce the prototype

1. Open the **Overview** page using the sidebar page selector.
2. Say: “This prototype demonstrates how simulated sensor episodes flow through a trained risk model and into dashboard views. All sensor data are synthetic.”
3. Point out the **Backend:** caption. Continue with the model-backed results only if it shows `real ML package` and there is no STUB MODE warning.

### 0:30–2:15 — Play the GLOF episode

1. Select **Live Monitor** in the sidebar.
2. In the **Scenario** selector, choose **GLOF precursor (South Lhonak-like)**.
3. Leave **Random seed** at `7`. The generated episode has `191` hourly rows and event hour `190`; the initial **Current hour** slider value is `95` for this episode.
4. Set **Current hour** to `146`, the computed first alert hour. Point out **Effective alert level (2h): MEDIUM** and capture the effective-level screenshot.
5. Click **▶ Play from this hour**. The dashboard advances from this first alert through the selected GLOF episode and displays its risk level, risk score, sensor charts, and alert messages.
6. Say: “For this reproducible synthetic seepage episode, the first alert is MEDIUM at hour `146`, which is `44` hours before the simulated event. The first HIGH alert is at hour `168`.”

### 2:15–2:45 — Show the effective alert level

1. The initial GLOF frame at **Current hour** `146` shows the caption beside **Risk level**: **Effective alert level (2h)**.
2. Explain that it uses the minimum predicted level across the current and preceding available row, suppressing a one-row blip. The episode playback then continues from the same hour.

### 2:45–3:15 — Show Overview and alert history

1. Select **Overview**. It shows the latest rendered reading from the GLOF episode, including the risk-coloured lake map.
2. Select **Alerts Log**. Point out the rows logged during the GLOF replay. If Telegram is not configured, the alert status is a preview; the local alert record is still logged.

### 3:15–4:00 — Compare the normal episode

1. Select **Live Monitor**.
2. Choose **Normal behaviour** in **Scenario** and leave **Random seed** at `7`.
3. Click **▶ Play from this hour**. The normal episode has `240` hourly rows and produces `0` alerts in the offline calculation.
4. Say: “This normal run contains the simulator's sensor noise and fault examples; this particular seeded run does not raise an alert.”

### 4:00–4:35 — Show lake-area observations

1. Select **Lake Growth**.
2. Point to the chart and table. Explain that these are approximate published observations from NRSC radar maps and secondary Planet Labs reporting, not a Sentinel-2 NDWI series computed by this project.

### 4:35–5:00 — Show model artifacts and close

1. Select **Model Performance**. Point out the confusion matrix and feature-importance figure if they are displayed.
2. The current dashboard page looks for some top-level metric keys that are not in the current `ml/results/metrics.json` schema. Its summary cards may therefore show empty or zero values; use the saved `ml/results/metrics.json` and report for the actual metrics rather than presenting those cards as the recorded report.
3. Close with the honesty note below.

## Screenshot checklist

Save screenshots in `docs/screenshots/` using these target names. The folder starts empty except for `.gitkeep`; no screenshots were captured while preparing this guide.

- [ ] `overview-glof.png` — **Overview** after rendering the GLOF episode.
- [ ] `effective-alert-level.png` — **Live Monitor** at the first alert, showing the **Effective alert level (2h)** caption.
- [ ] `alerts-log.png` — **Alerts Log** with the GLOF replay's entries.
- [ ] `lake-growth.png` — **Lake Growth** chart and observation table.
- [ ] `model-performance.png` — **Model Performance** page, including any visible figures and its current summary-card behavior.
- [ ] `normal-no-alerts.png` — **Live Monitor** with **Normal behaviour**, seed `7`, and no newly raised alerts.

## If something goes wrong

- **The sidebar shows STUB MODE:** one or more ML imports fell back to `app/stubs.py`. Those outputs are fake and not model predictions. Check that the project dependencies and ML modules are available, then restart the dashboard; do not present stub output as model-backed results.
- **`ml/model.pkl` is missing:** the real predictor loads that bundle from the `ml/` directory. Restore the tracked model bundle before the demo. If it cannot be restored, do not claim to be demonstrating real-model predictions.
- **The contract checker reports a scikit-learn version warning:** `requirements.txt` pins scikit-learn to `1.8.0`. Install the pinned requirements in the active environment and rerun the checks before presenting the saved-model results.
- **Telegram is not configured:** without both `TG_TOKEN` and `TG_CHAT`, Telegram delivery returns a preview status. Dashboard alert rows are still written to the local SQLite log; do not claim that a Telegram message was sent.
- **Model Performance summary cards look empty or show zeros:** the page currently requests keys such as `best_model` and top-level macro metrics, while `ml/evaluate.py` writes a different JSON structure. Refer to `ml/results/metrics.json` and the report for the recorded metrics.

## Honesty note for presenters

Say aloud: “This is a prototype using synthetic sensor data. It is not an operational warning system. The lake-area values are approximate published observations, not values calculated by this project from Sentinel-2 NDWI.”
