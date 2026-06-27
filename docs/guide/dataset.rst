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

Sources
-------

- ``(local, <path>)`` — directory on disk in the layout above
- ``(remote, coco_2017)`` — fetched via :func:`~feral_segmentor.data.fetch.fetch_coco`
