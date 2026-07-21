"""Contracts for the cloud-training container entrypoint."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONTAINER_TRAIN = REPOSITORY_ROOT / "scripts" / "container_train.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o755)


def test_container_training_persists_mlflow_backend_store_to_gcs(tmp_path):
    """A completed container run preserves MLflow metadata beyond the SSD."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    call_log = tmp_path / "gcloud.log"
    data_dir = tmp_path / "data"

    _write_executable(
        bin_dir / "gcloud",
        "#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> \"${CALL_LOG}\"\n",
    )
    python_log = tmp_path / "python.log"
    _write_executable(
        bin_dir / "python",
        "#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >> \"${PYTHON_LOG}\"\n",
    )
    _write_executable(
        bin_dir / "mlflow",
        "#!/usr/bin/env bash\n"
        "mkdir -p \"${DATA_DIR}/mlflow\"\n"
        ": > \"${DATA_DIR}/mlflow/mlflow.db\"\n"
        "trap 'exit 0' TERM\n"
        "while true; do /bin/sleep 1; done\n",
    )

    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "CALL_LOG": str(call_log),
        "PYTHON_LOG": str(python_log),
        "DATA_DIR": str(data_dir),
        "GCS_BUCKET": "feral-training",
        "GCS_DATA_PREFIX": "inputs/baseline",
        "MLFLOW_ARTIFACT_PREFIX": "runs/baseline",
        "MLFLOW_STARTUP_DELAY_SECONDS": "0",
    }

    subprocess.run(
        ["bash", str(CONTAINER_TRAIN)],
        check=True,
        cwd=REPOSITORY_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    calls = call_log.read_text().splitlines()
    assert (
        f"storage rsync -r {data_dir}/mlflow/ "
        "gs://feral-training/runs/baseline/tracking/"
    ) in calls
    assert (
        f"-m feral_vision.training.trainer --config-name runs/baseline "
        f"data.root={data_dir} tracking.tracking_uri=http://localhost:5000"
    ) in python_log.read_text().splitlines()
