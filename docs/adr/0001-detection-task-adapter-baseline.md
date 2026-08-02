# Detection task adapter for the first fine-tuning baseline

The first Feral Vision training run fine-tunes the PyTorch ``nn.Module``
downloaded through the Ultralytics source adapter as a two-class COCO-animal
bounding-box detector. A detection Task Adapter in ``training`` will preserve
the model's native target assignment, translate annotation-aware augmented
boxes and unchanged class labels into its batch contract, and compute the
selected classification plus generalized-IoU loss. This preserves the generic
trainer's ownership of optimization, MLflow, and checkpoints while keeping
model acquisition and augmentation outside the training loop. The run may start
only from a verified immutable augmented Dataset Variant, linked back
to its raw COCO Dataset Artifact.
