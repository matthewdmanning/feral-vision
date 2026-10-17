#!/bin/sh
# Pre-push: run tests in the Docker deployment image, only after explicit approval.
IMAGE=feral-vision-prepush-test

printf '[pre-push] Build the deployment image and run tests in Docker? [y/N] '
read -r answer < /dev/tty
case "$answer" in
  y|Y|yes|YES) ;;
  *) echo "[pre-push] Not approved. Push aborted."; exit 1 ;;
esac

docker build -f feral-vision/deploy/Dockerfile.gcp -t "$IMAGE" . || exit 1

docker run --rm -v "$PWD:/repo:ro" -w /repo \
  -e UV_PROJECT_ENVIRONMENT=/tmp/venv -e UV_NO_DEV=0 -e PYTHONDONTWRITEBYTECODE=1 \
  --entrypoint bash "$IMAGE" \
  -c 'uv sync --frozen --group dev && /tmp/venv/bin/python -m pytest -q -p no:cacheprovider' \
  || { echo "[pre-push] Docker tests failed. Push aborted."; exit 1; }