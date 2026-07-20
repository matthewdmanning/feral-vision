# Augmentation configuration

Augmentation configuration selects the stock Albumentations operations active
for a run. It describes parameters only; `data/augmentations.py` owns assembly
and composition, and no project-specific composition wrapper is part of this
contract.

Choose a semantic augmentation variant as part of a complete run. See
[ARCHITECTURE.md](../../ARCHITECTURE.md) for the augmentation boundary.
