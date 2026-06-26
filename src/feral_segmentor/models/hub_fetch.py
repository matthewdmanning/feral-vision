from pathlib import Path

import hydra
from huggingface_hub import hf_hub_download
from omegaconf import DictConfig

from feral_segmentor.utils import get_logger

log = get_logger(__name__)


def pull_model(cfg: DictConfig) -> list[Path]:
    """Download {repo_id, files} listed in a model config from the HF Hub into weights_dir."""
    weights_dir = Path(cfg.weights_dir)
    weights_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for filename in cfg.files:
        log.info("Fetching %s from %s", filename, cfg.repo_id)
        downloaded = hf_hub_download(
            repo_id=cfg.repo_id, filename=filename, local_dir=weights_dir
        )
        paths.append(Path(downloaded))
    return paths


@hydra.main(version_base=None, config_path="../../../conf", config_name="config")
def main(cfg: DictConfig) -> None:
    pull_model(cfg.model)


if __name__ == "__main__":
    main()
