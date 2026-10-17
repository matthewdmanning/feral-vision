"""Hydra-configured inference using native MLflow PyTorch models."""

from collections.abc import Callable, Iterable, Iterator, Mapping
from operator import itemgetter
from typing import Any

import mlflow.pytorch
import torch
from hydra.utils import instantiate
from omegaconf import DictConfig

from feral_vision.utils import to_device


class Predictor:
    """Load a published model once and preserve its native prediction contract.

    Parameters
    ----------
    model_uri : str
        MLflow artifact URI, logged-model URI, registered version, or alias.
    device : str, optional
        Device selected for loading and input placement.
    call_mode : {"auto", "positional", "args", "kwargs"}
        In auto mode, mappings are keyword inputs, tuples are positional
        arguments, and tensors/lists are passed as one argument.
    load_kwargs : dict, optional
        Native MLflow loading options, including ``dst_path`` or ``map_location``.
    forward_kwargs : dict, optional
        Native model-forward options shared by predictions.
    preprocess, postprocess : callable, optional
        Explicit input/output processing instantiated from Hydra configuration.
        Without postprocessing, the exact native output object is returned.
    input_selector, target_selector : callable, optional
        Select model inputs and ground truth from labeled dataset batches.
        Defaults select positions zero and one from an image/target pair.

    Notes
    -----
    MLflow places eager models in evaluation mode and loads exported models
    with their captured behavior. Do not call eval again on exported modules.
    Prediction and configured processing run under torch.inference_mode.
    """

    def __init__(
        self,
        model_uri: str,
        *,
        device: str = "cpu",
        call_mode: str = "auto",
        load_kwargs: dict[str, Any] | None = None,
        forward_kwargs: dict[str, Any] | None = None,
        preprocess: Callable[[Any], Any] | None = None,
        postprocess: Callable[[Any], Any] | None = None,
        input_selector: Callable[[Any], Any] | None = None,
        target_selector: Callable[[Any], Any] | None = None,
    ) -> None:
        if call_mode not in {"auto", "positional", "args", "kwargs"}:
            raise ValueError(f"unsupported inference.call_mode {call_mode!r}")
        self.model_uri = model_uri
        self.device = torch.device(device)
        self.call_mode = call_mode
        self.forward_kwargs = forward_kwargs or {}
        self.preprocess = preprocess
        self.postprocess = postprocess
        self.input_selector = (
            input_selector if input_selector is not None else itemgetter(0)
        )
        self.target_selector = (
            target_selector if target_selector is not None else itemgetter(1)
        )
        self.model = mlflow.pytorch.load_model(
            model_uri,
            device=str(self.device),
            **{"map_location": str(self.device), **(load_kwargs or {})},
        )

    @torch.inference_mode()
    def predict(self, inputs: Any) -> Any:
        """Run one prepared batch and return the model's native or selected processed output.

        Parameters
        ----------
        inputs : Any
            Prepared tensor batch, image list, positional tuple, or keyword mapping.

        Returns
        -------
        Any
            Native predictions, optionally transformed by the configured postprocessor.
        """
        if self.preprocess is not None:
            inputs = self.preprocess(inputs)
        prepared = to_device(inputs, self.device)
        mode = self.call_mode
        if mode == "auto":
            if isinstance(prepared, Mapping):
                mode = "kwargs"
            elif isinstance(prepared, tuple):
                mode = "args"
            else:
                mode = "positional"
        if mode == "kwargs":
            outputs = self.model(**prepared, **self.forward_kwargs)
        elif mode == "args":
            outputs = self.model(*prepared, **self.forward_kwargs)
        else:
            outputs = self.model(prepared, **self.forward_kwargs)
        return self.postprocess(outputs) if self.postprocess is not None else outputs

    def predict_batches(self, batches: Iterable[Any]) -> Iterator[Any]:
        """Yield one native prediction result per prepared batch without buffering the stream."""
        for batch in batches:
            yield self.predict(batch)

    def predict_dataset(self, batches: Iterable[Any]) -> Iterator[tuple[Any, Any]]:
        """Yield predictions paired with ground truth from each labeled batch.

        Parameters
        ----------
        batches : Iterable
            DataLoader or stream using the configured labeled batch structure.

        Returns
        -------
        Iterator[tuple[Any, Any]]
            Native predictions and original selected targets, one pair per batch.
            Targets are not sent to the model or changed by prediction processing.
        """
        for batch in batches:
            inputs = self.input_selector(batch)
            targets = self.target_selector(batch)
            yield self.predict(inputs), targets


def build_predictor(cfg: DictConfig) -> Predictor:
    """Build native inference from the registered Hydra inference and tracking settings.

    Parameters
    ----------
    cfg : DictConfig
        Configuration containing ``inference`` and optional ``tracking`` settings.

    Returns
    -------
    Predictor
        Loaded model ready for prepared batches; no inference run is started.
    """
    options = cfg.inference
    if options.model_uri is None:
        raise ValueError("Set inference.model_uri to the MLflow model to load")
    tracking = cfg.get("tracking")
    if tracking is not None and tracking.get("tracking_uri") is not None:
        mlflow.set_tracking_uri(tracking.tracking_uri)
    return Predictor(
        options.model_uri,
        device=options.device,
        call_mode=options.call_mode,
        load_kwargs=instantiate(options.load_kwargs, _convert_="all"),
        forward_kwargs=instantiate(options.forward_kwargs, _convert_="all"),
        preprocess=instantiate(options.preprocess, _convert_="all"),
        postprocess=instantiate(options.postprocess, _convert_="all"),
        input_selector=instantiate(options.input_selector, _convert_="all"),
        target_selector=instantiate(options.target_selector, _convert_="all"),
    )
