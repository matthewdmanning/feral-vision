import numpy as np
import pytest


@pytest.fixture
def tiny_image():
    """Synthetic 64x64 BGR image; no real files required."""
    rng = np.random.default_rng(0)
    return rng.integers(0, 256, (64, 64, 3), dtype=np.uint8)
