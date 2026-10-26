"""Cloud output preservation for the container training script."""

from __future__ import annotations

import base64
import hashlib
import json
import shutil
import sqlite3
import tempfile
import time
from contextlib import closing
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

from google.api_core.exceptions import GoogleAPICallError, NotFound
from google.cloud import storage
from google.cloud.storage.retry import DEFAULT_RETRY_IF_GENERATION_SPECIFIED


def instance_output_uri(bucket_uri: str) -> str:
    """Use this function to isolate one attempt under its numeric VM instance ID."""
    parsed = urlsplit(bucket_uri)
    if parsed.scheme != "gs" or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError(
            "Output destination must be a Cloud Storage bucket URI (gs scheme)"
        )
    request = Request(
        "http://metadata.google.internal/computeMetadata/v1/instance/id",
        headers={"Metadata-Flavor": "Google"},
    )
    with urlopen(request, timeout=10) as response:
        instance_id = response.read().decode().strip()
    if not instance_id.isdigit():
        raise ValueError("Metadata server did not return a numeric instance ID")
    return f"{bucket_uri.rstrip('/')}/instances/{instance_id}/{uuid4().hex}"


def upload_file(bucket, name: str, path: Path) -> None:
    """Use this function to upload a stable snapshot and verify its cloud bytes."""
    with path.open("rb") as stream:
        digest = base64.b64encode(hashlib.file_digest(stream, "md5").digest()).decode()
    blob = bucket.blob(name)
    try:
        blob.reload(timeout=30)
        generation = blob.generation
    except NotFound:
        generation = 0
    if generation and blob.md5_hash == digest and blob.size == path.stat().st_size:
        return
    blob.upload_from_filename(
        str(path),
        checksum="md5",
        if_generation_match=generation,
        retry=DEFAULT_RETRY_IF_GENERATION_SPECIFIED,
        timeout=60,
    )
    blob.reload(if_generation_match=blob.generation, timeout=30)
    if blob.md5_hash != digest or blob.size != path.stat().st_size:
        raise ValueError(f"Uploaded output failed verification: {name}")


def publish_outputs(directory: str, uri: str) -> None:
    """Use this function to preserve every output, including live SQLite databases."""
    root = Path(directory).resolve(strict=True)
    parsed = urlsplit(uri)
    if parsed.scheme != "gs" or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError(
            "Output destination must be a Cloud Storage bucket URI (gs scheme)"
        )
    bucket = storage.Client().bucket(parsed.netloc)
    files = {path: path.relative_to(root).as_posix() for path in root.rglob("*")}
    sources = root / "output-sources.json"
    if sources.exists():
        for source in json.loads(sources.read_text()):
            path = Path(source)
            if not path.is_absolute():
                raise ValueError("Additional output sources must be absolute paths")
            selected = [path] if path.is_file() else path.rglob("*")
            for item in selected:
                files[item] = "external/" + item.as_posix().lstrip("/")
    files = dict(
        sorted(
            files.items(),
            key=lambda item: (item[0] != root / "console.log", str(item[0])),
        )
    )
    databases = set()
    for path in files:
        if path.is_symlink():
            raise ValueError(f"Output symlinks are not supported: {path}")
        if path.is_file():
            with path.open("rb") as stream:
                if stream.read(16) == b"SQLite format 3\x00":
                    databases.add(path)
    errors = []
    with tempfile.TemporaryDirectory(prefix="training-export-") as temporary:
        for path in files:
            if not path.is_file():
                continue
            if path == root / "output-status.json":
                continue  # Only finish_outputs may publish terminal status.
            if any(
                str(path) == f"{db}{suffix}"
                for db in databases
                for suffix in ("-wal", "-shm", "-journal")
            ):
                continue
            snapshot = Path(temporary) / "snapshot"
            try:
                if path in databases:
                    with (
                        closing(
                            sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
                        ) as source,
                        closing(sqlite3.connect(snapshot)) as destination,
                    ):
                        source.backup(destination)
                else:
                    shutil.copyfile(path, snapshot)
                name = f"{parsed.path.strip('/')}/{files[path]}".lstrip("/")
                upload_file(bucket, name, snapshot)
            except (GoogleAPICallError, OSError, ValueError, sqlite3.Error) as error:
                # Preserve independent outputs even when one file cannot be exported.
                errors.append(error)
            finally:
                snapshot.unlink(missing_ok=True)
    if errors:
        raise ExceptionGroup("Output export failed", errors)


def watch_outputs(directory: str, uri: str) -> None:
    """Use this function to retain periodic copies before an unexpected VM loss."""
    import sys

    while True:
        try:
            publish_outputs(directory, uri)
        except (GoogleAPICallError, OSError, ValueError, ExceptionGroup) as error:
            # A final synchronous export must succeed; transient periodic failures may recover.
            print(
                f"Periodic output export failed: {error}", file=sys.stderr, flush=True
            )
        # shortcut: hard VM loss can lose unexported writes; use external streaming for stricter durability.
        time.sleep(30)


def train(
    config_dir: str,
    config_name: str,
    output_dir: str,
    overrides: list[str] | None = None,
) -> None:
    """Use this function to run the selected Hydra config without losing local outputs."""
    from hydra import compose, initialize_config_dir
    from omegaconf import OmegaConf

    from sightkit_learn.config.store import register_configs
    from sightkit_learn.training.trainer import build_dataloader, build_trainer

    root = Path(output_dir).resolve()
    register_configs()
    with initialize_config_dir(
        config_dir=str(Path(config_dir).resolve()), version_base=None
    ):
        cfg = compose(config_name=config_name, overrides=overrides or [])
    OmegaConf.save(cfg, root / "resolved-config.yaml", resolve=True)
    checkpoint = Path(cfg.train.best_model_path).resolve()
    external = []
    if not checkpoint.is_relative_to(root):
        external.append(str(checkpoint))
    tracking = cfg.get("tracking")
    if tracking:
        from sqlalchemy.engine import make_url

        uri = str(tracking.tracking_uri)
        if uri.startswith("sqlite:"):
            database = make_url(uri).database
            if not database or database == ":memory:":
                raise ValueError("An in-memory MLflow database cannot survive VM loss")
            if not Path(database).resolve().is_relative_to(root):
                external.append(str(Path(database).resolve()))
        elif urlsplit(uri).scheme in ("", "file"):
            location = Path(unquote(urlsplit(uri).path)).resolve()
            if not location.is_relative_to(root):
                external.append(str(location))
    (root / "output-sources.json").write_text(json.dumps(external) + "\n")
    try:
        trainer = build_trainer(cfg)
        train_loader = build_dataloader(cfg)
        history = trainer.fit(train_loader)
        (root / "history.json").write_text(json.dumps(history) + "\n")
    finally:
        export_mlflow_run(root)


def export_mlflow_run(root: Path) -> None:
    """Use this function to retain the run's tracking records and native model files."""
    import mlflow

    run = mlflow.active_run() or mlflow.last_active_run()
    if run is None:
        return
    client = mlflow.MlflowClient()
    run = client.get_run(run.info.run_id)
    exported = root / "mlflow-export"
    exported.mkdir(exist_ok=True)
    record = run.to_dictionary()
    record["metric_history"] = {
        key: [
            dict(metric) for metric in client.get_metric_history(run.info.run_id, key)
        ]
        for key in run.data.metrics
    }
    (exported / "run.json").write_text(json.dumps(record) + "\n")
    artifacts = exported / "artifacts"
    artifacts.mkdir(exist_ok=True)
    client.download_artifacts(run.info.run_id, "", str(artifacts))
    token = None
    while True:
        models = client.search_logged_models(
            experiment_ids=[run.info.experiment_id],
            filter_string=f"source_run_id = '{run.info.run_id}'",
            page_token=token,
        )
        for model in models:
            destination = exported / "models" / model.model_id
            destination.mkdir(parents=True, exist_ok=True)
            mlflow.artifacts.download_artifacts(
                artifact_uri=f"models:/{model.model_id}", dst_path=str(destination)
            )
        token = models.token
        if not token:
            break
    tags = run.data.tags
    if tags.get("registered_model_name") and tags.get("model_version"):
        version = client.get_model_version(
            tags["registered_model_name"], tags["model_version"]
        )
        (exported / "model-version.json").write_text(json.dumps(dict(version)) + "\n")


def finish_outputs(directory: str, uri: str, training_status: int) -> None:
    """Use this function to publish terminal status only after all outputs verify."""
    publish_outputs(directory, uri)
    status = Path(directory) / "output-status.json"
    status.write_text(
        json.dumps({"training_exit_code": training_status, "output_uri": uri}) + "\n"
    )
    parsed = urlsplit(uri)
    bucket = storage.Client().bucket(parsed.netloc)
    upload_file(bucket, f"{parsed.path.strip('/')}/output-status.json", status)
