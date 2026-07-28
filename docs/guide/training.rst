Training
========

Local training
--------------

The canonical training entrypoint is ``feral_vision.training.trainer``, wired
via Hydra:

.. code-block:: bash

   uv run python -m feral_vision.training.trainer

This builds the model (:mod:`feral_vision.models.register_model`), optimizer,
scheduler, and loss function from ``conf/train/`` (see :doc:`../api/training`),
then runs :meth:`~feral_vision.training.trainer.Trainer.fit`. Metrics are
logged to MLflow when a run is active. When artifact logging succeeds, only the
selected best model artifact is recorded; intermediate checkpoints remain local
and are not retained in the artifact store.

Cloud training
--------------

Stage a configured Ultralytics checkpoint before the GPU VM run::

   GCS_BUCKET=feral-vision scripts/cloud/stage_model.sh conf/model/yolo11n_seg.yaml

The GPU container mounts its SSD-backed input data at ``/data``, applies the
selected Hydra augmentation, and then starts the canonical trainer. The broader
deployment topology is defined in ``docs/planning/product-scope.md``.

Data pipeline
-------------

DVC owns data preparation only (fetch, preprocess, augment) — not training or
evaluation:

.. code-block:: bash

   dvc repro
