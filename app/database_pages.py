"""Streamlit controls for the PostgreSQL pages."""

import streamlit as st

from app import db
from DE.queries import QUERIES


def alert_details(levels):
    left, middle, right = st.columns(3)
    level = left.selectbox("Level filter", ["All", *levels])
    start = middle.date_input("Created on or after", value=None)
    end = right.date_input("Created on or before", value=None)
    if start and end and end < start:
        st.warning("Choose an end date on or after the start date.")
        return
    rows = db.get_alert_details({"level": None if level == "All" else level, "start": start, "end": end})
    if rows.empty:
        st.write("No alerts match the filters.")
        return
    st.dataframe(rows, hide_index=True)
    alert_id = st.selectbox("Alert ID", rows["id"].tolist())
    if st.button("Acknowledge"):
        db.acknowledge_alert(alert_id)
        st.rerun()
    st.subheader("Notifications")
    st.dataframe(db.get_notifications(alert_id), hide_index=True)


def recipients():
    st.title("Recipients")
    st.caption("Recipients track illustrative notification records. Telegram still uses the configured TG_CHAT.")
    rows = db.get_recipients()
    st.dataframe(rows, hide_index=True)
    selected = st.selectbox("Recipient to edit", [None, *rows["recipient_id"].tolist()],
                            format_func=lambda value: "Add recipient" if value is None else str(value))
    current = {} if selected is None else rows.set_index("recipient_id").loc[selected].to_dict()
    settlements = db.get_settlements().set_index("settlement_id")["name"].to_dict()
    options = [None, *settlements]
    with st.form(f"recipient_{selected}"):
        name = st.text_input("Name", current.get("name", ""))
        role = st.text_input("Role", current.get("role", ""))
        chat = st.text_input("Telegram chat ID", current.get("telegram_chat_id") or "")
        settlement = st.selectbox("Settlement", options, index=options.index(current.get("settlement_id")),
                                  format_func=lambda value: settlements.get(value, "None"))
        active = st.checkbox("Active", bool(current.get("is_active", True)))
        save = st.form_submit_button("Save recipient")
    if save:
        if not name.strip() or not role.strip():
            st.warning("Enter a name and role.")
        else:
            values = (name.strip(), role.strip(), chat.strip() or None, settlement, active)
            if selected is None:
                db.add_recipient(*values)
            else:
                db.update_recipient(selected, *values)
            st.rerun()
    if selected is not None and st.checkbox("Confirm deletion of this recipient and their notification links"):
        if st.button("Delete recipient"):
            db.delete_recipient(selected)
            st.rerun()


def query_lab():
    st.title("Query Lab")
    name = st.selectbox("Query", list(QUERIES), format_func=lambda key: f"{key}  {QUERIES[key].question}")
    query = QUERIES[name]
    st.code(query.sql, language="sql")
    st.write(query.explanation)
    if query.params:
        st.caption("Parameters")
        st.json(query.params)
    if query.preview:
        st.caption("Live read-only preview. Run the write example with python -m DE.run_queries.")
        st.code(query.preview, language="sql")
    st.dataframe(db.run_named_query(name), hide_index=True)


def database():
    st.title("Database")
    st.write("Active backend is PostgreSQL.")
    st.dataframe([{"Table": name, "Rows": count} for name, count in db.get_table_counts().items()],
                 hide_index=True)
    st.write("Episodes group readings. Each reading has at most one prediction, with ranked factors. "
             "Alerts can link to predictions and notify multiple recipients through the notification table. "
             "Published lake-area observations are stored separately from simulated sensor values.")
