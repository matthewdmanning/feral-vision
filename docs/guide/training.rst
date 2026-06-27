Training
========

Local training
--------------

.. code-block:: bash

   uv run python -m feral_segmentor.training.train

GCP training
------------

Requires ``GCP_PROJECT`` and ``GCS_BUCKET`` environment variables:

.. code-block:: bash

   GCP_PROJECT=my-proj GCS_BUCKET=my-bucket bash scripts/gcp_train.sh

Pipeline
--------

Run the full DVC pipeline:

.. code-block:: bash

   dvc repro
