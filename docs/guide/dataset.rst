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

``cfg.data.source`` (:mod:`feral_segmentor.data.fetch`) is a pluggable dispatch
point, not a fixed set of options. Current sources:

- ``coco`` — downloads COCO train2017 (animal supercategory) via
  :func:`~feral_segmentor.data.fetch.fetch_coco`.
- anything else — treated as a local filesystem path already in the layout above,
  via :func:`~feral_segmentor.data.fetch.fetch_data`.

Additional sources are added by extending the dispatch in ``fetch.py``; each must
resolve to the layout above.
