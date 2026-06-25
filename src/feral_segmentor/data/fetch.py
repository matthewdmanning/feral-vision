"""Data acquisition for the fetch DVC stage.

For the ``local`` source this just resolves and validates a directory already on
disk. Other source schemes (e.g. remote download) are not yet supported and
raise :class:`ValueError`.
"""

from __future__ import annotations

from pathlib import Path

import hydra
from omegaconf import DictConfig

from feral_segmentor.constants import DEFAULT_DATA_SOURCE
from feral_segmentor.utils import get_logger

logger = get_logger(__name__)


def fetch_data(source: str = DEFAULT_DATA_SOURCE) -> Path:
    """Resolve a data location and return its :class:`~pathlib.Path`.

    Parameters
    ----------
    source:
        A local filesystem path to a data directory. For the local source the
        path must already exist on disk.

    Returns
    -------
    Path
        The resolved, existing data path.

    Raises
    ------
    FileNotFoundError
        If ``source`` resolves to a path that does not exist.
    ValueError
        If ``source`` uses an unsupported (non-local) scheme such as
        ``http://`` or ``s3://``.
    """
    # Reject URI-style schemes; only plain local paths are supported for now.
    if "://" in source:
        scheme = source.split("://", 1)[0]
        raise ValueError(f"unsupported data source scheme: {scheme!r}")

    path = Path(source).resolve()
    if not path.exists():
        raise FileNotFoundError(f"data source path does not exist: {path}")
    logger.info("resolved local data source: %s", path)
    return path


@hydra.main(version_base=None, config_path="../../../conf", config_name="config")
def main(cfg: DictConfig) -> None:
    """Hydra entrypoint for the fetch DVC stage."""
    fetch_data(cfg.data.root)


if __name__ == "__main__":
    # Schemas must be registered before Hydra composes the config.
    from feral_segmentor.config.store import register_configs

    register_configs()
    main()
