"""Regression tests for the deliberately singular GPU training deployment path."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_only_one_complete_training_recipe_exists() -> None:
    recipes = sorted((ROOT / "conf" / "runs").glob("*.yaml"))
    assert [path.name for path in recipes] == ["detection.yaml"]


def test_only_one_gpu_training_dockerfile_exists() -> None:
    dockerfiles = sorted(ROOT.glob("deploy/**/Dockerfile.gcp"))
    assert dockerfiles == [ROOT / "deploy" / "Dockerfile.gcp"]


def test_only_one_container_training_entrypoint_exists() -> None:
    entrypoints = sorted((ROOT / "scripts" / "runs").glob("*container_train*.sh"))
    assert entrypoints == [ROOT / "scripts" / "runs" / "container_train.sh"]


def test_gpu_runtime_uses_dataset_manifest_and_not_dvc() -> None:
    runtime_paths = [
        ROOT / "terraform" / "runs" / "detection" / "templates" / "trainer_startup.sh.tftpl",
        ROOT / "scripts" / "runs" / "container_train.sh",
    ]
    runtime = "\n".join(path.read_text().lower() for path in runtime_paths)

    assert "dataset-artifact.json" in runtime
    for forbidden in ("dvc init", "dvc add", "dvc repro", "dvc.lock"):
        assert forbidden not in runtime


def test_training_image_matches_locked_torch_cuda_generation() -> None:
    dockerfile = (ROOT / "deploy" / "Dockerfile.gcp").read_text()
    lockfile = (ROOT / "uv.lock").read_text()

    # PyTorch 2.12.1 in this lock uses CUDA 13 user-space dependencies. Keep
    # the container's NVIDIA CUDA major aligned so an environment update cannot
    # silently reintroduce the old CUDA-12/CUDA-13 split.
    assert 'name = "torch"\nversion = "2.12.1"' in lockfile
    assert 'name = "nvidia-cudnn-cu13"' in lockfile
    assert "nvidia/cuda:13.0.0-base-ubuntu24.04@sha256:" in dockerfile


def test_training_image_is_reproducible_and_smoke_checked() -> None:
    dockerfile = (ROOT / "deploy" / "Dockerfile.gcp").read_text()
    cloudbuild = (ROOT / "deploy" / "cloudbuild.training-image.yaml").read_text()

    assert "nvidia/cuda:13.0.0-base-ubuntu24.04@sha256:" in dockerfile
    assert "ghcr.io/astral-sh/uv:0.12.18@sha256:" in dockerfile
    assert "uv sync --frozen --no-dev --no-editable" in dockerfile
    assert "--config-name runs/detection --cfg job" in dockerfile
    assert 'ENTRYPOINT ["bash", "/workspace/scripts/runs/container_train.sh"]' in dockerfile

    build = cloudbuild.index("id: build-training-image")
    verify = cloudbuild.index("id: verify-training-image-contract")
    push = cloudbuild.index("id: push-training-image")
    assert build < verify < push


def test_vm_authenticates_registry_before_pull_and_checks_host_gpu_runtime() -> None:
    startup = (
        ROOT
        / "terraform"
        / "runs"
        / "detection"
        / "templates"
        / "trainer_startup.sh.tftpl"
    ).read_text()

    assert "stage=\"verify_container_runtime\"" in startup
    assert "nvidia-smi --query-gpu=name,driver_version" in startup
    authenticate = startup.index("gcloud auth configure-docker")
    pull = startup.index('docker pull "$training_image"')
    assert authenticate < pull


def test_preflight_and_launcher_pin_the_handoff() -> None:
    preflight = (ROOT / "terraform" / "preflight" / "preflight.py").read_text()
    launcher = (ROOT / "scripts" / "runs" / "detection.sh").read_text()

    assert "deployment-manifest.json" in preflight
    assert "terraform_plan_sha256" in preflight
    assert "dataset_artifact_sha256" in preflight
    assert "terraform_plan_sha256" in launcher
    assert "dataset_artifact_sha256" in launcher
