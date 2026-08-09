# Grilling: Gap Between Agent Understanding and Ground Truth

| # | Gap description | Best guess at relevant file based on [project_instructions.md](docs/agents/project_instructions.md) description |
| ---: | --- | --- |
| 1 | Current canonical wording still calls the project operation “Cloud Run,” conflicting with Google’s Cloud Run API and the accepted project term “Feral Run.” | [cloudops.md](docs/agents/cloudops.md) — cloud-service ownership and operational entrypoints |
| 2 | “Feral Run” is not yet defined: its relationship to data runs, training runs, VM execution, and serverless execution remains unspecified. | [program-flow.md](docs/agents/program-flow.md) — system integration flows |
| 3 | The “Cloud Builds” flow incorrectly makes a Run Recipe directly produce a Cloud Run. It omits the distinct image-build path and its relationship to VM-based training. | [program-flow.md](docs/agents/program-flow.md) — data, model-sourcing, and cloud-training flows |
| 4 | The configuration vocabulary is incomplete: YAML/config, Docker YAML, Google Cloud Build configuration, and Run Recipe are not distinguished. | [configuration.md](docs/agents/configuration.md) — Hydra and model configuration requirements |
| 5 | The current lifecycle rule says every cloud run creates a VM, which conflicts with the stated serverless exception. | [cloudops.md](docs/agents/cloudops.md) — VM lifecycle and cloud operations |
| 6 | The durable-output requirement is documented, but the current startup script only uploads training evidence—not the runtime SQLite database, MLflow outputs, and best weights. | [cloudops.md](docs/agents/cloudops.md) — cloud operational entrypoints and lifecycle |
| 7 | The remote Dataset-existence rule needs one canonical contract for the configured folder and its manifest filename, so lack of local discovery never becomes evidence of absence. | [cloudops.md](docs/agents/cloudops.md) — script-controlled cloud operation |
| 8 | Model acquisition sequencing is incomplete in the flow: model existence must be checked before creating a Model Source Adapter. | [cloudops.md](docs/agents/cloudops.md) — cloud workflow control |
| 9 | The user-facing pipeline description still says “Cloud Run,” and therefore does not yet express the concrete, non-infrastructure-facing Feral Run vocabulary. | [user-interactions.md](docs/agents/user-interactions.md) — user-facing summaries |
| 10 | “Model Artifact” remains a useful search term for agents, but its concrete output set and human-facing replacement language need to remain aligned wherever training outputs are described. | [glossary.md](docs/domain/glossary.md) — domain terminology |
