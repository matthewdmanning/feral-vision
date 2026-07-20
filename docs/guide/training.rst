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
logged to MLflow when a run is active, and the best checkpoint is written to
``models/registry/best.pt``.

GCP training
------------

Requires ``GCP_PROJECT`` and ``GCS_BUCKET`` environment variables:

.. code-block:: bash

   GCP_PROJECT=my-proj GCS_BUCKET=my-bucket bash scripts/gcp_train.sh

Data pipeline
-------------

DVC owns data preparation only (fetch, preprocess, augment) — not training or
evaluation:

.. code-block:: bash

   dvc repro
