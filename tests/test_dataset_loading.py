"""Contract tests for DatasetSource and AnnotationDataset."""

from __future__ import annotations

import math

import numpy as np
import pytest
import torch

from feral_segmentor.data.annotations import MaskAnnotation
from feral_segmentor.data.dataset import AnnotationDataset, StreamingAnnotationDataset
from feral_segmentor.io_utils import DatasetSource


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MockSource:
    """In-memory stand-in for DatasetSource — no filesystem needed."""

    def __init__(self, n: int = 4, h: int = 8, w: int = 8):
        self._n = n
        self._h = h
        self._w = w

    def __len__(self) -> int:
        return self._n

    def load(self, index: int) -> tuple[torch.Tensor, list]:
        img = torch.full((3, self._h, self._w), index, dtype=torch.uint8)
        return img, []


def _write_sample_pair(root, stem, img_size=(32, 32)):
    """Write one image + mask pair under root/images/ and root/annotations/."""
    import cv2

    (root / "images").mkdir(exist_ok=True)
    (root / "annotations").mkdir(exist_ok=True)
    img = np.zeros((*img_size, 3), dtype=np.uint8)
    mask = np.zeros(img_size, dtype=np.uint8)
    cv2.imwrite(str(root / "images" / f"{stem}.jpg"), img)
    cv2.imwrite(str(root / "annotations" / f"{stem}.png"), mask)


# ---------------------------------------------------------------------------
# DatasetSource — indexing contract
# ---------------------------------------------------------------------------


def test_source_len_equals_paired_file_count(tmp_path):
    for i in range(3):
        _write_sample_pair(tmp_path, f"sample_{i}")
    source = DatasetSource(tmp_path)
    assert len(source) == 3


def test_source_load_returns_uint8_tensor(tmp_path):
    _write_sample_pair(tmp_path, "s0")
    img, _ = DatasetSource(tmp_path).load(0)
    assert img.dtype == torch.uint8


def test_source_load_image_shape_is_chw(tmp_path):
    _write_sample_pair(tmp_path, "s0", img_size=(16, 24))
    img, _ = DatasetSource(tmp_path).load(0)
    assert img.ndim == 3
    c, h, w = img.shape
    assert c == 3
    assert h == 16
    assert w == 24


def test_source_load_annotation_count_matches_annotation_files(tmp_path):
    _write_sample_pair(tmp_path, "s0")
    _, annotations = DatasetSource(tmp_path).load(0)
    assert len(annotations) == 1
    assert isinstance(annotations[0], MaskAnnotation)


def test_source_unmatched_image_raises(tmp_path):
    import cv2

    (tmp_path / "images").mkdir()
    (tmp_path / "annotations").mkdir()
    cv2.imwrite(
        str(tmp_path / "images" / "orphan.jpg"), np.zeros((8, 8, 3), dtype=np.uint8)
    )
    with pytest.raises(FileNotFoundError, match="orphan"):
        DatasetSource(tmp_path)


def test_source_missing_directory_raises(tmp_path):
    with pytest.raises((FileNotFoundError, NotADirectoryError)):
        DatasetSource(tmp_path / "nonexistent")


# ---------------------------------------------------------------------------
# DatasetSource — partition contract
# ---------------------------------------------------------------------------


def test_source_partition_returns_datasetsource_instance(tmp_path):
    _write_sample_pair(tmp_path, "s0")
    source = DatasetSource(tmp_path)
    assert isinstance(source.partition(0, 1), DatasetSource)


@pytest.mark.parametrize("n,num_workers", [(1, 1), (6, 2), (10, 3), (7, 4)])
def test_source_partition_lengths_sum_to_total(tmp_path, n, num_workers):
    for i in range(n):
        _write_sample_pair(tmp_path, f"s{i:02d}")
    source = DatasetSource(tmp_path)
    total = sum(len(source.partition(w, num_workers)) for w in range(num_workers))
    assert total == n


@pytest.mark.parametrize("n,num_workers", [(4, 2), (9, 3), (7, 4)])
def test_source_partition_slices_are_disjoint(tmp_path, n, num_workers):
    for i in range(n):
        _write_sample_pair(tmp_path, f"s{i:02d}")
    source = DatasetSource(tmp_path)
    path_sets = [
        {
            source.partition(w, num_workers)._index[j][0]
            for j in range(len(source.partition(w, num_workers)))
        }
        for w in range(num_workers)
    ]
    for i, a in enumerate(path_sets):
        for b in path_sets[i + 1 :]:
            assert a.isdisjoint(b)


def test_source_single_worker_gets_full_dataset(tmp_path):
    for i in range(5):
        _write_sample_pair(tmp_path, f"s{i}")
    source = DatasetSource(tmp_path)
    assert len(source.partition(0, 1)) == 5


@pytest.mark.parametrize("n,num_workers", [(10, 3), (7, 4)])
def test_source_partition_slices_are_contiguous_and_ordered(tmp_path, n, num_workers):
    for i in range(n):
        _write_sample_pair(tmp_path, f"s{i:02d}")
    source = DatasetSource(tmp_path)
    combined = []
    for w in range(num_workers):
        part = source.partition(w, num_workers)
        combined.extend(part._index[j][0] for j in range(len(part)))
    assert combined == [source._index[j][0] for j in range(len(source))]


def test_source_partition_is_loadable(tmp_path):
    for i in range(4):
        _write_sample_pair(tmp_path, f"s{i}")
    source = DatasetSource(tmp_path)
    part = source.partition(1, 2)
    img, annotations = part.load(0)
    assert img.dtype == torch.uint8
    assert img.ndim == 3 and img.shape[0] == 3


@pytest.mark.parametrize("n,num_workers", [(7, 2), (7, 4)])
def test_source_partition_first_worker_gets_ceil_items(tmp_path, n, num_workers):
    for i in range(n):
        _write_sample_pair(tmp_path, f"s{i}")
    source = DatasetSource(tmp_path)
    assert len(source.partition(0, num_workers)) == math.ceil(n / num_workers)


def test_source_partition_last_worker_gets_remainder_on_uneven_split(tmp_path):
    # ceil(7/3)=3 — workers get 3, 3, 1
    for i in range(7):
        _write_sample_pair(tmp_path, f"s{i}")
    source = DatasetSource(tmp_path)
    assert len(source.partition(2, 3)) == 1


def test_source_partition_excess_worker_gets_empty_slice(tmp_path):
    # ceil(3/5)=1 — workers 3 and 4 start past the end
    for i in range(3):
        _write_sample_pair(tmp_path, f"s{i}")
    source = DatasetSource(tmp_path)
    assert len(source.partition(4, 5)) == 0


# ---------------------------------------------------------------------------
# AnnotationDataset — contract with source
# ---------------------------------------------------------------------------


def test_dataset_len_delegates_to_source():
    ds = AnnotationDataset(_MockSource(n=7))
    assert len(ds) == 7


def test_dataset_getitem_returns_source_image():
    source = _MockSource(n=3)
    ds = AnnotationDataset(source)
    img, _ = ds[2]
    # MockSource fills pixel value = index, so index 2 → all pixels == 2
    assert img.shape == (3, 8, 8)
    assert img.unique().item() == 2


def test_dataset_target_transform_applied():
    ds = AnnotationDataset(_MockSource(), target_transform=lambda anns: "converted")
    _, result = ds[0]
    assert result == "converted"


def test_dataset_image_transform_applied():
    def transform(img):
        return img.float() / 255.0

    ds = AnnotationDataset(_MockSource(), transform=transform)
    img, _ = ds[0]
    assert img.dtype == torch.float32


def test_dataset_no_transform_returns_raw_annotations():
    ds = AnnotationDataset(_MockSource())
    _, annotations = ds[0]
    assert annotations == []


# ---------------------------------------------------------------------------
# StreamingAnnotationDataset — iteration contract
# ---------------------------------------------------------------------------


def test_streaming_dataset_yields_all_samples():
    source = _MockSource(n=5)
    ds = StreamingAnnotationDataset(source)
    samples = list(ds)
    assert len(samples) == 5


def test_streaming_dataset_applies_target_transform():
    ds = StreamingAnnotationDataset(_MockSource(n=3), target_transform=lambda a: "t")
    results = [target for _, target in ds]
    assert results == ["t", "t", "t"]


# ---------------------------------------------------------------------------
# Fixture-backed integration tests
# ---------------------------------------------------------------------------


def test_fixture_source_len(fixture_dataset_root):
    assert len(DatasetSource(fixture_dataset_root)) == 8


def test_fixture_dataset_all_images_load(fixture_dataset):
    for i in range(len(fixture_dataset)):
        img, _ = fixture_dataset[i]
        assert img.dtype == torch.uint8
        assert img.shape[0] == 3


def test_fixture_dataset_all_annotations_are_masks(fixture_dataset):
    for i in range(len(fixture_dataset)):
        _, annotations = fixture_dataset[i]
        assert len(annotations) == 1
        assert isinstance(annotations[0], MaskAnnotation)
        assert annotations[0].mask is not None


def test_fixture_dataset_with_mask_transform(fixture_dataset_root):
    def to_tensor(annotations):
        return torch.from_numpy(annotations[0].mask).long()

    ds = AnnotationDataset(
        DatasetSource(fixture_dataset_root), target_transform=to_tensor
    )
    for i in range(len(ds)):
        img, mask = ds[i]
        assert img.dtype == torch.uint8
        assert mask.dtype == torch.int64
        assert mask.ndim == 2
