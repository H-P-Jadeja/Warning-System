# app/alerts.py - level mapping, Telegram, anti-repeat logic
import os
import requests
from app import db

LEVEL_INFO = {
    "LOW":      {"colour": "Green",  "hex": "#2e7d32", "emoji": "🟢", "action": "Normal monitoring"},
    "MEDIUM":   {"colour": "Yellow", "hex": "#f9a825", "emoji": "🟡",
                 "action": "Watch: increase monitoring frequency, notify control room"},
    "HIGH":     {"colour": "Orange", "hex": "#ef6c00", "emoji": "🟠",
                 "action": "Warning: alert authorities, prepare evacuation of downstream villages"},
    "CRITICAL": {"colour": "Red",    "hex": "#c62828", "emoji": "🔴",
                 "action": "Danger: evacuate immediately, notify all downstream settlements and infrastructure"},
}


def send_telegram(msg):
    tok, chat = os.getenv("TG_TOKEN"), os.getenv("TG_CHAT")
    if not (tok and chat):
        return "Preview only (TG_TOKEN / TG_CHAT not set)"
    try:
        r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                          data={"chat_id": chat, "text": msg}, timeout=10)
        return "Sent to Telegram" if r.ok else f"Telegram failed: {r.text}"
    except Exception as e:
        return f"Telegram error: {e}"


def should_alert(last_level, new_level, hours_since_last, repeat_hours=12):
    """Alert only when level goes up, or (HIGH/CRITICAL) every repeat_hours."""
    if new_level < 1:
        return False
    if new_level > last_level:
        return True
    return new_level >= 2 and hours_since_last >= repeat_hours


def build_message(reading, res):
    info = LEVEL_INFO[res["risk_level"]]
    lead = res.get("estimated_lead_time_hrs")
    lines = [
        f"{info['emoji']} GLOF ALERT [{res['risk_level']} / {info['colour']}]",
        f"Lake: {reading.get('lake_id', 'SL001')} (South Lhonak)",
        f"Time: {reading.get('timestamp', '-')}",
        f"Risk score: {res['risk_score']:.2f}",
        f"Key drivers: {', '.join(res['top_factors'])}",
    ]
    if lead is not None:
        lines.append(f"Estimated lead time: ~{lead} hours")
    lines.append(f"Action: {info['action']}")
    return "\n".join(lines)


def raise_alert(reading, res):
    msg = build_message(reading, res)
    status = send_telegram(msg)
    db.log_alert(reading.get("lake_id", "SL001"), reading.get("timestamp", ""),
                 res["risk_level"], res["risk_score"], msg, status)
    return status