# app/dashboard.py   Run from project root:  streamlit run app/dashboard.py
import os, sys, json, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)   # so "ml" and "app" are importable

import pandas as pd
import streamlit as st

try:
    from ml.predict import predict_risk
    from ml.simulator import simulate_episode
    from ml.lake_area import get_lake_area_series
    USING = "real ML package"
except ImportError:
    from app.stubs import predict_risk, simulate_episode, get_lake_area_series
    USING = "STUBS (ml/ not found)"

from app import alerts, db

LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
LAKE = (27.92, 88.18)
CHUNGTHANG = (27.60, 88.64)
RESULTS = os.path.join(ROOT, "ml", "results")

st.set_page_config(page_title="GLOF EWS", layout="wide")


# ---------------- helpers ----------------
@st.cache_data(show_spinner="Running model on episode...")
def load_episode(scenario, seed):
    df = simulate_episode(scenario, int(seed))
    recs = df.to_dict("records")
    results = [predict_risk(recs[i], recs[max(0, i - 12): i]) for i in range(len(recs))]  # history oldest first
    df = df.copy()
    df["risk_score"] = [r["risk_score"] for r in results]
    df["level_index"] = [r["level_index"] for r in results]
    return df, results


def banner(res):
    info = alerts.LEVEL_INFO[res["risk_level"]]
    lead = res.get("estimated_lead_time_hrs")
    lead_txt = f"Estimated lead time: ~{lead} h" if lead is not None else "No warning lead time (normal)"
    st.markdown(
        f"<div style='background:{info['hex']};color:white;padding:14px;border-radius:8px;'>"
        f"<b style='font-size:22px'>{info['emoji']} {res['risk_level']} ({info['colour']})</b><br>"
        f"{info['action']}<br><small>{lead_txt}</small></div>", unsafe_allow_html=True)


def handle_alert(ctx, h, res, reading):
    state = st.session_state.get("alert_state")
    if state is None or state["ctx"] != ctx or h < state["hour"]:
        state = {"ctx": ctx, "level": 0, "hour": -999}
    lvl = res["level_index"]
    status = None
    if alerts.should_alert(state["level"], lvl, h - state["hour"]):
        status = alerts.raise_alert(reading, res)
        state = {"ctx": ctx, "level": lvl, "hour": h}
    elif lvl < state["level"]:
        state["level"] = lvl
    st.session_state["alert_state"] = state
    return status


def render_state(df, results, h, ctx):
    res, reading = results[h], df.iloc[h].to_dict()
    st.session_state["latest"] = (res, reading)
    status = handle_alert(ctx, h, res, reading)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Hour", int(reading["hour"]))
    c2.metric("Risk level", res["risk_level"])
    c3.metric("Risk score", f"{res['risk_score']:.2f}")
    c4.metric("Water level (m)", f"{reading['water_level_m']:.1f}")
    banner(res)
    st.write("**Key drivers:** " + ", ".join(res["top_factors"]))
    if status:
        st.info(f"Alert raised: {status}")

    d = df.iloc[: h + 1].set_index("hour")
    st.caption("Data source: simulated")
    a, b = st.columns(2)
    with a:
        st.subheader("Risk score")
        st.line_chart(d[["risk_score"]])
        st.subheader("Water level & seepage")
        st.line_chart(d[["water_level_m", "seepage_rate"]])
        st.subheader("Seismic activity & rainfall")
        st.line_chart(d[["seismic_activity", "rainfall_mm"]])
    with b:
        st.subheader("Dam tilt")
        st.line_chart(d[["dam_tilt_deg"]])
        st.subheader("Inflow rate")
        st.line_chart(d[["inflow_rate"]])
        st.subheader("Water temp & lake area")
        st.line_chart(d[["water_temp_c", "lake_area_km2"]])


# ---------------- sidebar ----------------
st.sidebar.title("🏔️ GLOF EWS")
page = st.sidebar.radio("Page", ["Overview", "Live Monitor", "Lake Growth", "Alerts Log", "Model Performance"])
st.sidebar.caption(f"Backend: {USING}")
st.sidebar.caption("Sensor data is synthetic; real labelled GLOF data is very scarce.")

# ---------------- pages ----------------
if page == "Overview":
    st.title("🏔️ GLOF Early Warning System - Overview")
    if "latest" in st.session_state:
        res, reading = st.session_state["latest"]
    else:
        df0, r0 = load_episode("normal", 7)
        res, reading = r0[-1], df0.iloc[-1].to_dict()
    info = alerts.LEVEL_INFO[res["risk_level"]]
    c1, c2 = st.columns(2)
    c1.metric("Current risk level", res["risk_level"])
    c2.metric("Risk score", f"{res['risk_score']:.2f}")
    banner(res)
    st.write("**Key drivers:** " + ", ".join(res["top_factors"]))
    st.subheader("Lake and downstream exposure")
    pts = pd.DataFrame({"name": ["South Lhonak Lake", "Chungthang town"],
                        "lat": [LAKE[0], CHUNGTHANG[0]], "lon": [LAKE[1], CHUNGTHANG[1]],
                        "color": [info["hex"], "#1565c0"], "size": [800, 500]})
    st.map(pts, latitude="lat", longitude="lon", color="color", size="size", zoom=8)
    st.caption("South Lhonak Lake (coloured by current risk level) and Chungthang town downstream. "
               "Outburst on 3-4 October 2023. Open Live Monitor to change the shown level.")

elif page == "Live Monitor":
    st.title("Live Monitor")
    c1, c2 = st.columns(2)
    scen_label = c1.selectbox("Scenario", ["GLOF precursor (South Lhonak-like)", "Normal behaviour"])
    seed = c2.number_input("Random seed", 0, 9999, 7)
    scenario = "glof" if scen_label.startswith("GLOF") else "normal"
    df, results = load_episode(scenario, int(seed))
    n = len(df)
    ctx = (scenario, int(seed))
    hour = st.slider("Current hour", 0, n - 1, n // 2, key=f"hour_{scenario}_{seed}")
    play = st.button("▶ Play from this hour")
    box = st.empty()
    if play:
        for h in range(hour, n, 3):
            with box.container():
                render_state(df, results, h, ctx)
            time.sleep(0.2)
        with box.container():
            render_state(df, results, n - 1, ctx)
    else:
        with box.container():
            render_state(df, results, hour, ctx)

elif page == "Lake Growth":
    st.title("Lake Growth - South Lhonak")
    ser = get_lake_area_series()
    st.warning("Approximate published observations (NRSC/ISRO radar-based maps and a secondary "
               "Planet Labs report). These are NOT Sentinel-2 NDWI values computed by this project.")
    st.scatter_chart(ser, x="date", y="area_km2")
    st.caption("The 4 Oct 2023 point is after the outburst, so the lake area drops sharply.")
    st.dataframe(ser, use_container_width=True)

elif page == "Alerts Log":
    st.title("Alerts Log")
    if st.button("Send test alert"):
        fake = {"lake_id": "SL001", "timestamp": "TEST"}
        fres = {"risk_score": 0.9, "risk_level": "CRITICAL", "level_index": 3,
                "top_factors": ["water_level_m", "seepage_rate", "dam_tilt_deg"],
                "estimated_lead_time_hrs": 6}
        st.info(alerts.raise_alert(fake, fres))
    if st.button("Clear log"):
        db.clear_alerts()
    log = db.get_alerts()
    if log.empty:
        st.write("No alerts raised yet. Run a GLOF scenario in Live Monitor.")
    else:
        st.dataframe(log, use_container_width=True)

elif page == "Model Performance":
    st.title("Model Performance")
    mpath = os.path.join(RESULTS, "metrics.json")
    if not os.path.exists(mpath):
        st.warning("ml/results/metrics.json not found.")
    else:
        m = json.load(open(mpath))
        if m.get("data_note"):
            st.warning(m["data_note"])
        st.write(f"Model: **{m.get('model', m.get('best_model', '-'))}**")
        sp = m.get("split_sizes")
        if sp:
            st.write(f"Train episodes: {sp.get('train_episodes')} | Test episodes: {sp.get('test_episodes')} "
                     f"(split by episode)")
        macro = m.get("macro_avg", {})
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Macro precision", f"{macro.get('precision', m.get('macro_precision', 0)):.2f}")
        c2.metric("Macro recall", f"{macro.get('recall', m.get('macro_recall', 0)):.2f}")
        c3.metric("Macro F1", f"{macro.get('f1', m.get('macro_f1', 0)):.2f}")
        c4.metric("Accuracy", f"{m.get('accuracy', 0):.2f}")
        if m.get("per_class"):
            st.subheader("Per class")
            st.dataframe(pd.DataFrame(m["per_class"]).T.round(2))
        if m.get("median_lead_time_hrs") is not None:
            st.write(f"Median lead time: {m['median_lead_time_hrs']} h")
        if m.get("model_comparison"):
            st.subheader("Model comparison")
            st.dataframe(pd.DataFrame(m["model_comparison"]).round(2))

    for fname, title in [("warning_timing.csv", "Warning timing"),
                         ("per_event_type_recall.csv", "Recall by event type"),
                         ("alert_persistence.csv", "Alert persistence")]:
        p = os.path.join(RESULTS, fname)
        if os.path.exists(p):
            st.subheader(title)
            st.dataframe(pd.read_csv(p), use_container_width=True)
    fa = os.path.join(RESULTS, "false_alarms.json")
    if os.path.exists(fa):
        st.subheader("False alarms")
        st.json(json.load(open(fa)))

    for f in ["confusion_matrix.png", "feature_importance.png", "risk_timeline_example.png",
              "lead_time_hist.png", "lake_area_growth.png"]:
        p = os.path.join(RESULTS, f)
        if os.path.exists(p):
            st.image(p, caption=f, use_container_width=True)
    st.title("Model Performance")
    mpath = os.path.join(RESULTS, "metrics.json")
    if not os.path.exists(mpath):
        st.warning("ml/results/metrics.json not found yet. It arrives with Member A's handoff.")
    else:
        m = json.load(open(mpath))
        st.write(f"Best model: **{m.get('best_model')}**")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Macro precision", f"{m.get('macro_precision', 0):.2f}")
        c2.metric("Macro recall", f"{m.get('macro_recall', 0):.2f}")
        c3.metric("Macro F1", f"{m.get('macro_f1', 0):.2f}")
        c4.metric("Median lead time (h)", f"{m.get('median_lead_time_hrs', 0):.1f}")
        st.write(f"False alarm rate (normal episodes): {m.get('false_alarm_rate_normal_episodes', 0):.2f}")
        if m.get("per_class"):
            st.subheader("Per class")
            st.dataframe(pd.DataFrame(m["per_class"]).T.round(2))
        if m.get("model_comparison"):
            st.subheader("Model comparison")
            st.dataframe(pd.DataFrame(m["model_comparison"]).round(2))
        if m.get("noise_robustness"):
            st.subheader("Noise robustness")
            st.dataframe(pd.DataFrame(m["noise_robustness"]).round(2))
    for f in ["confusion_matrix.png", "feature_importance.png", "risk_timeline_example.png",
              "lead_time_hist.png", "lake_area_growth.png"]:
        p = os.path.join(RESULTS, f)
        if os.path.exists(p):
            st.image(p, caption=f, use_container_width=True)