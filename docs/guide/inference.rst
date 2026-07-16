Inference
=========

Inference is not currently wired up. ``feral_segmentor.inference.predictor`` was
removed pending a redesign of how a plain ``nn.Module.forward()`` output maps to a
prediction contract — see ``ARCHITECTURE.md`` in the repository root for details.

Mask post-processing utilities (:func:`~feral_segmentor.inference.postprocess.clean_mask`,
:func:`~feral_segmentor.inference.postprocess.masks_to_boxes`) are available and
independent of the predictor.
