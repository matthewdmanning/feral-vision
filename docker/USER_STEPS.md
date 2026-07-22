# Docker/GCE training procedure

This is the operational procedure for the current Docker/GCE path. The required
deployment contract and the first-run readiness gate are defined in
[Product Scope](../docs/planning/product-scope.md). Do not treat this procedure
as a production acceptance runbook until #37, #38, and #20 are complete.

## Deploy persistent MLflow tracking

MLflow run metadata must use Cloud SQL PostgreSQL; a GCS bucket is the artifact
store, not a SQLite filesystem. Create a database and store this Unix-socket
connection URI in Secret Manager:

~~~bash
PROJECT="YOUR_GCP_PROJECT_ID"
REGION="us-central1"
SQL_INSTANCE="${PROJECT}:${REGION}:feral-vision-mlflow"
DB_NAME="mlflow"
DB_USER="mlflow"
DB_PASSWORD="CHOOSE_A_STRONG_PASSWORD"
BUCKET="YOUR_BUCKET_NAME"

gcloud sql instances create feral-vision-mlflow \
    --database-version=POSTGRES_16 --region=${REGION} --project=${PROJECT}
gcloud sql databases create ${DB_NAME} --instance=feral-vision-mlflow --project=${PROJECT}
gcloud sql users create ${DB_USER} --instance=feral-vision-mlflow \
    --password="${DB_PASSWORD}" --project=${PROJECT}
printf 'postgresql://%s:%s@/%s?host=/cloudsql/%s' \
    "${DB_USER}" "${DB_PASSWORD}" "${DB_NAME}" "${SQL_INSTANCE}" \
    | gcloud secrets create mlflow-backend-store-uri --data-file=- --project=${PROJECT}
~~~

Build and deploy the MLflow server. Its Cloud Run service account needs
``roles/cloudsql.client`` and ``roles/storage.objectUser`` on the artifact
bucket.

~~~bash
REPO="feral-vision"
MLFLOW_IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/mlflow:0.1.0"
gcloud builds submit --tag=${MLFLOW_IMAGE} --file=docker/mlflow.Dockerfile .

GCP_PROJECT=${PROJECT} GCS_BUCKET=${BUCKET} CLOUD_SQL_INSTANCE=${SQL_INSTANCE} \
MLFLOW_IMAGE_URI=${MLFLOW_IMAGE} \
MLFLOW_SERVICE_ACCOUNT="MLFLOW_SERVICE_ACCOUNT@${PROJECT}.iam.gserviceaccount.com" \
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/deploy_mlflow.py
~~~

Retrieve the service URL and pass it as ``MLFLOW_TRACKING_URI`` to every
training container.

~~~bash
MLFLOW_TRACKING_URI="$(gcloud run services describe mlflow --region=${REGION} \
    --format='value(status.url)')"
~~~

---

## Build and push a training image

~~~bash
# Fill in your GCP project and region
PROJECT="YOUR_GCP_PROJECT_ID"
REGION="us-central1"          # change if needed
REPO="feral-vision"
TAG="0.1.0"

# Create Artifact Registry repo (one-time)
gcloud artifacts repositories create ${REPO} \
    --repository-format=docker \
    --location=${REGION} \
    --project=${PROJECT}

# Configure Docker auth
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# Build and push
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/trainer:${TAG}"
docker build -f docker/Dockerfile -t ${IMAGE} .
docker push ${IMAGE}

echo "Image: ${IMAGE}"
~~~

---

## Stage an already prepared data artifact and run the container

The VM must use an attached service account with least-privilege access to read
the selected data artifact and write only to the selected MLflow artifact
prefix. Do not place a service-account key file on the VM. The automated
preflight that verifies these requirements is not implemented yet; see
[Product Scope](../docs/planning/product-scope.md).

~~~bash
# On the T4 GCE instance — run once to mount SSD
DEVICE="/dev/disk/by-id/google-local-ssd-0"   # adjust if different
sudo mkfs.ext4 -F ${DEVICE}
sudo mkdir -p /mnt/disks/ssd
sudo mount ${DEVICE} /mnt/disks/ssd
sudo chmod a+w /mnt/disks/ssd

# Prepare and version data outside this container. The selected prefix must
# contain images/, annotations/, and its data.dvc tracker. The container stages
# these files and never invokes DVC itself.
gcloud storage cp data.dvc gs://${BUCKET}/train/data.dvc

# Run training container (on the T4 instance)
IMAGE="REGION-docker.pkg.dev/PROJECT/feral-vision/trainer:0.1.0"
docker run --gpus all \
    -v /mnt/disks/ssd:/data \
    -e GCS_BUCKET="YOUR_BUCKET_NAME" \
    -e GCS_DATA_PREFIX="train" \
    -e DATA_DIR="/data/train" \
    -e MLFLOW_TRACKING_URI="https://YOUR_MLFLOW_SERVICE-REGION.a.run.app" \
    -e RUN_RECIPE="baseline" \
    -e HYDRA_OVERRIDES="train.epochs=50 train.batch_size=16" \
    ${IMAGE}
~~~

When the tracking endpoint is reachable, the container attempts to record
metrics and the selected best model artifact in MLflow. The shared Cloud Run
service stores run metadata in Cloud SQL and artifacts in its configured GCS
bucket. Do not copy checkpoints or SQLite database files to a parallel GCS
location.
