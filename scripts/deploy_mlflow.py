"""Deploy the shared Cloud Run MLflow service from a Hydra-style config."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
from typing import Any

from omegaconf import DictConfig, OmegaConf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "conf" / "deploy" / "mlflow.yaml"


def _required(cfg: DictConfig, path: str) -> str:
    value: Any = OmegaConf.select(cfg, path)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing required deployment setting: {path}")
    return value


def deploy(cfg: DictConfig) -> None:
    """Deploy MLflow with Cloud SQL metadata and GCS artifacts."""
    project = _required(cfg, "gcp.project")
    region = _required(cfg, "gcp.region")
    service = _required(cfg, "service.name")
    image_uri = _required(cfg, "service.image_uri")
    service_account = _required(cfg, "service.account")
    sql_instance = _required(cfg, "cloud_sql.instance")
    backend_secret = _required(cfg, "cloud_sql.backend_store_uri_secret")
    bucket = _required(cfg, "artifacts.bucket")
    prefix = _required(cfg, "artifacts.prefix").strip("/")

    subprocess.run(
        [
            "gcloud",
            "run",
            "deploy",
            service,
            "--project",
            project,
            "--region",
            region,
            "--image",
            image_uri,
            "--service-account",
            service_account,
            "--add-cloudsql-instances",
            sql_instance,
            "--set-secrets",
            f"MLFLOW_BACKEND_STORE_URI={backend_secret}:latest",
            "--set-env-vars",
            f"MLFLOW_ARTIFACT_ROOT=gs://{bucket}/{prefix}",
            "--port",
            "8080",
        ],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args()
    deploy(OmegaConf.load(args.config))


if __name__ == "__main__":
    main()
