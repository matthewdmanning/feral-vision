"""Computer vision task enum for the feral-vision dataset pipeline."""

from __future__ import annotations

from enum import StrEnum


class CVTask(StrEnum):
    SEG_INSTANCE = "seg_instance"  # bounding box per instance
    SEG_SEMANTIC = "seg_semantic"  # pixel-level class mask
    DETECTION = "detection"  # binary present/absent
    CLASSIFICATION = "classification"
    POSE = "pose"

    # Mutually exclusive constraints (enforced at Dataset init):
    #   SEG_INSTANCE xor SEG_SEMANTIC  (at most one segmentation type)
    #   DETECTION is exclusive with all others
    #   POSE is at most one per dataset
    #   CLASSIFICATION may appear multiple times (multi-head)
