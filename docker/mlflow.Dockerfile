FROM ghcr.io/mlflow/mlflow:v3.14.0-full

RUN pip install --no-cache-dir google-cloud-storage psycopg2-binary

CMD ["sh", "-c", "exec mlflow server --backend-store-uri \"$MLFLOW_BACKEND_STORE_URI\" --artifacts-destination \"$MLFLOW_ARTIFACT_ROOT\" --host 0.0.0.0 --port \"${PORT:-8080}\""]
