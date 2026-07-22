# Docker and MLflow setup

This document retains image and MLflow setup instructions. The former Docker/GCE
launch orchestration is deprecated; there is no supported first-run procedure
until the readiness work in [Product Scope](../docs/planning/product-scope.md)
is complete.

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
