# Screenshots to capture

Use a PostgreSQL demo database and unset `TG_TOKEN` and `TG_CHAT` before starting Streamlit.

1. `01-database-counts.png` — Database page with the PostgreSQL sidebar caption and table counts.
2. `02-live-monitor.png` — Live Monitor on GLOF seed 7 at hour 146, showing the effective alert level. Open the Database page afterward to verify readings, predictions and factors were saved.
3. `03-alert-acknowledgment.png` — Alerts Log filtered to MEDIUM, with an alert acknowledged and its recipient notification rows visible.
4. `04-recipient-insert.png` — Recipients page after adding a disposable inactive example.
5. `05-recipient-update.png` — The same recipient after changing its role.
6. `06-recipient-delete.png` — Recipients page after confirming deletion of that example.
7. `07-query-lab.png` — Query Lab with query 10 selected, showing SQL and a live result.
8. `08-lake-growth.png` — Lake Growth with the five PostgreSQL-backed published observations.
9. `09-sqlite-fallback.png` — Restart without `DATABASE_URL` and open the Database page to show the fallback caption and configuration message.
