"""YOLO11n-seg training entrypoint via Hydra + ultralytics Python API."""

from __future__ import annotations

import importlib
import tempfile
from pathlib import Path
from typing import Callable

import hydra
import yaml
from omegaconf import DictConfig

from feral_segmentor.config.store import register_configs
from feral_segmentor.utils import get_logger

logger = get_logger(__name__)


def _resolve_callable(dotted: str) -> Callable | None:
    """Import and return a callable from a dotted module path, or None if "none"."""
    if dotted == "none":
        return None
    module_path, _, attr = dotted.rpartition(".")
    if not module_path:
        raise ValueError(f"similarity callable must be a dotted path, got: {dotted!r}")
    module = importlib.import_module(module_path)
    return getattr(module, attr)


def _write_data_yaml(cfg: DictConfig, data_dir: str | Path) -> Path:
    """Generate a YOLO data.yaml from Hydra DataConfig and return its path."""
    data_dir = Path(data_dir)
    names_path = data_dir / "labels" / "names.yaml"

    # Load class names written by coco_to_yolo --names.
    if names_path.exists():
        with names_path.open() as f:
            names_data = yaml.safe_load(f)
        names = list(names_data.get("names", {}).values())
    else:
        # Fallback: generic class names based on similarity list length.
        n = len(cfg.data.class_similarity) or cfg.model.num_classes
        names = [f"class{i}" for i in range(n)]
        logger.warning(
            "names.yaml not found at %s; using generic class names", names_path
        )

    payload = {
        "path": str(data_dir),
        "train": "images/train",
        "val": "images/val",
        "nc": len(names),
        "names": names,
    }

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, prefix="feral_data_"
    )
    yaml.dump(payload, tmp)
    tmp.flush()
    logger.info("wrote data.yaml to %s", tmp.name)
    return Path(tmp.name)


@hydra.main(version_base=None, config_path="../../../conf", config_name="config")
def main(cfg: DictConfig) -> None:
    from ultralytics import YOLO

    data_dir = cfg.get("train", {}).get("data_dir", "/data")
    data_yaml = _write_data_yaml(cfg, data_dir)

    # Resolve similarity callables if requested.
    similarity_loss_fn = None
    similarity_sampler_fn = None
    if cfg.train.use_similarity:
        similarity_loss_fn = _resolve_callable(cfg.train.similarity_loss)
        similarity_sampler_fn = _resolve_callable(cfg.train.similarity_sampler)
        logger.info(
            "similarity weighting active — loss: %s, sampler: %s",
            cfg.train.similarity_loss,
            cfg.train.similarity_sampler,
        )
        if similarity_loss_fn is not None:
            similarity_loss_fn = similarity_loss_fn(
                class_similarity=list(cfg.data.class_similarity)
            )
        if similarity_sampler_fn is not None:
            similarity_sampler_fn = similarity_sampler_fn(
                class_similarity=list(cfg.data.class_similarity)
            )

    model = YOLO(cfg.model.architecture.id)
    model.train(
        data=str(data_yaml),
        epochs=cfg.train.epochs,
        imgsz=cfg.data.image_size,
        batch=cfg.train.batch_size,
        lr0=cfg.train.lr,
        weight_decay=cfg.train.weight_decay,
        momentum=cfg.train.momentum,
        workers=cfg.train.num_workers,
        project=str(Path(data_dir) / "runs"),
        name="feral_seg",
        exist_ok=True,
        # Loss/sampler injection points — extend here when callables are implemented.
        # criterion=similarity_loss_fn,  # uncomment when custom loss is ready
    )
    logger.info("training complete. results in %s/runs/feral_seg/", data_dir)


if __name__ == "__main__":
    register_configs()
    main()
