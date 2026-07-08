import hydra
import mlflow
from hydra.core.hydra_config import HydraConfig
from omegaconf import DictConfig, OmegaConf
from feral_segmentor.config.store import register_configs
from feral_segmentor.utils import get_logger

logger = get_logger(__name__)


def _flatten_params(obj, prefix: str = "") -> dict[str, object]:
    """Flatten a nested config mapping into dotted scalar keys for mlflow."""
    flat: dict[str, object] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            flat.update(_flatten_params(value, child))
    else:
        flat[prefix] = obj
    return flat


@hydra.main(version_base=None, config_path="../../conf", config_name="config")
def main(cfg: DictConfig) -> None:
    register_configs()

    output_dir = HydraConfig.get().runtime.output_dir
    logger.info("hydra output dir: %s", output_dir)

    mlflow.set_tracking_uri(cfg.tracking.tracking_uri)
    mlflow.set_experiment(cfg.tracking.experiment_name)

    resolved = OmegaConf.to_container(cfg, resolve=True)
    with mlflow.start_run():
        mlflow.log_params(_flatten_params(resolved))
        mlflow.log_param("output_dir", output_dir)
        mlflow.set_tag("output_dir", output_dir)
        mlflow.set_tag("dataset_variant", cfg.augmentation.name)


if __name__ == "__main__":
    main()
