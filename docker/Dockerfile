FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps: Python 3.12, curl for gcloud installer, libGL for OpenCV.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.12 \
        python3.12-dev \
        python3-pip \
        curl \
        gnupg \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Make python3.12 the default python/pip.
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1 \
    && update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1

# Google Cloud SDK (for gcloud storage rsync).
RUN curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
        gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] \
        https://packages.cloud.google.com/apt cloud-sdk main" \
        > /etc/apt/sources.list.d/google-cloud-sdk.list && \
    apt-get update && apt-get install -y --no-install-recommends google-cloud-cli \
    && rm -rf /var/lib/apt/lists/*

# Python deps: torch (CUDA 12.1 wheel), ultralytics pinned, project deps.
RUN pip install --upgrade pip && \
    pip install \
        torch==2.3.1+cu121 \
        torchvision==0.18.1+cu121 \
        --index-url https://download.pytorch.org/whl/cu121

RUN pip install \
        "ultralytics==8.3.0" \
        "pycocotools>=2.0" \
        "hydra-core" \
        "omegaconf" \
        "mlflow" \
        "opencv-python-headless>=4.13"

# Install feral-vision package.
WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install -e .

# Entrypoint and project-specific training workflow.
COPY docker/entrypoint.sh /entrypoint.sh
COPY scripts/container_train.sh /container_train.sh
RUN chmod +x /entrypoint.sh /container_train.sh

# /data is the SSD mount point: docker run -v /mnt/disks/ssd:/data
VOLUME ["/data"]

ENTRYPOINT ["/entrypoint.sh"]
