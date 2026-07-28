# Data

Use this guide when changing data ingestion or datasets.

Every dataset root has `images/` and `annotations/` directories. Annotation
files match image stems: masks use `.png` or `.jpg`, YOLO boxes use `.txt`, and
classification labels use `.json`; `names.yaml` records class indices. The data
source dispatch in `data/fetch.py` must resolve every source to this layout.

For the local DVC data pipeline, use `dvc repro` or `dvc pull`.
