"""Verify the first augmented detection cloud workflow keeps immutable inputs explicit.

The Terraform side of this workflow is covered by
``terraform/tests/detection_run.tftest.hcl``; per the Terraform test boundary in
``docs/agents/testing.md``, Terraform contracts are not asserted from here.
"""

from __future__ import annotations

# stdlib
from pathlib import Path

# third-party
import yaml


# ---------------------------------------------------------------------------
# Run-specific Cloud Build contract
# ---------------------------------------------------------------------------


def test_variant_materialization_build_uses_selected_identity_and_image_input() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load(
        (
            repository_root
            / "deploy/runs/detection_first_run_augmented/cloudbuild.materialize-variant.yaml"
        ).read_text()
    )

    assert config["serviceAccount"].endswith(
        "feral-vision-ai@cs-poc-kewg0kffb7uwobgq1rex2af.iam.gserviceaccount.com"
    )
    assert config["steps"][0]["name"] == "${_TRAINING_IMAGE}"
    assert config["steps"][0]["env"] == [
        "GCS_BUCKET=${_GCS_BUCKET}",
        "RAW_DATASET_ARTIFACT_URI=${_RAW_DATASET_ARTIFACT_URI}",
        "VARIANT_ARTIFACT_PREFIX=${_VARIANT_ARTIFACT_PREFIX}",
    ]
