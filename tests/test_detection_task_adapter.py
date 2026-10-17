"""Detection task batches preserve YOLO labels and delegate native assignment safely."""

from __future__ import annotations

# stdlib
from functools import partial
from pathlib import Path
from unittest.mock import create_autospec

# third-party
import pytest
import torch
from omegaconf import OmegaConf
from torch.utils.data import DataLoader
from ultralytics.cfg import get_cfg
from ultralytics.nn.tasks import DetectionModel
from ultralytics.utils.loss import v8DetectionLoss

# project
from feral_vision.data.annotations import BBoxAnnotation
from feral_vision.training.detection import collate_detection, detection_loss
from feral_vision.training.task_adapters.detection import DetectionTaskAdapter
from feral_vision.training.trainer import Trainer


# ---------------------------------------------------------------------------
# Helpers / local fixtures
# ---------------------------------------------------------------------------


def _annotation(class_ids: list[int], boxes: list[list[float]]) -> BBoxAnnotation:
    """Build an in-memory YOLO annotation for a two-dimensional image sample."""
    return BBoxAnnotation(
        path=Path("sample.txt"),
        class_ids=torch.tensor(class_ids).numpy(),
        boxes=torch.tensor(boxes, dtype=torch.float32).numpy(),
    )


@pytest.fixture
def native_detector() -> DetectionModel:
    """Build a tiny local Ultralytics detector with its real assignment and loss APIs."""
    cfg = {
        "nc": 2,
        "backbone": [[-1, 1, "Conv", [8, 3, 2]], [-1, 1, "Conv", [16, 3, 2]]],
        "head": [[[1], 1, "Detect", [2]]],
    }
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(0)
        model = DetectionModel(cfg=cfg, nc=2, verbose=False)
    model.args = get_cfg()
    return model


# ---------------------------------------------------------------------------
# DetectionTaskAdapter — batch and loss contracts
# ---------------------------------------------------------------------------


def test_collate_keeps_variable_box_counts_and_normalized_images() -> None:
    """One detection batch retains every class-labelled box without padding targets."""
    adapter = DetectionTaskAdapter(num_classes=10)

    batch = adapter.collate(
        [
            (
                torch.zeros(3, 8, 8, dtype=torch.uint8),
                [_annotation([1], [[0.5, 0.5, 0.4, 0.4]])],
            ),
            (
                torch.full((3, 8, 8), 255, dtype=torch.uint8),
                [_annotation([2, 3], [[0.2, 0.2, 0.1, 0.1], [0.8, 0.8, 0.1, 0.1]])],
            ),
        ]
    )

    assert batch.images.shape == (2, 3, 8, 8)
    assert batch.batch_idx.tolist() == [0, 1, 1]
    assert batch.class_ids.tolist() == [1, 2, 3]
    assert batch.boxes.shape == (3, 4)


def test_collate_rejects_class_ids_outside_the_selected_taxonomy() -> None:
    """The two-class recipe contract rejects label drift before native assignment."""
    adapter = DetectionTaskAdapter(num_classes=2)

    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        adapter.collate(
            [
                (
                    torch.zeros(3, 8, 8, dtype=torch.uint8),
                    [_annotation([2], [[0.5, 0.5, 0.4, 0.4]])],
                )
            ]
        )


def test_loss_reuses_native_assignment_and_trains_with_classification_plus_giou(
    native_detector, monkeypatch
) -> None:
    """Real native assignment supplies differentiable classification and box supervision."""
    adapter = DetectionTaskAdapter(num_classes=2)
    criterion = native_detector.init_criterion()
    assert isinstance(criterion, v8DetectionLoss)
    native_detector.criterion = criterion
    native_assignment = criterion.get_assigned_targets_and_loss
    assign = create_autospec(
        native_assignment,
        side_effect=native_assignment,
    )
    monkeypatch.setattr(criterion, "get_assigned_targets_and_loss", assign)
    batch = adapter.collate(
        [
            (
                torch.full((3, 32, 32), 255, dtype=torch.uint8),
                [_annotation([label], [[0.5, 0.5, 0.4, 0.4]])],
            )
            for label in (0, 1)
        ]
    )

    loss, metrics = adapter.loss(native_detector, batch)
    loss.backward()

    assign.assert_called_once()
    _, native_terms, _ = native_assignment(*assign.call_args.args)
    torch.testing.assert_close(metrics["classification_loss"], native_terms[1].detach())
    native_images = assign.call_args.args[1]["img"]
    torch.testing.assert_close(native_images, torch.ones(2, 3, 32, 32))
    assert set(metrics) == {"classification_loss", "giou_loss"}
    assert all(torch.isfinite(value) and value > 0 for value in metrics.values())
    assert all(not value.requires_grad for value in metrics.values())
    torch.testing.assert_close(loss.detach(), 2 * sum(metrics.values()))
    gradients = [p.grad for p in native_detector.parameters() if p.grad is not None]
    assert gradients
    assert all(torch.isfinite(gradient).all() for gradient in gradients)
    assert any(torch.count_nonzero(gradient) for gradient in gradients)


def test_shared_training_loop_updates_native_detector_and_records_components(
    native_detector, tmp_path
) -> None:
    """The callable loss path trains a real detector and retains named loss history."""
    samples = [
        (
            torch.full((3, 32, 32), 255, dtype=torch.uint8),
            [_annotation([label], [[0.5, 0.5, 0.4, 0.4]])],
        )
        for label in (0, 1)
    ]
    dataloader = DataLoader(
        samples, batch_size=2, collate_fn=partial(collate_detection, num_classes=2)
    )
    before = [parameter.detach().clone() for parameter in native_detector.parameters()]
    trainer = Trainer(
        native_detector,
        torch.optim.SGD(native_detector.parameters(), lr=0.01),
        cfg=OmegaConf.create({"train": {"epochs": 1}}),
        compute_loss=detection_loss,
        best_model_path=tmp_path / "detector.pt",
    )

    history = trainer.fit(dataloader)

    assert history["train_loss"][0] == pytest.approx(
        2 * (history["classification_loss"][0] + history["giou_loss"][0])
    )
    assert history["best_loss"] == history["train_loss"][0]
    assert trainer.best_model_path.is_file()
    assert any(
        not torch.equal(old, new)
        for old, new in zip(before, native_detector.parameters())
    )
