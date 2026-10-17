"""Collation of already-prepared provider targets; retrieval remains upstream."""

from collections.abc import Mapping
from typing import Any

from torch.utils.data import default_collate


def collate_vision(samples):
    """Keep variable-sized images and per-image native detection targets as lists."""
    images, targets = zip(*samples)
    return list(images), list(targets)


def collate_huggingface(samples: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Stack prepared processor inputs while retaining ragged instance labels.

    Parameters
    ----------
    samples : list[Mapping[str, Any]]
        Processor-prepared images and labels, including padding when required.

    Returns
    -------
    dict[str, Any]
        Keyword batch for the selected Transformers task model.
    """
    batch = {}
    for key in samples[0]:
        values = [sample[key] for sample in samples]
        if key in {"class_labels", "mask_labels"} or (
            key == "labels" and isinstance(values[0], Mapping)
        ):
            batch[key] = values
        else:
            batch[key] = default_collate(values)
    return batch
