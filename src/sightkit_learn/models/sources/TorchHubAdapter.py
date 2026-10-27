"""Torch Hub source adapter.

architecture.id  â€” torch.hub repo (e.g. 'ultralytics/ultralytics')
architecture.location â€” model entrypoint passed to torch.hub.load
weights.id[0]    â€” legacy entrypoint when architecture.location is absent
"""

from __future__ import annotations

import ast
import base64
import inspect
import json
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from omegaconf import DictConfig
from torch import nn

from sightkit_learn.models.ModelProperties import ModelProperties
from sightkit_learn.models.sources.SourceAdapter import SourceAdapter
from sightkit_learn.tasks import CVTask
from sightkit_learn.utils import get_logger

SOURCE_KEY = "torch_hub"
log = get_logger(__name__)


def _prepare_repository(repository: str):
    """Use this function to retain installed TorchVision extensions when Hub adds its source checkout to sys.path."""
    if repository.split(":", 1)[0] == "pytorch/vision":
        import torchvision

        return torchvision
    return None


def _hub_metadata(repository: str) -> tuple[dict, str]:
    """Use this function to read published Hub entrypoint declarations without executing repository code."""
    repo, _, ref = repository.partition(":")
    parts = repo.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError("repository must be owner/repo[:ref]")
    url = f"https://api.github.com/repos/{quote(parts[0], safe='')}/{quote(parts[1], safe='')}/contents/hubconf.py"
    if ref:
        url += "?" + urlencode({"ref": ref})
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "feral-vision-model-inspector",
        },
    )
    with urlopen(request, timeout=30) as response:
        document = json.load(response)
    source = base64.b64decode(document["content"]).decode("utf-8")
    entries = {}
    for node in ast.parse(source).body:
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ) and not node.name.startswith("_"):
            entries[node.name] = {
                "documentation": ast.get_docstring(node),
                "declaration": ast.unparse(node.args)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                else None,
            }
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                name = alias.asname or alias.name
                if not name.startswith("_") and name != "*":
                    entries[name] = {
                        "documentation": None,
                        "source_module": node.module,
                    }
    return entries, document["html_url"]


class TorchHubAdapter(SourceAdapter):
    """Load the configured Hub entrypoint with Hydra-selected native options."""

    def list_models(self, *, query=None, repository=None, pipeline_tag=None):
        """Use this function to discover entrypoints in an explicitly supplied Torch Hub repository."""
        if not repository:
            raise ValueError(
                "torch_hub discovery requires repository='owner/repo[:ref]'; Hub has no global repository catalogue"
            )
        if pipeline_tag:
            raise ValueError(
                "torch_hub has no pipeline_tag filter; use query to filter entrypoint names"
            )
        entries, _ = _hub_metadata(repository)
        for name in sorted(entries):
            if not query or query.casefold() in name.casefold():
                yield {"model_id": repository, "architecture_location": name}

    def fetch(self, cfg: DictConfig) -> nn.Module:
        """Delegate configured model construction to the upstream Hub implementation."""
        import torch

        weights = getattr(cfg, "weights", None)
        _prepare_repository(cfg.architecture.id)
        model_name = cfg.architecture.get("location")
        if not model_name:
            model_name = weights.id[0] if weights and weights.id else "default"
        log.info("loading %s from torch.hub repo %s", model_name, cfg.architecture.id)
        from hydra.utils import instantiate

        options = {
            "verbose": False,
            "trust_repo": True,
            **instantiate(cfg.architecture.get("kwargs", {}), _convert_="all"),
        }
        return torch.hub.load(cfg.architecture.id, model_name, **options)

    def inspect(self, cfg: DictConfig) -> tuple[ModelProperties, dict]:
        entrypoint = cfg.architecture.get("location")
        weights = cfg.get("weights")
        if not entrypoint:
            entrypoint = weights.id[0] if weights and weights.id else "default"
        entries, source_url = _hub_metadata(cfg.architecture.id)
        if entrypoint not in entries:
            raise ValueError(
                f"no published Hub entrypoint {entrypoint!r} in {cfg.architecture.id!r}"
            )
        properties = ModelProperties()
        metadata = {
            **entries[entrypoint],
            "entrypoint": entrypoint,
            "source_url": source_url,
            "available_weights": None,
            "nc": None,
            "names": None,
        }
        vision = _prepare_repository(cfg.architecture.id)
        if vision is not None:
            if entrypoint not in vision.models.list_models():
                return properties, metadata
            builder = vision.models.get_model_builder(entrypoint)
            metadata["documentation_version"] = vision.__version__
            metadata["documentation"] = inspect.getdoc(builder)
            metadata["declaration"] = str(inspect.signature(builder))
            for module, task in [
                (vision.models, CVTask.CLASSIFICATION),
                (vision.models.detection, CVTask.DETECTION),
                (vision.models.segmentation, CVTask.SEG_SEMANTIC),
            ]:
                if entrypoint in vision.models.list_models(module=module):
                    properties.model_outputs = [
                        CVTask.SEG_INSTANCE
                        if entrypoint.startswith("maskrcnn")
                        else task
                    ]
                    break
            try:
                variants = vision.models.get_model_weights(entrypoint)
            except ValueError:
                # Hub also exports helper entrypoints that have no weight enum.
                variants = []
            metadata["available_weights"] = [
                {"id": weight.name, "location": weight.url} for weight in variants
            ]
            for weight in variants:
                categories = weight.meta.get("categories")
                if categories:
                    metadata["nc"] = len(categories)
                    metadata["names"] = dict(enumerate(categories))
                    break
        return properties, metadata
