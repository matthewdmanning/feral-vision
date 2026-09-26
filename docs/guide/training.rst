Training
========

Feral Vision has one complete training Run Recipe:
``conf/runs/detection.yaml``. Local execution, image validation, and the GPU
training deployment all compose that same recipe.

Dataset boundary
----------------

Dataset versioning and publication happen upstream of GPU training. The
published Dataset Artifact is the handoff boundary. Training requires its
``payload/images/``, selected annotations, and ``dataset-artifact.json``.

``dataset-artifact.json`` is the provenance record consumed by training. The
GPU workflow does not initialize DVC, generate a new ``dvc.lock``, or reproduce
the dataset. Deployment preflight parses the published manifest and records its
SHA-256; VM startup stages and re-hashes the exact manifest before training.
The container verifies the same SHA-256 again before starting the trainer.

Training image
--------------

The only supported GPU training image is ``deploy/Dockerfile.gcp``. Build it
through ``scripts/cloud/build_training_image.sh``, which uses
``deploy/cloudbuild.training-image.yaml`` and returns a digest-pinned Artifact
Registry reference for Terraform.

The image build composes ``runs/detection`` and imports the core runtime before
it can be pushed. GPU availability is verified later on the actual training VM.

GPU deployment
--------------

Run ``terraform/preflight/preflight.py`` with the exact intended Terraform
inputs before every apply. A passing preflight produces a saved Terraform plan
and ``deployment-manifest.json`` containing the plan SHA-256, digest-pinned
training image, Dataset Artifact URI, and Dataset Artifact manifest SHA-256.

Apply only through::

   scripts/runs/detection.sh --manifest terraform/preflight/reports/<timestamp>/deployment-manifest.json

The launcher rejects a changed plan, collects startup logs, waits for terminal
``training-evidence.json``, and verifies that the Dataset Artifact manifest hash
observed by the VM matches the hash approved during preflight.

A VM reaching ``RUNNING`` is not training success. Terminal training evidence
is the authoritative run result.

Run metadata
------------

MLflow records the resolved training configuration and the exact
``dataset-artifact.json`` used by the run, including its SHA-256. The startup
workflow also preserves that manifest beside terminal run evidence in the
operational artifact prefix.
