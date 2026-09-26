# Run Recipes

Run Recipes are complete Hydra entrypoints. This repository intentionally has
one training Run Recipe: `detection.yaml`.

Local training, container-image validation, and GPU deployment all compose
`runs/detection`. Runtime locations such as the staged dataset root may be
overridden, but deployment must not select or create a second Run Recipe.

Component YAML files under `data/`, `model/`, `train/`, `inference/`,
`tracking/`, and `augmentation/` own their concern-specific values. They are
not independent training deployment configurations.
