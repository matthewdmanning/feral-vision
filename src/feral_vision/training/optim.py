"""Hydra builders for configurable training components."""

from hydra.utils import instantiate


def build_optimizer(parameters, config):
    """Use this function to bind a configured optimizer to model parameters."""
    return instantiate(config)(parameters)


def build_scheduler(optimizer, config):
    """Use this function to bind an optional configured scheduler to an optimizer."""
    return instantiate(config)(optimizer) if config else None


def build_loss_fn(config):
    """Use this function to instantiate the configured loss function."""
    return instantiate(config)
