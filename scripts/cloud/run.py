"""Load cloud-smoke configuration and invoke one operational script."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess

from hydra import compose, initialize_config_dir
from omegaconf import DictConfig, OmegaConf

from feral_vision.config.store import register_configs

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = Path(__file__).resolve().parent


def _required(cfg: DictConfig, path: str) -> str:
    """Return one non-empty configuration value."""
    value = OmegaConf.select(cfg, path)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing required cloud configuration: {path}")
    return value


def _environment(cfg: DictConfig) -> dict[str, str]:
    """Build the operational-script environment from declarative configuration."""
    deploy = cfg.deploy
    substitutions = deploy.substitutions
    project = _required(substitutions, "_GCP_PROJECT")
    region = _required(substitutions, "_REGION")
    repository = _required(substitutions, "_REPO")
    image_name = _required(substitutions, "_IMAGE_NAME")
    image_tag = _required(substitutions, "_IMAGE_TAG")
    return {
        "GCP_PROJECT": project,
        "REGISTRY_REGION": region,
        "ARTIFACT_REPOSITORY": repository,
        "BASE_IMAGE_NAME": _required(substitutions, "_BASE_IMAGE_NAME"),
        "TRAINING_IMAGE_NAME": image_name,
        "IMAGE_TAG": image_tag,
        "IMAGE_URI": (
            f"{region}-docker.pkg.dev/{project}/{repository}/{image_name}:{image_tag}"
        ),
    }


def _load_config(path: Path) -> DictConfig:
    """Compose one deploy config with its registered structured schema."""
    path = path.resolve()
    config_root = PROJECT_ROOT.resolve()
    try:
        config_name = path.relative_to(config_root).with_suffix("").as_posix()
    except ValueError as exc:
        raise ValueError(f"Cloud config must be under {config_root}: {path}") from exc

    register_configs()
    with initialize_config_dir(version_base=None, config_dir=str(config_root)):
        return compose(config_name=config_name)


def main() -> None:
    """Run the selected cloud-smoke operation with declared configuration."""
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "push"))
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT / "deploy" / "cloudbuild.yaml",
    )
    args = parser.parse_args()

    cfg = _load_config(args.config)
    environment = os.environ | _environment(cfg)
    subprocess.run([SCRIPTS / f"{args.action}.sh"], check=True, env=environment)


if __name__ == "__main__":
    main()
