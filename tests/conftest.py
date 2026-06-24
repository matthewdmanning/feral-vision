import numpy as np
import pytest


@pytest.fixture
def tiny_image():
    rng = np.random.default_rng(0)
    return rng.integers(0, 256, (64, 64, 3), dtype=np.uint8)
