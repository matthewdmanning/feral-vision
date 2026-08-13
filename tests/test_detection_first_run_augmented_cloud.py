"""Verify the first augmented detection cloud workflow keeps immutable inputs explicit."""

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


# ---------------------------------------------------------------------------
# Terraform runtime input contract
# ---------------------------------------------------------------------------


def test_run_terraform_passes_modular_training_inputs_to_startup_template() -> None:
    repository_root = Path(__file__).resolve().parents[1]
    terraform_root = repository_root / "terraform/runs/detection_first_run_augmented"
    main = (terraform_root / "main.tf").read_text()
    variables = (terraform_root / "variables.tf").read_text()
    startup = (terraform_root / "templates/trainer_startup.sh.tftpl").read_text()

    for name in (
        "source_annotation_generation",
        "dataset_host_mount_dir",
        "dataset_container_mount_dir",
        "run_config_name",
        "mlflow_tracking_uri",
    ):
        assert f'variable "{name}"' in variables
        assert f"{name} " in main and f"var.{name}" in main
        assert f"${{{name}}}" in startup
    assert 'readonly local_ssd_device="/dev/nvme0n1"' in startup
    assert 'uv run --no-sync dvc init --no-scm' in startup
    assert 'cp dvc.lock "${dataset_container_mount_dir}/dvc.lock"' in startup
