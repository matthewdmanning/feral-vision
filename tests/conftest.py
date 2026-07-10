from pathlib import Path
from unittest.mock import MagicMock

import cv2
import numpy as np
import pytest
import torch
import torch.nn as nn

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
    """Path to the 8-sample test dataset (images/ + annotations/ subdirs)."""
    return FIXTURES_DIR


@pytest.fixture
def fixture_dataset():
    """AnnotationDataset over the 8 committed fixture samples."""
    from feral_segmentor.data.dataset import AnnotationDataset
    from feral_segmentor.io_utils import DatasetSource

    return AnnotationDataset(DatasetSource(FIXTURES_DIR))


@pytest.fixture
def synthetic_bgr_image():
    """Random uint8 BGR image — no disk dependency."""
    rng = np.random.default_rng(0)
    return rng.integers(0, 256, (256, 256, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# Tensor fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def image_tensor():
    """Single CHW float32 image tensor."""
    return torch.rand(3, 256, 256)


@pytest.fixture
def batch_image_tensor():
    """BCHW float32 batch."""
    return torch.rand(2, 3, 256, 256)


@pytest.fixture
def mask_tensor():
    """Single HW int64 segmentation mask."""
    return torch.randint(0, 2, (256, 256))


@pytest.fixture
def batch_mask_tensor():
    """BHW int64 batch of masks."""
    return torch.randint(0, 2, (2, 256, 256))


@pytest.fixture
def logits_tensor():
    """BCHW float32 logits matching batch/class/spatial defaults."""
    return torch.randn(2, 2, 256, 256)


# ---------------------------------------------------------------------------
# DataLoader fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def tiny_dataloader():
    """In-memory DataLoader with 4 synthetic (image, mask) batches."""
    data = [
        (
            torch.rand(2, 3, 256, 256),
            torch.randint(0, 2, (2, 256, 256)),
        )
        for _ in range(4)
    ]
    return data


# ---------------------------------------------------------------------------
# Mock model fixtures
# ---------------------------------------------------------------------------


class _MinimalSegmenter(nn.Module):
    """Deterministic stand-in: returns zero logits of correct shape."""

    def __init__(self, num_classes: int = 2):
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
    teacher.return_value = torch.zeros(2, 2, 256, 256)
    return teacher


# ---------------------------------------------------------------------------
# Bounding-box model fixtures
# ---------------------------------------------------------------------------


def make_bbox_test_net(
    in_channels: int = 3,
    num_boxes: int = 1,
    box_format: str = "cxcywh",
) -> nn.Module:
    """Build a minimal bbox-regression network for use as a real model in tests.

    Parameters
    ----------
    in_channels : int
        Number of input image channels (3 for RGB).
    num_boxes : int
        Number of boxes predicted per image.
    box_format : {"cxcywh", "xyxy"}
        Encoding of the raw (unconstrained, unnormalised) output coordinates.

    Returns
    -------
    nn.Module
        Network mapping ``(B, in_channels, H, W)`` to ``(B, num_boxes, 4)``.

    Raises
    ------
    ValueError
        If ``box_format`` is not ``"cxcywh"`` or ``"xyxy"``.
    """
    if box_format not in ("cxcywh", "xyxy"):
        raise ValueError(f"box_format must be 'cxcywh' or 'xyxy', got {box_format!r}")

    class _BBoxRegressionNet(nn.Module):
        """Tiny conv + global-pool + linear head producing raw box coordinates."""

        def __init__(self, c_in: int, k: int, fmt: str) -> None:
            super().__init__()
            self.num_boxes = k
            self.box_format = fmt
            self.feat = nn.Sequential(
                nn.Conv2d(c_in, 16, kernel_size=3, padding=1),
                nn.ReLU(inplace=True),
                nn.AdaptiveAvgPool2d((1, 1)),
            )
            self.head = nn.Linear(16, k * 4)

        def forward(self, x: torch.Tensor) -> torch.Tensor:
            z = self.feat(x).flatten(1)
            return self.head(z).view(-1, self.num_boxes, 4)

    return _BBoxRegressionNet(in_channels, num_boxes, box_format)


@pytest.fixture
def bbox_test_net_factory():
    """Factory fixture returning make_bbox_test_net for per-test box-count/format control."""
    return make_bbox_test_net


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
        mask_logits=torch.randn(2, 256, 256),
        boxes=torch.tensor([[4.0, 4.0, 12.0, 12.0]]),
        scores=torch.tensor([0.9]),
        labels=torch.tensor([1], dtype=torch.long),
    )
