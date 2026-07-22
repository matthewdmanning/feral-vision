from pathlib import Path

import yaml


def test_dvc_pipeline_owns_only_data_operations() -> None:
    """DVC versions data artifacts; training and evaluation are runtime work."""
    pipeline = yaml.safe_load(Path("dvc.yaml").read_text())

    assert set(pipeline["stages"]) == {"fetch", "preprocess", "augment"}
