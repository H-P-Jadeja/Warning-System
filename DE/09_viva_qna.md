# Viva questions and answers

1. **Why PostgreSQL?** It enforces relationships between readings, predictions, alerts and recipients and supports the transactions and reporting joins the app needs.
2. **Where is one-to-one used?** Predictions have a unique reading ID. Every stored prediction belongs to one reading.
3. **Where is one-to-many used?** One episode has multiple hourly readings, and a risk level can classify multiple predictions.
4. **Where is many-to-many used?** The notification junction connects alerts and recipients and records the channel.
5. **Why is sensor time alone insufficient?** Distinct seeds reuse a timestamp sequence. Episode ID plus hour identifies each row.
6. **What changed at 1NF?** Each prediction factor and recipient delivery became its own record.
7. **What changed at 2NF?** Alert and recipient attributes moved away from delivery attributes that depend on the whole junction key.
8. **What changed at 3NF?** Lookup facts such as risk guidance and lake location moved to their owning entities.
9. **Why retain alert text and score?** They preserve the alert as raised even if its prediction is unavailable later.
10. **What is the difference between raw and effective risk?** The model assigns raw risk. The app applies the existing persistence rule to determine effective alert severity.
11. **What is a manual alert linked to?** Its lake and effective level. It has no model prediction.
12. **How is missing sensor data stored?** As SQL NULL, while the model continues its existing imputation.
13. **What prevents partial episode writes?** One transaction contains the episode and all dependent inserts.
14. **What prevents duplicate episodes?** A unique scenario-seed key checked by an insert with conflict handling.
15. **How is SQL injection avoided?** Application values are bound parameters, and dynamic table identifiers are quoted using the driver's identifier API.
16. **What does the six-hour query do?** It subtracts the reading six hourly rows earlier within the same episode and verifies the hour gap.
17. **What happens when an episode is removed?** Readings, predictions and factors cascade. Related alerts survive with their prediction references cleared.
18. **How does SQLite fallback work?** The legacy alert methods run locally if PostgreSQL cannot be opened or its schema is missing.
19. **Does each recipient receive a separate Telegram send?** The app uses its existing single destination. Active recipient records carry the shared delivery status for the demonstration.
20. **How can this schema scale?** Batch inserts and targeted indexes reduce work. High-volume deployment could add connection pooling and time partitioning after revisiting keys.
