"""Output preservation with real files, fictitious bucket URIs and a mocked SDK."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import io
import json
import shutil
import sqlite3
from pathlib import Path
from unittest.mock import create_autospec

import pytest
from google.api_core.exceptions import NotFound, ServiceUnavailable
from google.cloud import storage

TEST_BUCKET = "gs://bucket"  # gitleaks:allow (fictitious bucket)

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "feral-vision/scripts/runs/run_outputs.py"
)
spec = importlib.util.spec_from_file_location("run_outputs", MODULE_PATH)
outputs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(outputs)


@pytest.fixture
def cloud(monkeypatch):
    """Use this fixture for SDK-signature-checked uploads with retained remote bytes."""
    contents = {}
    uploaded = []
    bucket = create_autospec(storage.Bucket, instance=True)

    def blob_for(name):
        """Use this function to model GCS generation checks and read-back metadata."""
        blob = create_autospec(storage.Blob, instance=True)

        def reload(**kwargs):
            """Use this function to expose metadata only for existing objects."""
            if name not in contents:
                raise NotFound(name)
            data = contents[name]
            blob.generation = 1
            blob.size = len(data)
            blob.md5_hash = base64.b64encode(hashlib.md5(data).digest()).decode()

        def upload(filename, **kwargs):
            """Use this function to retain uploaded bytes rather than merely count calls."""
            assert kwargs["if_generation_match"] == (1 if name in contents else 0)
            contents[name] = Path(filename).read_bytes()
            uploaded.append(name)
            reload()

        blob.reload.side_effect = reload
        blob.upload_from_filename.side_effect = upload
        return blob

    bucket.blob.side_effect = blob_for
    client = create_autospec(storage.Client, instance=True)
    client.bucket.return_value = bucket
    monkeypatch.setattr(outputs.storage, "Client", lambda: client)
    return contents, uploaded, bucket


def test_export_restores_arbitrary_files_logs_and_live_sqlite(tmp_path, cloud):
    """Use this test to prove exports survive deletion of the source workspace."""
    root = tmp_path / "work"
    root.mkdir()
    (root / "nested").mkdir()
    (root / "nested" / "weights.custom").write_bytes(b"trained weights")
    (root / "console.log").write_text("stdout line\nstderr line\n")
    database = sqlite3.connect(root / "tracking.database")
    database.execute("pragma journal_mode=wal")
    database.execute("create table metrics(value real)")
    database.execute("insert into metrics values (1.25)")
    database.commit()
    try:
        outputs.finish_outputs(
            str(root),
            f"{TEST_BUCKET}/instances/123/attempt",
            0,
        )
    finally:
        database.close()
    contents, uploaded, _ = cloud
    assert uploaded[-1].endswith("output-status.json")
    shutil.rmtree(root)
    restored = tmp_path / "restored"
    restored.mkdir()
    for name, data in contents.items():
        path = restored / name.removeprefix("instances/123/attempt/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    assert (restored / "nested" / "weights.custom").read_bytes() == b"trained weights"
    assert "stderr line" in (restored / "console.log").read_text()
    with sqlite3.connect(restored / "tracking.database") as connection:
        assert connection.execute("select value from metrics").fetchone() == (1.25,)
    assert not any(name.endswith(("-wal", "-shm")) for name in contents)
    assert (
        json.loads((restored / "output-status.json").read_text())["training_exit_code"]
        == 0
    )


def test_failed_export_never_publishes_terminal_status(tmp_path, cloud, monkeypatch):
    """Use this test to reject success when any required output cannot upload."""
    (tmp_path / "console.log").write_text("keep this diagnostic")
    monkeypatch.setattr(
        outputs,
        "upload_file",
        create_autospec(
            outputs.upload_file, side_effect=ServiceUnavailable("upload failed")
        ),
    )
    with pytest.raises(ExceptionGroup, match="Output export failed"):
        outputs.finish_outputs(
            str(tmp_path),
            f"{TEST_BUCKET}/instances/123/attempt",
            0,
        )
    assert not (tmp_path / "output-status.json").exists()
    assert (tmp_path / "console.log").is_file()


def test_failed_training_exports_its_diagnostics_and_failure_status(tmp_path, cloud):
    """Use this test to retain partial outputs when training itself failed."""
    (tmp_path / "console.log").write_text("training traceback")
    outputs.finish_outputs(
        str(tmp_path),
        f"{TEST_BUCKET}/instances/123/failure",
        17,
    )
    contents, _, _ = cloud
    assert contents["instances/123/failure/console.log"] == b"training traceback"
    assert (
        json.loads(contents["instances/123/failure/output-status.json"])[
            "training_exit_code"
        ]
        == 17
    )


def test_each_attempt_is_scoped_to_numeric_vm_identity(monkeypatch):
    """Use this test to prevent shared output locations across VM attempts."""
    response = io.BytesIO(b"123456789")
    lookup = create_autospec(outputs.urlopen, return_value=response)
    monkeypatch.setattr(outputs, "urlopen", lookup)
    first = outputs.instance_output_uri(f"{TEST_BUCKET}/jobs")
    lookup.return_value = io.BytesIO(b"123456789")
    second = outputs.instance_output_uri(f"{TEST_BUCKET}/jobs")
    assert first.startswith(f"{TEST_BUCKET}/jobs/instances/123456789/")
    assert first != second
    request = lookup.call_args.args[0]
    assert request.get_header("Metadata-flavor") == "Google"
    assert request.full_url.endswith("/instance/id")
    lookup.return_value = io.BytesIO(b"987654321")
    other_vm = outputs.instance_output_uri(f"{TEST_BUCKET}/jobs")
    assert other_vm.startswith(f"{TEST_BUCKET}/jobs/instances/987654321/")


def test_remote_checksum_mismatch_is_an_export_failure(tmp_path, cloud, monkeypatch):
    """Use this test to require cloud verification rather than upload success alone."""
    path = tmp_path / "weights"
    path.write_bytes(b"weights")
    _, _, bucket = cloud
    blob = create_autospec(storage.Blob, instance=True)
    blob.reload.side_effect = [NotFound("absent"), None]
    blob.md5_hash = "wrong"
    blob.size = len(b"weights")
    blob.generation = 1
    bucket.blob.side_effect = None
    bucket.blob.return_value = blob
    with pytest.raises(ValueError, match="failed verification"):
        outputs.upload_file(bucket, "weights", path)


@pytest.mark.parametrize(
    "training_status,export_failure,terminate",
    [(0, False, False), (17, False, False), (0, True, False), (143, False, True)],
)
def test_shell_captures_both_streams_and_exports_after_training(
    tmp_path, training_status, export_failure, terminate
):
    """Use this test to exercise the real shell and exporter across child processes."""
    import os
    import signal
    import subprocess
    import sys
    import time

    hook = tmp_path / "hooks"
    hook.mkdir()
    (hook / "sitecustomize.py").write_text("""
import base64, hashlib, io, os
from pathlib import Path
from unittest.mock import create_autospec
from google.cloud import storage
from google.api_core.exceptions import NotFound, ServiceUnavailable
import run_outputs

cloud = Path(os.environ['TEST_CLOUD'])
bucket = create_autospec(storage.Bucket, instance=True)
def blob_for(name):
    path = cloud / name
    blob = create_autospec(storage.Blob, instance=True)
    def reload(**kwargs):
        if not path.exists(): raise NotFound(name)
        data = path.read_bytes()
        blob.generation = 1
        blob.size = len(data)
        blob.md5_hash = base64.b64encode(hashlib.md5(data).digest()).decode()
    def upload(filename, **kwargs):
        if name.endswith('arbitrary-output') and os.environ['TEST_EXPORT_FAILURE'] == '1':
            raise ServiceUnavailable('artifact upload failed')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(Path(filename).read_bytes())
        reload()
    blob.reload.side_effect = reload
    blob.upload_from_filename.side_effect = upload
    return blob
bucket.blob.side_effect = blob_for
client = create_autospec(storage.Client, instance=True)
client.bucket.return_value = bucket
storage.Client = lambda: client
run_outputs.urlopen = lambda *a, **k: io.BytesIO(b'123456789')
def training(*args):
    print('training standard output', flush=True)
    print('training standard error', file=__import__('sys').stderr, flush=True)
    Path('arbitrary-output').write_bytes(b'trained result')
    if os.environ['TEST_TERMINATE'] == '1': __import__('time').sleep(60)
    if int(os.environ['TEST_TRAINING_STATUS']):
        raise SystemExit(int(os.environ['TEST_TRAINING_STATUS']))
run_outputs.train = training
""")
    executable = Path(sys.executable).parent
    env = {
        **os.environ,
        "PATH": str(executable) + os.pathsep + os.environ["PATH"],
        "PYTHONPATH": str(hook),
        "CONFIG_DIR": str(tmp_path),
        "CONFIG_NAME": "user-selected-config",
        "RUN_OUTPUT_DIR": str(tmp_path / "outputs"),
        "TRAINING_DATA_BUCKET_URI": f"{TEST_BUCKET}/user-prefix",
        "TEST_CLOUD": str(tmp_path / "cloud"),
        "TEST_TRAINING_STATUS": str(training_status),
        "TEST_EXPORT_FAILURE": str(int(export_failure)),
        "TEST_TERMINATE": str(int(terminate)),
    }
    with subprocess.Popen(
        ["bash", str(MODULE_PATH.with_name("cloud_train.sh"))],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as process:
        if terminate:
            deadline = time.monotonic() + 10
            while not (tmp_path / "outputs/arbitrary-output").exists():
                assert time.monotonic() < deadline, "training never started"
                time.sleep(0.05)
            process.send_signal(signal.SIGTERM)
        _stdout, stderr = process.communicate(timeout=30)
        assert process.returncode == (1 if export_failure else training_status), stderr
    logs = list((tmp_path / "cloud").rglob("console.log"))
    assert len(logs) == 1
    text = logs[0].read_text()
    assert "training standard output" in text
    assert "training standard error" in text
    if export_failure:
        assert not logs[0].with_name("output-status.json").exists()
        assert (tmp_path / "outputs" / "arbitrary-output").is_file()
        return
    assert logs[0].with_name("arbitrary-output").read_bytes() == b"trained result"
    status = json.loads(logs[0].with_name("output-status.json").read_text())
    assert status["training_exit_code"] == training_status


@pytest.mark.parametrize("absolute_outputs", [False, True])
def test_real_hydra_training_and_mlflow_outputs_restore_after_workspace_loss(
    tmp_path, monkeypatch, cloud, absolute_outputs
):
    """Use this test to recover real 2D training outputs without the original workspace."""
    import mlflow
    import torch
    from omegaconf import OmegaConf

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    root = tmp_path / "work"
    root.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    checkpoint = (
        external / "weights/native.custom"
        if absolute_outputs
        else root / "weights/native.custom"
    )
    database = (
        external / "tracking.database"
        if absolute_outputs
        else root / "tracking.database"
    )
    checkpoint_relative = (
        Path("external") / checkpoint.relative_to("/")
        if absolute_outputs
        else checkpoint.relative_to(root)
    )
    database_relative = (
        Path("external") / database.relative_to("/")
        if absolute_outputs
        else database.relative_to(root)
    )
    monkeypatch.chdir(root)
    monkeypatch.setenv("MLFLOW_ENABLE_ARTIFACTS_PROGRESS_BAR", "false")
    configuration = {
        "defaults": [
            {"train": "train_schema"},
            {"train/optim": "sgd_schema"},
            {"model": "model_schema"},
            {"tracking": "tracking_schema"},
            "_self_",
        ],
        "model": {
            "architecture": {
                "source": "local",
                "id": "durability-test",
                "location": "torch.nn.Conv2d",
                "kwargs": {"in_channels": 1, "out_channels": 1, "kernel_size": 1},
            }
        },
        "train": {
            "epochs": 1,
            "device": "cpu",
            "task": "generic",
            "loss_mode": "prediction",
            "best_model_path": str(checkpoint)
            if absolute_outputs
            else "weights/native.custom",
            "loss_fn": {"_target_": "torch.nn.MSELoss"},
            "dataloader": {
                "_target_": "torch.utils.data.DataLoader",
                "_convert_": "all",
                "batch_size": 1,
                "dataset": {
                    "_target_": "torch.utils.data.TensorDataset",
                    "_args_": [
                        {"_target_": "torch.ones", "size": [2, 1, 4, 4]},
                        {"_target_": "torch.zeros", "size": [2, 1, 4, 4]},
                    ],
                },
            },
        },
        "tracking": {
            "tracking_uri": f"sqlite:///{database}"
            if absolute_outputs
            else "sqlite:///tracking.database",
            "experiment_name": "durability-test",
        },
    }
    OmegaConf.save(OmegaConf.create(configuration), config_dir / "selected.yaml")
    previous_tracking = mlflow.get_tracking_uri()
    torch.manual_seed(0)
    original_weights = torch.nn.Conv2d(1, 1, 1).weight.detach().clone()
    torch.manual_seed(0)
    try:
        outputs.train(str(config_dir), "selected", str(root))
        weights = torch.load(checkpoint, weights_only=True)
        assert not torch.equal(weights["weight"], original_weights)
        outputs.finish_outputs(
            str(root),
            f"{TEST_BUCKET}/instances/123/trained",
            0,
        )
    finally:
        mlflow.set_tracking_uri(previous_tracking)
    monkeypatch.chdir(tmp_path)
    shutil.rmtree(root)
    shutil.rmtree(external)
    restored = tmp_path / "restored"
    restored.mkdir()
    contents, _, _ = cloud
    for name, data in contents.items():
        path = restored / name.removeprefix("instances/123/trained/")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    history = json.loads((restored / "history.json").read_text())
    assert history["train_loss"]
    assert (restored / "resolved-config.yaml").is_file()
    assert (restored / checkpoint_relative).is_file()
    with sqlite3.connect(restored / database_relative) as connection:
        assert connection.execute("select count(*) from metrics").fetchone()[0] > 0
        assert (
            connection.execute("select count(*) from model_versions").fetchone()[0] == 1
        )
    record = json.loads((restored / "mlflow-export/run.json").read_text())
    assert record["info"]["status"] == "FINISHED"
    assert record["metric_history"]["train_loss"][-1]["value"] == pytest.approx(
        history["train_loss"][-1]
    )
    model_dir = next((restored / "mlflow-export/models").rglob("MLmodel")).parent
    model = mlflow.pytorch.load_model(str(model_dir), map_location="cpu")
    restored_weights = torch.load(restored / checkpoint_relative, weights_only=True)
    for name, value in model.state_dict().items():
        torch.testing.assert_close(value, restored_weights[name])
    assert torch.isfinite(model(torch.ones(1, 1, 4, 4))).all()


def test_failed_checkpoint_save_preserves_previous_weights(tmp_path, monkeypatch):
    """Use this test to protect the last complete checkpoint against a failed save."""
    import torch

    from sightkit_learn.training.trainer import Trainer

    checkpoint = tmp_path / "weights.custom"
    checkpoint.write_bytes(b"previous complete checkpoint")
    trainer = Trainer.__new__(Trainer)
    trainer.best_model_path = checkpoint
    trainer.model = torch.nn.Conv2d(1, 1, 1)

    def interrupted_save(state, path):
        """Use this function to reproduce a disk-full failure after partial writes."""
        Path(path).write_bytes(b"incomplete checkpoint")
        raise OSError("disk full")

    save = create_autospec(torch.save, side_effect=interrupted_save)
    monkeypatch.setattr(torch, "save", save)
    with pytest.raises(OSError, match="disk full"):
        trainer._save_best()
    assert checkpoint.read_bytes() == b"previous complete checkpoint"
    assert list(tmp_path.iterdir()) == [checkpoint]


@pytest.mark.parametrize("transient_failure", [False, True])
def test_periodic_export_updates_cloud_logs_and_recovers_from_upload_failure(
    tmp_path, monkeypatch, cloud, transient_failure
):
    """Use this test to verify successive exports without waiting for real timers."""
    log = tmp_path / "console.log"
    log.write_text("initial log\n")
    contents, _, _ = cloud
    real_upload = outputs.upload_file
    attempts = 0

    def upload(bucket, name, path):
        """Use this function to inject one recoverable transport failure."""
        nonlocal attempts
        attempts += 1
        if transient_failure and attempts == 1:
            raise ServiceUnavailable("temporary transport failure")
        return real_upload(bucket, name, path)

    monkeypatch.setattr(outputs, "upload_file", upload)
    waits = 0

    def next_interval(seconds):
        """Use this function to advance log contents between export intervals."""
        nonlocal waits
        assert seconds == 30
        waits += 1
        if waits == 1:
            if not transient_failure:
                assert contents["instances/123/live/console.log"] == b"initial log\n"
            log.write_text("initial log\nlater stderr\n")
        else:
            raise StopIteration

    monkeypatch.setattr(outputs.time, "sleep", next_interval)
    with pytest.raises(StopIteration):
        outputs.watch_outputs(
            str(tmp_path),
            f"{TEST_BUCKET}/instances/123/live",
        )
    assert attempts == 2
    assert contents["instances/123/live/console.log"] == b"initial log\nlater stderr\n"
    assert not any(name.endswith("output-status.json") for name in contents)
