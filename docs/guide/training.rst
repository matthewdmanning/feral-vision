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
then runs :meth:`~feral_vision.training.Trainer.Trainer.fit`. Metrics are
logged to MLflow when a run is active. When artifact logging succeeds, only the
selected best model artifact is recorded; intermediate checkpoints remain local
and are not retained in the artifact store.

Recipe-specific operating contracts are maintained in ``docs/runs/``.

Cloud training
--------------

Cloud training is provisioned through Terraform and its operational scripts;
manual Docker launches are not a supported workflow. The provisioned GPU VM
stages data on its SSD, mounts it at ``/data`` in the training container, runs
the configured augmentation, and starts the canonical trainer. Cloud workflow
changes are made through the Terraform and operational-script interfaces.

Data pipeline
-------------

DVC owns data preparation only (fetch, preprocess, augment) — not training or
evaluation:

.. code-block:: bash

   dvc repro

For cloud training, the selected Dataset Artifact is prepared and reviewed
upstream in the dedicated DVC repository. The training container receives its
staged data and does not invoke DVC or resolve a mutable Cloud Storage prefix.
