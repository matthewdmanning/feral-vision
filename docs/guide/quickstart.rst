Quickstart
==========

Install (development)
----------------------

This project is not published as a package. Install for local development with
``uv``:

.. code-block:: bash

   uv sync

Prepare data
------------

DVC owns data preparation only (fetch, preprocess, augment) — not training or
evaluation:

.. code-block:: bash

   dvc repro

Train
-----

The canonical training entrypoint is ``feral_vision.training.trainer``:

.. code-block:: bash

   uv run python -m feral_vision.training.trainer

See :doc:`training` for GCP training and further detail.
