# Data and model tests

Use this guide when changing data ingestion, datasets, model tests, or model
examples.

Every dataset root has `images/` and `annotations/` directories. Annotation
files match image stems: masks use `.png` or `.jpg`, YOLO boxes use `.txt`, and
classification labels use `.json`; `names.yaml` records class indices. The data
source dispatch in `data/fetch.py` must resolve every source to this layout.

Always use 2D data when writing tests or examples of models. Never use 1D or
flat inputs.
