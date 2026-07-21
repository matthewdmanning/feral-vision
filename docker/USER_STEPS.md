# User Action Required: GCS + Docker + T4 Setup

Three steps need your input/credentials. Run them in order.

---

## Task 2 — Convert annotations, split, and push to GCS

Fill in your bucket name, then run:

~~~bash
# 1. Convert COCO annotations to YOLO annotation files
python -m feral_vision.data.coco_to_yolo \
    --ann data/raw/annotations/coco_train2017/instances_train2017_animals.json \
    --out data/raw/annotations/yolo_train2017/ \
    --names data/raw/annotations/names.yaml

# 2. Split into train/val (80/20, seeded)
python - <<'EOF'
import random, shutil
from pathlib import Path

SEED = 42
VAL_RATIO = 0.2
SRC_IMAGES = Path("data/raw/images/coco_train2017")
SRC_ANNOTATIONS = Path("data/raw/annotations/yolo_train2017")

all_stems = sorted(p.stem for p in SRC_IMAGES.glob("*.jpg"))
random.seed(SEED)
random.shuffle(all_stems)
n_val = int(len(all_stems) * VAL_RATIO)
val_stems = set(all_stems[:n_val])
train_stems = set(all_stems[n_val:])

for split, stems in [("train", train_stems), ("val", val_stems)]:
    split_root = Path(f"data/split/{split}")
    for stem in stems:
        img_src = SRC_IMAGES / f"{stem}.jpg"
        annotation_src = SRC_ANNOTATIONS / f"{stem}.txt"
        (split_root / "images").mkdir(parents=True, exist_ok=True)
        (split_root / "annotations").mkdir(parents=True, exist_ok=True)
        if img_src.exists(): shutil.copy2(img_src, split_root / "images" / f"{stem}.jpg")
        if annotation_src.exists(): shutil.copy2(annotation_src, split_root / "annotations" / f"{stem}.txt")

    shutil.copy2("data/raw/annotations/names.yaml", split_root / "annotations/names.yaml")

print(f"train: {len(train_stems)}, val: {len(val_stems)}")
EOF

# 3. Push to GCS  ← FILL IN YOUR BUCKET NAME
BUCKET="YOUR_BUCKET_NAME"
for SPLIT in train val; do
    gcloud storage rsync -r data/split/${SPLIT}/images/ gs://${BUCKET}/${SPLIT}/images/
    gcloud storage rsync -r data/split/${SPLIT}/annotations/ gs://${BUCKET}/${SPLIT}/annotations/
done
~~~

---

## Task 8 — Build and push Docker image to Artifact Registry

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

## Task 9 — Configure T4 instance and run container

~~~bash
# On the T4 GCE instance — run once to mount SSD
DEVICE="/dev/disk/by-id/google-local-ssd-0"   # adjust if different
sudo mkfs.ext4 -F ${DEVICE}
sudo mkdir -p /mnt/disks/ssd
sudo mount ${DEVICE} /mnt/disks/ssd
sudo chmod a+w /mnt/disks/ssd

# Grant service account GCS access (run from your local machine)
PROJECT="YOUR_GCP_PROJECT_ID"
BUCKET="YOUR_BUCKET_NAME"
SA="$(gcloud compute instances describe YOUR_INSTANCE_NAME \
    --format='value(serviceAccounts[0].email)')"
gcloud storage buckets add-iam-policy-binding gs://${BUCKET} \
    --member="serviceAccount:${SA}" \
    --role="roles/storage.objectAdmin"

# Run training container (on the T4 instance)
IMAGE="REGION-docker.pkg.dev/PROJECT/feral-vision/trainer:0.1.0"
docker run --gpus all \
    -v /mnt/disks/ssd:/data \
    -e GCS_BUCKET="YOUR_BUCKET_NAME" \
    -e GCS_DATA_PREFIX="train" \
    -e DATA_DIR="/data/train" \
    -e MLFLOW_ARTIFACT_PREFIX="mlflow" \
    -e RUN_RECIPE="baseline" \
    -e HYDRA_OVERRIDES="train.epochs=50 train.batch_size=16" \
    ${IMAGE}
~~~

The container records metrics and the best checkpoint in its MLflow run. MLflow
stores those artifacts under the runtime-selected artifact prefix; when the
container exits, it also synchronizes the MLflow backend store to
`${MLFLOW_ARTIFACT_PREFIX}/tracking/`. Do not copy checkpoints to a parallel
GCS location.
