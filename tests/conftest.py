from pathlib import Path
from unittest.mock import MagicMock

import cv2
import numpy as np
import pytest
import torch
import torch.nn as nn

from feral_segmentor.constants import (
    DEFAULT_IMAGE_SIZE,
    DEFAULT_IN_CHANNELS,
    DEFAULT_NUM_CLASSES,
)
from feral_segmentor.models.base import SegmentationOutput

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Image fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tiny_image():
    """Real BGR image loaded from the committed test fixtures."""
    path = FIXTURES_DIR / "american_bulldog_103_original.jpg"
    return cv2.imread(str(path), cv2.IMREAD_UNCHANGED)


@pytest.fixture
def fixture_dataset_root():
    """Path to the 8-sample test dataset (images/ + masks/ subdirs)."""
    return FIXTURES_DIR


@pytest.fixture
def fixture_dataset():
    """SegmentationDataset over the 8 committed fixture samples."""
    from feral_segmentor.data.dataset import SegmentationDataset

    return SegmentationDataset(str(FIXTURES_DIR))


@pytest.fixture
def synthetic_bgr_image():
    """Random uint8 BGR image — no disk dependency."""
    rng = np.random.default_rng(0)
    return rng.integers(
        0, 256, (DEFAULT_IMAGE_SIZE, DEFAULT_IMAGE_SIZE, 3), dtype=np.uint8
    )


# ---------------------------------------------------------------------------
# Tensor fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def image_tensor():
    """Single CHW float32 image tensor."""
    return torch.rand(DEFAULT_IN_CHANNELS, DEFAULT_IMAGE_SIZE, DEFAULT_IMAGE_SIZE)


@pytest.fixture
def batch_image_tensor():
    """BCHW float32 batch."""
    return torch.rand(2, DEFAULT_IN_CHANNELS, DEFAULT_IMAGE_SIZE, DEFAULT_IMAGE_SIZE)


@pytest.fixture
def mask_tensor():
    """Single HW int64 segmentation mask."""
    return torch.randint(
        0, DEFAULT_NUM_CLASSES, (DEFAULT_IMAGE_SIZE, DEFAULT_IMAGE_SIZE)
    )


@pytest.fixture
def batch_mask_tensor():
    """BHW int64 batch of masks."""
    return torch.randint(
        0, DEFAULT_NUM_CLASSES, (2, DEFAULT_IMAGE_SIZE, DEFAULT_IMAGE_SIZE)
    )


@pytest.fixture
def logits_tensor():
    """BCHW float32 logits matching batch/class/spatial defaults."""
    return torch.randn(2, DEFAULT_NUM_CLASSES, DEFAULT_IMAGE_SIZE, DEFAULT_IMAGE_SIZE)


# ---------------------------------------------------------------------------
# DataLoader fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def tiny_dataloader():
    """In-memory DataLoader with 4 synthetic (image, mask) batches."""
    data = [
        (
            torch.rand(2, DEFAULT_IN_CHANNELS, DEFAULT_IMAGE_SIZE, DEFAULT_IMAGE_SIZE),
            torch.randint(
                0, DEFAULT_NUM_CLASSES, (2, DEFAULT_IMAGE_SIZE, DEFAULT_IMAGE_SIZE)
            ),
        )
        for _ in range(4)
    ]
    return data


# ---------------------------------------------------------------------------
# Mock model fixtures
# ---------------------------------------------------------------------------


class _MinimalSegmenter(nn.Module):
    """Deterministic stand-in: returns zero logits of correct shape."""

    def __init__(self, num_classes: int = DEFAULT_NUM_CLASSES):
        super().__init__()
        self.num_classes = num_classes
        # one parameter so optimizers have something to update
        self._p = nn.Parameter(torch.zeros(1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, _, h, w = x.shape
        return self._p * torch.zeros(b, self.num_classes, h, w)

    def predict(self, image: torch.Tensor) -> SegmentationOutput:
        logits = self.forward(image.unsqueeze(0)).squeeze(0)
        return SegmentationOutput(
            mask_logits=logits,
            boxes=torch.zeros(0, 4),
            scores=torch.zeros(0),
            labels=torch.zeros(0, dtype=torch.long),
        )


@pytest.fixture
def mock_model():
    """Lightweight nn.Module with correct forward/predict signatures."""
    return _MinimalSegmenter()


@pytest.fixture
def mock_teacher():
    """MagicMock replacing TeacherModel — no YOLO download."""
    teacher = MagicMock(spec=nn.Module)
    teacher.return_value = torch.zeros(
        2, DEFAULT_NUM_CLASSES, DEFAULT_IMAGE_SIZE, DEFAULT_IMAGE_SIZE
    )
    return teacher


# ---------------------------------------------------------------------------
# Optimizer / scheduler fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_optimizer(mock_model):
    return torch.optim.SGD(mock_model.parameters(), lr=1e-3)


@pytest.fixture
def mock_scheduler(mock_optimizer):
    return torch.optim.lr_scheduler.StepLR(mock_optimizer, step_size=1, gamma=0.5)


# ---------------------------------------------------------------------------
# SegmentationOutput fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def dummy_output():
    return SegmentationOutput(
        mask_logits=torch.randn(
            DEFAULT_NUM_CLASSES, DEFAULT_IMAGE_SIZE, DEFAULT_IMAGE_SIZE
        ),
        boxes=torch.tensor([[4.0, 4.0, 12.0, 12.0]]),
        scores=torch.tensor([0.9]),
        labels=torch.tensor([1], dtype=torch.long),
    )
