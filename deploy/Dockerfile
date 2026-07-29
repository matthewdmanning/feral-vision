ARG PYTORCH_IMAGE=pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime
FROM ${PYTORCH_IMAGE}

RUN apt-get update && apt-get install -y \
    git curl wget unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -Ls https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /workspace
COPY . /workspace

RUN uv sync

ENV PYTHONUNBUFFERED=1 \
    OMP_NUM_THREADS=1
