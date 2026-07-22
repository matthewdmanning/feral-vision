# Augmentation configuration

## Purpose

Augmentation configuration selects the stock Albumentations operations active
for a run.

## Selection

Choose a semantic augmentation variant as part of a complete Run Recipe.

## Ownership

`data/augmentations.py` owns assembly and composition; YAML only declares the
active operations. The augmentation boundary is defined in
[the program flow](../../docs/architecture/program-flow.md).
