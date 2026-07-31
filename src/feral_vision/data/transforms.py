"""Image preprocessing: cv2 BGR image -> normalized CHW float tensor."""

from __future__ import annotations

import cv2
import numpy as np
import torch


# uint8 images span [0, 255]; divide by this to scale into [0, 1].
_UINT8_MAX: float = 255.0


def preprocess(image: np.ndarray, size: int = 256) -> torch.Tensor:
    """Convert a cv2-loaded image into a model-ready tensor.

    Steps: convert BGR(A)/grayscale to 3-channel RGB, resize to
    ``(size, size)``, scale to ``[0, 1]`` float32, and return as a CHW tensor.

    Parameters
    ----------
    image:
        An image as loaded by ``cv2.imread`` — ``(H, W)`` grayscale,
        ``(H, W, 3)`` BGR, or ``(H, W, 4)`` BGRA, dtype ``uint8``.
    size:
        Target square side length.

    Returns
    -------
    torch.Tensor
        A ``(3, size, size)`` float32 tensor with values in ``[0, 1]``.
    """
    if image.ndim == 2:
        # Grayscale -> RGB.
        rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    elif image.ndim == 3 and image.shape[2] == 4:
        # BGRA (alpha) -> RGB (drop alpha).
        rgb = cv2.cvtColor(image, cv2.COLOR_BGRA2RGB)
    elif image.ndim == 3 and image.shape[2] == 3:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    else:
        raise ValueError(f"unsupported image shape for preprocessing: {image.shape}")

    resized = cv2.resize(rgb, (size, size), interpolation=cv2.INTER_LINEAR)
    scaled = resized.astype(np.float32) / _UINT8_MAX
    # HWC -> CHW.
    tensor = torch.from_numpy(scaled).permute(2, 0, 1).contiguous()
    return tensor
