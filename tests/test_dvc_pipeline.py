"""Verify DVC stages cover the documented data-preparation pipeline only."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def dvc_pipeline() -> dict:
    """Load the repository DVC pipeline definition."""
    return yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "dvc.yaml").read_text()
    )


@pytest.fixture(
    params=[
        ("fetch", "feral_vision.data.fetch", None, "data/raw"),
        ("preprocess", "feral_vision.data.transforms", "data/raw", "data/processed"),
        (
            "augment",
            "feral_vision.data.augmentations",
            "data/processed",
            "data/augmented",
        ),
    ]
)
def dvc_data_stage(request: pytest.FixtureRequest) -> tuple[str, str, str | None, str]:
    """Provide each documented data-preparation stage contract."""
    return request.param


def test_dvc_pipeline_declares_only_documented_data_stages(
    dvc_pipeline: dict, dvc_data_stage: tuple[str, str, str | None, str]
) -> None:
    stage_name, module, dependency, output = dvc_data_stage
    stages = dvc_pipeline["stages"]
    stage = stages[stage_name]

    assert set(stages) == {"fetch", "preprocess", "augment"}
    assert stage["cmd"] == f"uv run python -m {module}"
    assert stage["outs"] == [output]
    if dependency is None:
        assert "deps" not in stage
    else:
        assert stage["deps"] == [dependency]
