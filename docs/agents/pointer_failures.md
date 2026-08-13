# Pointer Failures

Log of instances where an agent selected the wrong source document/doc-instance when pointed at "a doc" by the user or another doc — wrong branch copy, stale note, guessed path, etc. Purpose: build a record of the failure pattern so future triage/pointer logic can be corrected.

Fields:

- **correct source** — the document instance that should have been used.
- **source selected** — description (not a raw path) of what the agent actually accessed instead.
- **original pointer prompt** — the user/doc text that pointed the agent at the source.
- **reason given by agent** — the agent's own verbatim explanation for choosing that source, once asked for a plain language reason.
- **time** — `YYYYMMDD-HHMM`, 24-hour `HH` (00–23).

| correct source | source selected | reason given by agent | original pointer prompt | time |
| -------------- | --------------- | --------------------- | ----------------------- | ---- |
| `docs/agents/cloudops.md` MLflow section and Context7 MLflow documentation | repository-wide tracking search plus GCP Cloud Run and VM listings | "Training cannot start yet because there is no managed MLflow endpoint in the project; Terraform requires its HTTPS tracking URI." | "then run both" after the Cloud Operations routing instruction for cloud training | 20260811-1309 |
