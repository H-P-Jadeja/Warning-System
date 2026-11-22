# Database selection

PostgreSQL stores time-stamped synthetic lake readings, model outputs, alert history, notification records and published area observations. Each reading belongs to an episode. Alerts can reference a prediction and have multiple recipient records. These relationships have explicit keys and repeatable joins.

Transactions let the app commit a reading episode together with its predictions and ranked factors. They also let it commit an alert and its notification records together. Foreign keys protect references and uniqueness prevents duplicate episode hours. SQL joins let operators inspect alert provenance. Aggregates and window functions support episode summaries and six-hour sensor deltas.

MongoDB could store an episode and its readings in an embedded document. In this workflow, independently managed recipients, shared level definitions and alerts linked to predictions would still require cross-document references. PostgreSQL enforces those relationships and supports the required cross-entity queries directly.

The simulator supplies synthetic readings. Evaluation metrics describe a synthetic holdout. The lake and map coordinates come from the app, and the area observations are approximate published values from the existing CSV. Recipient records and the settlement example are illustrative.
