Inference
=========

Inference is not currently wired up. ``feral_vision.inference.predictor`` was
removed pending a redesign of how a plain ``nn.Module.forward()`` output maps to a
prediction contract — see ``docs/architecture/program-flow.md`` for details.

Mask post-processing utilities (:func:`~feral_vision.inference.postprocess.clean_mask`,
:func:`~feral_vision.inference.postprocess.masks_to_boxes`) are available and
independent of the predictor.
