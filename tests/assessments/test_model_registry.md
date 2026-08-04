# test_model_registry.py

## Module-level tests

### test_register_model_persists_and_reads_definition_metadata

Purpose: Verify model registration persists configuration, output tasks, metadata, and reconstructable definitions in MLflow.

Load-bearing: True

Occurrence probability: 2

#### monkeypatch

#### tmp_path

#### mlflow_client

#### model_definition

### test_register_model_replays_offline_definition

Purpose: Verify registration journals metadata while offline and replays it into MLflow when connectivity returns.

Load-bearing: True

Occurrence probability: 2

#### monkeypatch

#### tmp_path

#### mlflow_client

#### model_definition
