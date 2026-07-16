import functools
import logging
import time

import numpy as np

# Maps (source_dtype, target_dtype) to the scale factor applied before casting.
# Covers the standard uint8 ↔ float conversions used across training, augmentation,
# and inference. Unsupported pairs raise ValueError rather than silently casting.
_DTYPE_SCALE: dict[tuple[np.dtype, np.dtype], float] = {
    (np.dtype("uint8"), np.dtype("float32")): 1.0 / 255.0,
    (np.dtype("uint8"), np.dtype("float64")): 1.0 / 255.0,
    (np.dtype("float32"), np.dtype("uint8")): 255.0,
    (np.dtype("float64"), np.dtype("uint8")): 255.0,
    (np.dtype("float32"), np.dtype("float64")): 1.0,
    (np.dtype("float64"), np.dtype("float32")): 1.0,
}


def to_dtype(image: np.ndarray, target_dtype: "np.dtype | type") -> np.ndarray:
    """Convert image to target_dtype with automatic scale adjustment.

    Parameters
    ----------
    image : np.ndarray
        Input image array of any shape.
    target_dtype : np.dtype or type
        Desired output dtype (e.g. ``np.uint8``, ``np.float32``).

    Returns
    -------
    np.ndarray
        Image cast to ``target_dtype`` with pixel values rescaled to the
        target range (uint8 [0, 255] ↔ float [0.0, 1.0]).

    Raises
    ------
    ValueError
        If the (source, target) dtype pair is not in ``_DTYPE_SCALE``.

    Notes
    -----
    Scale factors are looked up from ``_DTYPE_SCALE`` rather than inferred,
    so unsupported conversions fail loudly instead of silently truncating values.
    Integer targets are clipped to their valid range before casting.
    """
    target = np.dtype(target_dtype)
    if image.dtype == target:
        return image
    key = (image.dtype, target)
    if key not in _DTYPE_SCALE:
        supported = [(str(s), str(t)) for s, t in _DTYPE_SCALE]
        raise ValueError(
            f"unsupported dtype conversion {image.dtype} → {target}; supported pairs: {supported}"
        )
    scaled = image.astype(np.float64) * _DTYPE_SCALE[key]
    if np.issubdtype(target, np.integer):
        info = np.iinfo(target)
        scaled = np.clip(scaled, info.min, info.max)
    return scaled.astype(target)


def get_logger(name: str) -> logging.Logger:
    logging.basicConfig(level=logging.INFO)
    return logging.getLogger(name)


def timing(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        get_logger(func.__module__).info("%s took %.4fs", func.__name__, elapsed)
        return result

    return wrapper
