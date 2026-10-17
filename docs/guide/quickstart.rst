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

Workflow scripts acquire and transform data. Register one prepared Dataset with
``feral-vision/scripts/data/register.sh``; it runs ``dvc add`` and a targeted ``dvc push``.
There is no fixed DVC preparation pipeline. See :doc:`dataset` for the required
layout, default remote configuration, complete registration command, and the
remaining cloud publication integration.

Inspect local tracking without using a platform-specific project environment:

.. code-block:: bash

   uv tool run --from 'dvc[gs]==3.67.1' dvc status --json

This does not prepare data or verify the cloud remote. A result of ``{}`` can
also mean no Dataset is registered yet. Training requires a prepared Dataset
with compatible annotations; a configured default path alone does not provide one.

Train
-----

The canonical training entrypoint is ``sightkit_learn.training.trainer``:

.. code-block:: bash

   cd feral-vision
   uv run python -m sightkit_learn.training.trainer --config-dir conf --config-name runs/detection

See :doc:`training` for GCP training and further detail.

Model inspector
---------------

Run the following command from the repository root (return there after local
training). The model inspector uses the MCP 2 Python SDK and serves its tools over stdio.
The repository connector configuration and desktop bundle use the locked
environment. An MCP client launches the server with:

.. code-block:: bash

   uv run --frozen python mcp/server/main.py

It provides model inspection, adapter discovery, adapter reading and writing,
and Hugging Face model search. Set ``PROJECT_ROOT`` when the client operates
on a checkout other than its working directory.
