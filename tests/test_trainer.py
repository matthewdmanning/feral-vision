"""Integration tests for the dependency-injected Trainer training loop.

Uses real nn.Module/optimizer/scheduler instances throughout (no mocks). The
validation-metric tests use the real fixture-backed AnnotationDataset from
conftest.py (trainer_fixture_dataset) rather than a stand-in, to exercise
Trainer.fit's actual val_dataset contract end to end.
"""

from __future__ import annotations

import math
import json
from pathlib import Path
from types import SimpleNamespace

import mlflow
import pytest
import torch
import yaml
from omegaconf import DictConfig, OmegaConf
from torch import nn

from feral_vision.data.annotations import BBoxAnnotation
from feral_vision.training.optim import build_loss_fn, build_optimizer
from feral_vision.training.trainer import Trainer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cfg(epochs: int) -> SimpleNamespace:
    """Minimal Hydra-cfg stand-in exposing only cfg.train.epochs."""
    return SimpleNamespace(train=SimpleNamespace(epochs=epochs))


def _tiny_dataloader(
    n: int = 4, channels: int = 3, classes: int = 2, image_size: int = 8
):
    """List of 2D image batches usable as a real Iterable dataloader."""
    return [
        (
            torch.randn(2, channels, image_size, image_size),
            torch.randn(2, classes, image_size, image_size),
        )
        for _ in range(n)
    ]


def _trivial_loss(outputs, targets):
    return ((outputs - targets) ** 2).mean()


def _build_trainer(tmp_path: Path, epochs: int = 2) -> Trainer:
    model = nn.Conv2d(3, 2, kernel_size=1)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    return Trainer(
        model=model,
        optimizer=optimizer,
        loss_fn=_trivial_loss,
        cfg=_make_cfg(epochs),
        best_model_path=tmp_path / "best.pt",
    )


class _ValLenTrainer(Trainer):
    """Trainer whose _validate reports the real val_dataset's length as a metric."""

    def _validate(self, dataset) -> dict[str, float]:
        return {"val_len": float(len(dataset))}


class _BestModelTrainer(Trainer):
    """Produces a deliberately worse final epoch for artifact-selection tests."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._epoch = 0

    def _train_one_epoch(self, dataloader) -> float:
        self._input_example = torch.ones(2, 3, 8, 8)
        with torch.no_grad():
            self.model.weight.fill_(float(self._epoch + 1))
        self._epoch += 1
        return float(self._epoch)


# ---------------------------------------------------------------------------
# fit() — epoch loop and returned history
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("epochs", [1, 2, 5])
def test_fit_runs_and_returns_history_for_each_epoch(tmp_path, epochs):
    trainer = _build_trainer(tmp_path, epochs=epochs)

    history = trainer.fit(_tiny_dataloader())

    assert isinstance(history, dict)
    assert len(history["train_loss"]) == epochs
    assert all(math.isfinite(loss) for loss in history["train_loss"])
    assert math.isfinite(history["best_loss"])


def test_fit_best_loss_is_minimum_train_loss_when_no_validation(tmp_path):
    trainer = _build_trainer(tmp_path, epochs=5)

    history = trainer.fit(_tiny_dataloader())

    assert history["best_loss"] == min(history["train_loss"])


# ---------------------------------------------------------------------------
# fit() — best checkpoint persistence
# ---------------------------------------------------------------------------


def test_fit_writes_best_checkpoint(tmp_path):
    best_path = tmp_path / "best.pt"
    trainer = _build_trainer(tmp_path, epochs=1)

    trainer.fit(_tiny_dataloader())

    assert best_path.exists()
    state = torch.load(best_path)
    assert "weight" in state and "bias" in state


def test_fit_creates_nested_parent_dir_for_checkpoint(tmp_path):
    nested = tmp_path / "nested" / "registry" / "best.pt"
    model = nn.Conv2d(3, 2, kernel_size=1)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    trainer = Trainer(
        model=model,
        optimizer=optimizer,
        loss_fn=_trivial_loss,
        cfg=_make_cfg(1),
        best_model_path=nested,
    )

    trainer.fit(_tiny_dataloader())

    assert nested.exists()


def test_fit_tracks_metrics_and_best_checkpoint_in_configured_mlflow_run(tmp_path):
    """Logs a two-dimensional image model with MLflow's PyTorch flavor."""
    tracking_uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    mlflow.set_tracking_uri(tracking_uri)
    artifact_root = tmp_path / "artifacts"
    client = mlflow.tracking.MlflowClient(tracking_uri)
    experiment_id = client.create_experiment(
        "trainer-tests", artifact_location=artifact_root.as_uri()
    )
    data_root = tmp_path / "data"
    data_root.mkdir()
    data_tracker = data_root / "dvc.lock"
    data_tracker.write_text("outs:\n- md5: immutable-data-version\n")
    cfg = SimpleNamespace(
        train=SimpleNamespace(epochs=1),
        data=SimpleNamespace(root=str(data_root)),
        model=SimpleNamespace(architecture=SimpleNamespace(id="trainer-test-model")),
        tracking=SimpleNamespace(
            tracking_uri=tracking_uri,
            experiment_name="trainer-tests",
        ),
    )
    best_path = tmp_path / "best.pt"
    model = nn.Conv2d(3, 2, kernel_size=1)
    trainer = Trainer(
        model=model,
        optimizer=torch.optim.SGD(model.parameters(), lr=0.01),
        loss_fn=_trivial_loss,
        cfg=cfg,
        best_model_path=best_path,
    )

    dataloader = [(torch.randn(2, 3, 8, 8), torch.randn(2, 2, 8, 8))]
    trainer.fit(dataloader)

    mlmodel_files = list(artifact_root.rglob("MLmodel"))
    assert len(mlmodel_files) == 1
    model_metadata = yaml.safe_load(mlmodel_files[0].read_text())
    assert model_metadata["signature"] is not None
    assert model_metadata["saved_input_example_info"] is not None
    run = client.search_runs([experiment_id])[0]
    assert run.data.params["dvc_data_version"].startswith("dvc.lock@sha256:")
    logged_trackers = list(artifact_root.rglob("dvc.lock"))
    assert len(logged_trackers) == 1
    assert logged_trackers[0].read_text() == data_tracker.read_text()
    resolved_configs = list(artifact_root.rglob("resolved_config.json"))
    assert len(resolved_configs) == 1
    assert json.loads(resolved_configs[0].read_text()) == {
        "data": {"root": str(data_root)},
        "model": {"architecture": {"id": "trainer-test-model"}},
        "tracking": {
            "experiment_name": "trainer-tests",
            "tracking_uri": tracking_uri,
        },
        "train": {"epochs": 1},
    }
    model_versions = client.search_model_versions("name = 'trainer-test-model'")
    assert len(model_versions) == 1
    assert model_versions[0].run_id == run.info.run_id


def test_fit_logs_best_model_weights_not_final_epoch_weights(tmp_path):
    """MLflow stores only the selected best model artifact for a run."""
    tracking_uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    mlflow.set_tracking_uri(tracking_uri)
    artifact_root = tmp_path / "artifacts"
    client = mlflow.tracking.MlflowClient(tracking_uri)
    client.create_experiment(
        "best-model-tests", artifact_location=artifact_root.as_uri()
    )
    cfg = SimpleNamespace(
        train=SimpleNamespace(epochs=2),
        data=SimpleNamespace(root=str(tmp_path)),
        tracking=SimpleNamespace(
            tracking_uri=tracking_uri,
            experiment_name="best-model-tests",
        ),
    )
    model = nn.Conv2d(3, 1, kernel_size=1, bias=False)
    trainer = _BestModelTrainer(
        model=model,
        optimizer=torch.optim.SGD(model.parameters(), lr=0.01),
        loss_fn=_trivial_loss,
        cfg=cfg,
        best_model_path=tmp_path / "best.pt",
    )

    trainer.fit([])

    mlmodel_file = next(artifact_root.rglob("MLmodel"))
    logged_model = mlflow.pytorch.load_model(str(mlmodel_file.parent))
    input_example = torch.ones(2, 3, 8, 8)
    assert torch.allclose(logged_model(input_example), torch.full((2, 1, 8, 8), 3.0))
    assert torch.allclose(trainer.model(input_example), torch.full((2, 1, 8, 8), 6.0))


# ---------------------------------------------------------------------------
# fit() — scheduler stepping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("epochs,gamma", [(1, 0.5), (2, 0.5), (3, 0.1)])
def test_scheduler_steps_once_per_epoch(tmp_path, epochs, gamma):
    model = nn.Conv2d(3, 2, kernel_size=1)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.1)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=1, gamma=gamma)
    trainer = Trainer(
        model=model,
        optimizer=optimizer,
        loss_fn=_trivial_loss,
        cfg=_make_cfg(epochs),
        scheduler=scheduler,
        best_model_path=tmp_path / "best.pt",
    )

    trainer.fit(_tiny_dataloader())

    expected_lr = 0.1 * (gamma**epochs)
    assert math.isclose(optimizer.param_groups[0]["lr"], expected_lr, rel_tol=1e-6)


# ---------------------------------------------------------------------------
# fit() — real val_dataset integration
# ---------------------------------------------------------------------------


def test_base_validate_returns_empty_dict_and_falls_back_to_train_loss(
    tmp_path, trainer_fixture_dataset
):
    trainer = _build_trainer(tmp_path, epochs=3)

    history = trainer.fit(_tiny_dataloader(), val_dataset=trainer_fixture_dataset)

    assert set(history) == {"train_loss", "best_loss"}
    assert history["best_loss"] == min(history["train_loss"])


@pytest.mark.parametrize("epochs", [1, 3])
def test_validate_metric_is_tracked_per_epoch_using_real_dataset(
    tmp_path, trainer_fixture_dataset, epochs
):
    model = nn.Conv2d(3, 2, kernel_size=1)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    trainer = _ValLenTrainer(
        model=model,
        optimizer=optimizer,
        loss_fn=_trivial_loss,
        cfg=_make_cfg(epochs),
        best_model_path=tmp_path / "best.pt",
    )

    history = trainer.fit(_tiny_dataloader(), val_dataset=trainer_fixture_dataset)

    assert history["val_len"] == [float(len(trainer_fixture_dataset))] * epochs


def test_validate_metric_drives_checkpoint_selection_over_train_loss(
    tmp_path, trainer_fixture_dataset
):
    model = nn.Conv2d(3, 2, kernel_size=1)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    trainer = _ValLenTrainer(
        model=model,
        optimizer=optimizer,
        loss_fn=_trivial_loss,
        cfg=_make_cfg(1),
        best_model_path=tmp_path / "best.pt",
    )

    trainer.fit(_tiny_dataloader(), val_dataset=trainer_fixture_dataset)

    # tracked_loss comes from the metric (val_len), not train_loss.
    assert trainer.best_loss == float(len(trainer_fixture_dataset))


# ---------------------------------------------------------------------------
# fit() — bbox regression against real BBoxAnnotation-loaded targets
# ---------------------------------------------------------------------------


def _write_yolo_txt(
    path: Path, rows: list[tuple[int, float, float, float, float]]
) -> None:
    """Write a YOLO-format annotation file with one ``class x y w h`` row per line."""
    lines = [" ".join(str(v) for v in row) for row in rows]
    path.write_text("\n".join(lines))


def _make_bbox_train_cfg(
    batch_size: int = 2,
    optim_target: str = "torch.optim.Adam",
    lr: float = 0.05,
    loss_fn_target: str = "torch.nn.MSELoss",
) -> DictConfig:
    """cfg shaped like the real conf/train/base.yaml: epochs/batch_size plus
    optim/loss_fn sub-configs carrying ``_target_`` (and ``_partial_`` for
    optim), exactly as ``build_optimizer``/``build_loss_fn`` expect.

    ``epochs`` is pinned at 2, not parametrized — 2 is enough to exercise one
    full forward pass, backward pass, and optimizer step per batch; more
    epochs would only test convergence, not the loop mechanics under test
    here. ``_partial_: true`` on optim is likewise pinned, not parametrized —
    ``build_optimizer`` requires the deferred-factory form
    (``opt_factory(model.parameters())``); it is a structural requirement of
    the real config schema, not a value that varies between configs.
    """
    return OmegaConf.create(
        {
            "train": {
                "epochs": 2,
                "batch_size": batch_size,
                "optim": {
                    "_target_": optim_target,
                    "_partial_": True,
                    "lr": lr,
                },
                "loss_fn": {
                    "_target_": loss_fn_target,
                    "reduction": "mean",
                },
            }
        }
    )


def _bbox_dataloader(
    target_boxes: torch.Tensor,
    cfg: DictConfig,
    image_size: int,
    n_batches: int = 2,
):
    """Batches of (random RGB image, target_boxes repeated per-sample), batch size from cfg.train."""
    batch_size = cfg.train.batch_size
    targets = target_boxes.unsqueeze(0).expand(batch_size, -1, -1)
    return [
        (torch.randn(batch_size, 3, image_size, image_size), targets.clone())
        for _ in range(n_batches)
    ]


@pytest.mark.parametrize(
    "in_channels,num_boxes,box_format,image_size",
    [(3, 1, "cxcywh", 8), (3, 3, "xyxy", 16), (1, 2, "cxcywh", 20)],
)
def test_bbox_net_output_shape_matches_num_boxes(
    bbox_net_factory, in_channels, num_boxes, box_format, image_size
):
    """image_size varies per case to prove _BBoxNet's adaptive pooling is
    genuinely size-invariant, rather than assuming it from a fixed input."""
    cfg = _make_bbox_train_cfg()
    net = bbox_net_factory(
        in_channels=in_channels, num_boxes=num_boxes, box_format=box_format
    )

    out = net(torch.randn(cfg.train.batch_size, in_channels, image_size, image_size))

    assert out.shape == (cfg.train.batch_size, num_boxes, 4)
    assert out.dtype == torch.float32


@pytest.mark.parametrize("invalid_format", ["not_a_format", "", "CXCYWH"])
def test_bbox_net_factory_rejects_invalid_box_format(bbox_net_factory, invalid_format):
    with pytest.raises(ValueError, match="box_format"):
        bbox_net_factory(box_format=invalid_format)


@pytest.mark.parametrize(
    "box_format,batch_size,optim_target,loss_fn_target,rows",
    [
        (
            "cxcywh",
            2,
            "torch.optim.Adam",
            "torch.nn.MSELoss",
            [(0, 0.5, 0.5, 0.2, 0.2)],
        ),
        (
            "xyxy",
            3,
            "torch.optim.SGD",
            "torch.nn.L1Loss",
            [(0, 0.5, 0.5, 0.2, 0.2), (1, 0.25, 0.75, 0.1, 0.3)],
        ),
        (
            "cxcywh",
            4,
            "torch.optim.AdamW",
            "torch.nn.MSELoss",
            [
                (0, 0.1, 0.1, 0.05, 0.05),
                (1, 0.9, 0.9, 0.05, 0.05),
                (2, 0.5, 0.5, 0.3, 0.3),
            ],
        ),
    ],
)
def test_fit_trains_bbox_net_toward_real_annotation_boxes(
    tmp_path,
    bbox_net_factory,
    box_format,
    batch_size,
    optim_target,
    loss_fn_target,
    rows,
):
    cfg = _make_bbox_train_cfg(
        batch_size=batch_size, optim_target=optim_target, loss_fn_target=loss_fn_target
    )
    ann_path = tmp_path / "boxes.txt"
    _write_yolo_txt(ann_path, rows)
    target = torch.from_numpy(BBoxAnnotation(path=ann_path).load().boxes)

    model = bbox_net_factory(num_boxes=len(rows), box_format=box_format)
    optimizer = build_optimizer(model.parameters(), cfg.train.optim)
    loss_fn = build_loss_fn(cfg.train.loss_fn)
    trainer = Trainer(
        model=model,
        optimizer=optimizer,
        loss_fn=loss_fn,
        cfg=cfg,
        best_model_path=tmp_path / "best.pt",
    )
    params_before = [p.clone() for p in model.parameters()]

    history = trainer.fit(_bbox_dataloader(target, cfg, image_size=16))

    assert len(history["train_loss"]) == cfg.train.epochs
    assert all(math.isfinite(loss) for loss in history["train_loss"])
    # A real optimizer step actually ran against the real annotation-derived target.
    assert any(
        not torch.equal(before, after)
        for before, after in zip(params_before, model.parameters())
    )
