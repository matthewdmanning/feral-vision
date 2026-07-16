"""Paired image / annotation datasets backed by a :class:`~feral_vision.io_utils.DatasetSource`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Iterator

import torch
from torch.utils.data import Dataset, IterableDataset, get_worker_info

if TYPE_CHECKING:
    from feral_vision.io_utils import DatasetSource


class AnnotationDataset(Dataset[tuple[torch.Tensor, Any]]):
    """Map-style dataset for on-disk image / annotation pairs.

    Delegates all filesystem scanning and disk I/O to the injected
    :class:`~feral_vision.io_utils.DatasetSource`. Pass a
    ``target_transform`` to convert annotations to tensors eagerly on each
    ``__getitem__`` call, or omit it to receive raw
    :class:`~feral_vision.data.annotations.Annotation` objects for lazy
    downstream conversion.

    Parameters
    ----------
    source : DatasetSource
        Scanned and indexed data source that owns all file I/O.
    transform : callable, optional
        Applied to the image tensor after loading.
    target_transform : callable, optional
        Applied to the ``list[Annotation]`` after loading.
    """

    def __init__(
        self,
        source: DatasetSource,
        transform: Callable | None = None,
        target_transform: Callable | None = None,
    ) -> None:
        self.source = source
        self.transform = transform
        self.target_transform = target_transform

    def __len__(self) -> int:
        """Return the number of samples in the dataset.

        Returns
        -------
        int
            Total number of image / annotation pairs.
        """
        return len(self.source)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, Any]:
        """Return the image and annotation(s) for a single sample.

        Parameters
        ----------
        index : int
            Sample index.

        Returns
        -------
        tuple[torch.Tensor, Any]
            ``(image, annotations)`` where image is ``(C, H, W)`` uint8.
            ``annotations`` is a ``list[Annotation]`` when no
            ``target_transform`` is set, or the transform's output otherwise.
        """
        image, annotations = self.source.load(index)

        if self.transform is not None:
            image = self.transform(image)
        if self.target_transform is not None:
            annotations = self.target_transform(annotations)

        return image, annotations


class StreamingAnnotationDataset(IterableDataset[tuple[torch.Tensor, Any]]):
    """Iterable dataset for streaming image / annotation pairs.

    Functionally equivalent to :class:`AnnotationDataset` but implements
    ``__iter__`` for use as a streaming source. Workload is automatically
    partitioned across DataLoader workers via
    :func:`~torch.utils.data.get_worker_info` using
    :meth:`~feral_vision.io_utils.DatasetSource.partition`.

    Parameters
    ----------
    source : DatasetSource
        Scanned and indexed data source that owns all file I/O.
    transform : callable, optional
        Applied to each image tensor after loading.
    target_transform : callable, optional
        Applied to each ``list[Annotation]`` after loading.
    """

    def __init__(
        self,
        source: DatasetSource,
        transform: Callable | None = None,
        target_transform: Callable | None = None,
    ) -> None:
        self.source = source
        self.transform = transform
        self.target_transform = target_transform

    def __iter__(self) -> Iterator[tuple[torch.Tensor, Any]]:
        """Yield image / annotation pairs for this worker's partition.

        Returns
        -------
        Iterator[tuple[torch.Tensor, Any]]
            Yields ``(image, annotations)`` pairs. Each DataLoader worker
            receives a contiguous slice of the full sample index.
        """
        worker_info = get_worker_info()
        source = (
            self.source.partition(worker_info.id, worker_info.num_workers)
            if worker_info is not None
            else self.source
        )

        for i in range(len(source)):
            image, annotations = source.load(i)

            if self.transform is not None:
                image = self.transform(image)
            if self.target_transform is not None:
                annotations = self.target_transform(annotations)

            yield image, annotations
