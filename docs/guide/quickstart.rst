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

Set ``PROJECT_ROOT`` when the client operates on another checkout. MCP exposes
five prep tools: ``list_adapters``, ``list_models``, ``inspect_model``,
``save_model`` and ``get_model``. There are no source-code editing tools.

``list_adapters`` reports each provider and its accepted filters. Use
``list_models(source=..., query=..., filters=...)`` for both discovery and
search. ``query`` searches model names; ``filters`` matches returned fields
exactly, before pagination. All providers accept ``model_id`` and
``architecture_location`` filters. Hugging Face also accepts ``pipeline_tag``;
Ultralytics also accepts ``kind`` (``architecture`` or ``checkpoint``).
Unsupported filter fields are errors. Follow ``next_offset`` using ``offset``
to retrieve more results; ``limit`` defaults to 100 and accepts 1–1000.

Examples of MCP arguments:

* Ultralytics: ``source="ultralytics"``, ``query="yolo11"``,
  ``filters={"kind": "checkpoint"}``.
* Hugging Face: ``source="hf_hub"``, ``query="detr"``,
  ``filters={"pipeline_tag": "object-detection"}``.
  ``repository`` optionally filters the author.
* Torch Hub: ``source="torch_hub"``,
  ``repository="pytorch/vision:v0.20.1"``, ``query="resnet"``.
  Hub requires a repository; there is no global repository catalogue.

Pass a candidate's ``model_id`` and ``architecture_location`` to
``inspect_model``. Prep reads metadata without constructing models, loading
weights, downloading repository archives or executing their code:

* Hugging Face reads Hub metadata and the small ``config.json``.
* Ultralytics lists installed architecture YAMLs and known checkpoint names.
  Inspection reads architecture YAML and constructor documentation. ``nc`` is
  an architecture default, not a measurement of a checkpoint; class names
  remain unknown when no published vocabulary is available.
* Torch Hub reads the published ``hubconf.py`` as text and parses declarations
  without importing or executing it. For ``pytorch/vision``, inspection also
  reads the installed TorchVision's builder documentation and weight enums
  without calling a model builder. Generic Hub entrypoints may have unknown
  task or weight information; declarations and documentation remain available.

``inspect_model`` returns ``config``, ``model_outputs``, ``metadata`` and
``missing``. Unknown or unmapped tasks retain an empty ``model_outputs`` list.
Available pretrained weights are provider facts; choosing starting weights is
a separate setup choice. Constructor options supplied to inspection are saved
as configuration, not executed.

``save_model`` takes a local ``name`` plus ``config``, ``model_outputs`` and
``metadata``. It saves them in ``models/registry/model_registry.json``.
Replacing an entry requires ``overwrite=True``. Configuration must satisfy
``ModelConfig``; unresolved ``???`` values currently fail save validation.
``get_model`` retrieves the saved information and Hydra YAML without contacting
a provider or MLflow.

For Python setup, ``sightkit_learn.models.offline_registry.load_model_definition``
takes the registry path and saved name and returns ``(DictConfig,
ModelProperties, metadata)``. Prep stops at this configuration handoff.
