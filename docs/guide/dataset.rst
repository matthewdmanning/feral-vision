Dataset Layout
==============

All datasets follow a canonical two-directory layout::

   <root>/
     images/       # raw image files (.jpg, .jpeg, .png, .bmp)
     annotations/  # annotation files matched by stem to images/
                   #   <stem>.png or <stem>.jpg  -- semantic mask
                   #   <stem>.txt                -- YOLO bbox
                   #   <stem>.json               -- classification labels
                   #   names.yaml                -- class index reference

Annotation files are loaded by extension and are assumed to already be in the
correct format for that extension — there is no additional validation layer.

Sources
-------

``cfg.data.source`` (:mod:`feral_vision.data.fetch`) is a pluggable dispatch
point, not a fixed set of options. Current sources:

- ``coco`` — downloads COCO train2017 (animal supercategory) via
  :func:`~feral_vision.data.fetch.fetch_coco`.
- anything else — treated as a local filesystem path already in the layout above,
  via :func:`~feral_vision.data.fetch.fetch_data`.

Additional sources are added by extending the dispatch in ``fetch.py``; each must
resolve to the layout above.

Sampled COCO zoo pull
---------------------

For a bounded COCO 2017 training subset, call the FiftyOne helper from Python::

   from scripts.pull_coco_train2017 import pull_coco_train2017

   dataset = pull_coco_train2017(
       max_epochs=max_epochs,
       batch_size=batch_size,
   )

It loads COCO's ``train`` split with detection annotations for bird, cat, dog,
horse, sheep, cow, elephant, bear, zebra, and giraffe. The sample limit is
``max_epochs * batch_size``; FiftyOne manages the downloaded images and
annotations in its dataset-zoo storage. This is separate from the DVC ``coco``
fetch stage above.

Cloud Dataset Artifacts
-----------------------

Publication requires ``TRAINING_DATA_BUCKET_URI``,
``DATASET_ARTIFACT_PREFIX``, and ``GCS_URI_PREFIX`` in the environment. Set
``GCS_URI_PREFIX`` to the Cloud Storage URI scheme and separator. Cloud Build
passes it through the required ``_GCS_URI_PREFIX`` substitution; there is no
hard-coded fallback. Python publication tests set an isolated URI prefix.

Cloud preparation publishes the selected ``images/`` and ``annotations/``
layout under ``payload/`` in a Google Cloud Storage artifact prefix. It then
writes ``dataset-artifact.json`` beside that payload. The manifest lists every
payload file with its SHA-256 and object generation. The bucket is the durable
Dataset Artifact catalog; object retention protects each published generation.

Acquisition and publication are intentionally separate. Any source-specific
acquisition image writes ``/workspace/payload/images/``,
``/workspace/payload/annotations/``, and ``/workspace/dataset-input.json``.
The input metadata identifies the dataset and source and carries a provenance
object. A minimal source-agnostic publication image validates that shared
workspace and uploads the payload and manifest with the Cloud Storage Python
client. This lets a new download source reuse the publication boundary without
adding its dependencies to the publication image.
The acquisition image includes FiftyOne and its MongoDB runtime; those
source-specific dependencies are not part of the publisher.

Training stages its selected Dataset Artifact on the training VM's local SSD.
It records the SHA-256 of ``dataset-artifact.json`` in MLflow lineage. A later
data version is adopted through a reviewed input selection, rather than by
overwriting the source artifact in place.

The training run names the retained generation of the annotations object and
stages it alongside the selected images on the local SSD.
