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

Cloud preparation publishes the selected ``images/`` and ``annotations/``
layout under ``payload/`` in a versioned Google Cloud Storage artifact prefix.
It then writes ``dataset-artifact.json`` and a version-aware
``dataset-artifact.dvc`` tracker beside that payload. The bucket is the durable
Dataset Artifact catalog; the tracker pins the object generations without
copying the data into the application repository.

Acquisition and publication are intentionally separate. Any source-specific
acquisition image writes ``/workspace/payload/images/``,
``/workspace/payload/annotations/``, and ``/workspace/dataset-input.json``.
The input metadata identifies the dataset and source and carries a provenance
object. A minimal source-agnostic DVC image validates that shared workspace,
uploads the payload and manifest with the Cloud Storage Python client, and then
creates the version-aware tracker. This lets a new download source reuse the
publication boundary without adding its dependencies to the DVC image.
The COCO acquisition image includes FiftyOne and its MongoDB runtime; those
source-specific dependencies are not part of the publisher.

Training stages its selected Dataset Artifact on the training VM's local SSD.
It creates ``dataset-artifact.dvc`` and ``dvc.lock`` locally before model
training, then records the lock in MLflow lineage. A later data version is
adopted through a reviewed input selection, rather than by overwriting the
source artifact in place.

When a Dataset has a retained annotation generation but no live annotation or
lockfile, the training run names that retained generation, stages it alongside
the selected images on the local SSD, and creates its local DVC tracker and
lock before training.
