FROM python:3.12-slim

RUN python3 -m pip install --no-cache-dir "dvc-gs>=3.1.0"

COPY src/sightkit_learn/data/dataset_artifact.py /opt/feral-vision/src/sightkit_learn/data/dataset_artifact.py
COPY feral-vision/scripts/cloud/publish_dataset_artifact.sh /usr/local/bin/publish-dataset-artifact

RUN chmod 0755 /usr/local/bin/publish-dataset-artifact

ENV PYTHONPATH=/opt/feral-vision/src

ENTRYPOINT ["/usr/local/bin/publish-dataset-artifact"]
