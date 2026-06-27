# User Action Required: GCS + Docker + T4 Setup

Three steps need your input/credentials. Run them in order.

---

## Task 2 — Convert labels + split + push to GCS

Fill in your bucket name, then run:

```bash
# 1. Convert COCO annotations to YOLO label files
python -m feral_segmentor.data.coco_to_yolo \
    --ann data/raw/annotations/coco_train2017/instances_train2017_animals.json \
    --out data/raw/labels/coco_train2017/ \
    --names data/raw/labels/names.yaml

# 2. Split into train/val (80/20, seeded)
python - <<'EOF'
import json, random, shutil
from pathlib import Path

SEED = 42
VAL_RATIO = 0.2
SRC_IMAGES = Path("data/raw/images/coco_train2017")
SRC_LABELS = Path("data/raw/labels/coco_train2017")

all_stems = sorted(p.stem for p in SRC_IMAGES.glob("*.jpg"))
random.seed(SEED)
random.shuffle(all_stems)
n_val = int(len(all_stems) * VAL_RATIO)
val_stems = set(all_stems[:n_val])
train_stems = set(all_stems[n_val:])

for split, stems in [("train", train_stems), ("val", val_stems)]:
    for stem in stems:
        img_src = SRC_IMAGES / f"{stem}.jpg"
        lbl_src = SRC_LABELS / f"{stem}.txt"
        (Path(f"data/split/images/{split}")).mkdir(parents=True, exist_ok=True)
        (Path(f"data/split/labels/{split}")).mkdir(parents=True, exist_ok=True)
        if img_src.exists(): shutil.copy2(img_src, f"data/split/images/{split}/{stem}.jpg")
        if lbl_src.exists(): shutil.copy2(lbl_src, f"data/split/labels/{split}/{stem}.txt")

print(f"train: {len(train_stems)}, val: {len(val_stems)}")
EOF

# 3. Push to GCS  ← FILL IN YOUR BUCKET NAME
BUCKET="YOUR_BUCKET_NAME"
gcloud storage rsync -r data/split/images/ gs://${BUCKET}/images/
gcloud storage rsync -r data/split/labels/ gs://${BUCKET}/labels/
gcloud storage cp data/raw/labels/names.yaml gs://${BUCKET}/labels/names.yaml
```

---

## Task 8 — Build and push Docker image to Artifact Registry

```bash
# Fill in your GCP project and region
PROJECT="YOUR_GCP_PROJECT_ID"
REGION="us-central1"          # change if needed
REPO="feral-segmentor"
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
```

---

## Task 9 — Configure T4 instance and run container

```bash
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
IMAGE="REGION-docker.pkg.dev/PROJECT/feral-segmentor/trainer:0.1.0"
docker run --gpus all \
    -v /mnt/disks/ssd:/data \
    -e GCS_BUCKET="YOUR_BUCKET_NAME" \
    -e HYDRA_OVERRIDES="train.epochs=50 train.batch_size=16" \
    ${IMAGE}
```
