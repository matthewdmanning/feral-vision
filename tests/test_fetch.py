"""Contracts for local and COCO data acquisition at the data-flow boundary."""

from __future__ import annotations

# stdlib
import io
import json
import zipfile
from pathlib import Path

# third-party
import pytest

# project
from feral_vision.data import fetch


# ---------------------------------------------------------------------------
# Helpers / local fixtures
# ---------------------------------------------------------------------------


class _BytesResponse:
    """Context-managed URL response carrying an in-memory byte payload."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def __enter__(self) -> _BytesResponse:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


def _coco_annotations_zip() -> bytes:
    """Build a tiny COCO annotations archive with animal and non-animal records."""
    full = {
        "info": {"description": "fixture"},
        "licenses": [{"id": 1}],
        "categories": [
            {"id": 1, "name": "cat", "supercategory": "animal"},
            {"id": 2, "name": "car", "supercategory": "vehicle"},
        ],
        "images": [
            {"id": 10, "file_name": "cat.jpg"},
            {"id": 20, "file_name": "car.jpg"},
            {"id": 30, "file_name": "dog.jpg"},
        ],
        "annotations": [
            {"id": 100, "image_id": 10, "category_id": 1},
            {"id": 200, "image_id": 20, "category_id": 2},
            {"id": 300, "image_id": 30, "category_id": 1},
        ],
    }
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("annotations/instances_train2017.json", json.dumps(full))
    return stream.getvalue()


# ---------------------------------------------------------------------------
# fetch_data — local source boundary
# ---------------------------------------------------------------------------


def test_fetch_data_returns_resolved_existing_local_directory(tmp_path):
    source = tmp_path / "nested" / "dataset"
    source.mkdir(parents=True)

    resolved = fetch.fetch_data(str(source))

    assert resolved == source.resolve()


@pytest.mark.parametrize("source", ["https://example.test/data", "s3://bucket/data"])
def test_fetch_data_rejects_non_local_uri_schemes(source):
    with pytest.raises(ValueError, match="unsupported data source scheme"):
        fetch.fetch_data(source)


def test_fetch_data_rejects_missing_local_path(tmp_path):
    with pytest.raises(FileNotFoundError, match="does not exist"):
        fetch.fetch_data(str(tmp_path / "missing"))


# ---------------------------------------------------------------------------
# fetch_coco — filtered, idempotent remote acquisition contract
# ---------------------------------------------------------------------------


def test_fetch_coco_filters_animal_records_and_skips_existing_downloads(
    tmp_path, monkeypatch
):
    downloads: list[tuple[str, Path]] = []

    monkeypatch.setattr(
        fetch.urllib.request,
        "urlopen",
        lambda url: _BytesResponse(_coco_annotations_zip()),
    )

    def _download(url: str, destination: Path) -> None:
        downloads.append((url, destination))
        destination.write_bytes(b"image")

    monkeypatch.setattr(fetch.urllib.request, "urlretrieve", _download)

    images_dir, annotations_path = fetch.fetch_coco(str(tmp_path))

    filtered = json.loads(annotations_path.read_text())
    assert images_dir == tmp_path.resolve() / "images" / "coco_train2017"
    assert [category["id"] for category in filtered["categories"]] == [1]
    assert [image["id"] for image in filtered["images"]] == [10, 30]
    assert [annotation["id"] for annotation in filtered["annotations"]] == [100, 300]
    assert [destination.name for _, destination in downloads] == ["cat.jpg", "dog.jpg"]
    assert all(destination.exists() for _, destination in downloads)

    monkeypatch.setattr(
        fetch.urllib.request,
        "urlopen",
        lambda url: pytest.fail("cached annotations must not be downloaded again"),
    )
    monkeypatch.setattr(
        fetch.urllib.request,
        "urlretrieve",
        lambda url, destination: pytest.fail(
            "existing images must not be downloaded again"
        ),
    )

    assert fetch.fetch_coco(str(tmp_path)) == (images_dir, annotations_path)
