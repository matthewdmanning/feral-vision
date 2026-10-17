"""Native model inference through MLflow, with explicit task post-processing."""

from feral_vision.inference.predictor import Predictor, build_predictor
from feral_vision.inference.loading import build_dataloader

__all__ = ["Predictor", "build_predictor", "build_dataloader"]
