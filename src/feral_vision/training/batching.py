"""Compatibility imports for shared prepared-data collators."""

from feral_vision.data.batching import collate_huggingface, collate_vision

__all__ = ["collate_huggingface", "collate_vision"]
