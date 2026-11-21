"""Allowlisted SQL and descriptions shared by the app and the evidence runner."""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Query:
    sql: str
    question: str
    explanation: str
    mutates: bool = False
    params: dict | None = None
    preview: str | None = None


DESCRIPTIONS = (
    ("How are a synthetic reading, prediction and ranked factors stored together?",
     "Writable CTEs pass each generated key to its dependent insert.",
     "SELECT * FROM predictions ORDER BY prediction_id DESC LIMIT 10"),
    ("Which rows change when a warning is acknowledged and a delivery failure is recorded?",
     "The updates target one demo alert and its notification rows.",
     "SELECT alert_id, ack_status, acknowledged_at FROM alerts ORDER BY alert_id DESC LIMIT 10"),
    ("What happens when we remove an old episode and clear demo alerts?",
     "The episode cascades to readings, predictions and factors. Clearing the demo alert cascades to notifications.",
     "SELECT episode_id, scenario, seed, hours FROM simulation_episodes ORDER BY episode_id DESC LIMIT 10"),
    ("What are the most recent HIGH and CRITICAL warnings?",
     "Filter by effective alert level and sort by creation time with an ID tie-breaker."),
    ("How many alerts occurred at each level?",
     "A left join retains risk levels with zero alerts."),
    ("Which episodes had more than five elevated predictions?",
     "Group raw predictions by episode and apply HAVING after counting."),
    ("What lake and sensor reading underpin each alert?",
     "Four tables expose both predicted and effective levels and retain unlinked manual alerts."),
    ("Which illustrative recipients have notification records, and which deliveries failed?",
     "Join through the notification junction. The status is the shared Telegram result."),
    ("Which readings exceed their lake's average water level?",
     "A correlated subquery computes the lake average and ignores missing water levels."),
    ("How much did water level change over six hours?",
     "LAG compares six rows within each episode. Continuous hourly pairs with two values match the model delta."),
    ("How many hours before the endpoint was the first linked warning?",
     "Aggregate the first linked alert and final reading per GLOF episode, then average warned episodes."),
    ("How wide is the published area range within each source and method?",
     "Subtract the minimum from the maximum. This spread does not imply chronological growth."),
)

source = Path(__file__).with_name("sql").joinpath("03_queries.sql").read_text()
statements = re.split(r"^-- (\d\d)\n", source, flags=re.MULTILINE)
QUERIES = {}
for number, statement in zip(statements[1::2], statements[2::2]):
    index = int(number)
    question, explanation, *preview = DESCRIPTIONS[index - 1]
    QUERIES[number] = Query(statement.strip(), question, explanation, index <= 3,
                            {"minimum": 5} if index == 6 else None,
                            preview[0] if preview else None)
