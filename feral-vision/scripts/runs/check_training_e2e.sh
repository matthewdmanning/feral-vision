#!/usr/bin/env bash
# Run inside the exact cached deployment image, offline, with GPU access.
set -euo pipefail
python - <<'PY'
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

from hydra import compose, initialize_config_dir
from mlflow import MlflowClient
from PIL import Image
import torch
from sightkit_learn.config.store import register_configs
from sightkit_learn.training.trainer import build_dataloader

assert torch.cuda.is_available(), "E2E requires GPU access; CPU substitution is not allowed"
assert "sm_75" in torch.cuda.get_arch_list(), "Deployment image lacks T4 CUDA kernels"
register_configs()
with tempfile.TemporaryDirectory(prefix="training-e2e-") as directory:
    root = Path(directory)
    dataset = root / "dataset"
    (dataset / "images").mkdir(parents=True)
    (dataset / "annotations").mkdir()
    tracking_uri = f"sqlite:///{root / 'mlflow.db'}"
    with initialize_config_dir(version_base=None, config_dir="/workspace/feral-vision/conf"):
        cfg = compose(config_name="runs/detection", overrides=[
            f"data.root={dataset}", f"tracking.tracking_uri={tracking_uri}",
        ])
    side = int(cfg.data.image_size)
    images = []
    annotations = []
    for index in range(cfg.train.batch_size):
        name = f"sample-{index}.png"
        Image.new("RGB", (side, side), (40 + (index % 2) * 80, 120, 180)).save(dataset / "images" / name)
        images.append({"id": index, "file_name": name, "width": side, "height": side})
        annotations.append({"id": index, "image_id": index, "category_id": (index % 2) + 1, "bbox": [side // 8, side // 8, side // 2, side // 2], "area": (side // 2)**2, "iscrowd": 0})
    (dataset / "annotations/instances.json").write_text(json.dumps({
        "images": images, "annotations": annotations,
        "categories": [{"id": 1, "name": "cat"}, {"id": 2, "name": "dog"}],
    }))
    manifest = dataset / "dataset-artifact.json"
    manifest.write_text(json.dumps({"source": "local-e2e", "image_count": cfg.train.batch_size}))
    # Check the staged input contract before any model construction or retrieval.
    loader = build_dataloader(cfg)
    next(iter(loader))
    if cfg.model.architecture.source == "ultralytics":
        from ultralytics.utils import SETTINGS

        weights = Path(cfg.model.architecture.id)
        assert any(path.is_file() for path in [weights, Path(SETTINGS["weights_dir"]) / weights.name]), (
            "Reviewed model weights are not cached; stage them once explicitly. Downloads are disabled."
        )
    env = os.environ | {
        "TRAIN_DATA": str(dataset),
        "DATASET_ARTIFACT_MANIFEST": str(manifest),
        "DATASET_ARTIFACT_SHA256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "MLFLOW_TRACKING_URI": tracking_uri,
    }
    subprocess.run(["bash", "/workspace/feral-vision/scripts/runs/container_train.sh"], env=env, check=True)
    checkpoint = Path(cfg.train.best_model_path)
    assert checkpoint.is_file() and checkpoint.stat().st_size > 0, "No training checkpoint"
    client = MlflowClient(tracking_uri=tracking_uri)
    experiment = client.get_experiment_by_name(cfg.tracking.experiment_name)
    assert experiment is not None, "No tracked experiment"
    runs = client.search_runs([experiment.experiment_id])
    assert len(runs) == 1 and runs[0].info.status == "FINISHED", "Training did not finish"
    losses = client.get_metric_history(runs[0].info.run_id, "train_loss")
    assert len(losses) == cfg.train.epochs and all(math.isfinite(item.value) for item in losses), "Missing or nonfinite epoch losses"
    print("PASS: deployed entrypoint, COCO input, CUDA training, checkpoint, and MLflow run")
PY
