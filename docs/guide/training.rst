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

The former GCE launch script is deprecated. The required deployment topology
and first-run readiness gate are defined in ``docs/planning/product-scope.md``.

Data pipeline
-------------

DVC owns data preparation only (fetch, preprocess, augment) — not training or
evaluation:

.. code-block:: bash

   dvc repro
