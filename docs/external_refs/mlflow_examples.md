# MLFlow Examples

## Server Setup

The MLFlow tracking server must be created using the bash command `mlflow server`.

For locally hosted servers, add:

`--host 0.0.0.0 --port 5000`

Two storage backend types are supported:

Local filesystem:
`--backend-store-uri <backend_folder_path>`
SQL Server
`--backend_store_uri <database-connect-string>`

Artifacts destination is set with the `--artifacts-destination` flag.

## MLFlow PyTorch Logging

To manually log a PyTorch model in MLflow, use the `mlflow.pytorch.log_model()` function inside an active run block.

## Basic Command

```python
mlflow.pytorch.log_model(model, name="model_name")

```

## Logging with Signatures (Recommended)

For better model understanding and smoother deployment, it is highly recommended to log the model along with its input and output signatures:

```python
from mlflow.models import infer_signature

# Generate a sample input and get predictions
input_example = torch.randn(1, 784)
predictions = model(input_example)

# Infer the signature from the numpy equivalents
signature = infer_signature(input_example.numpy(), predictions.detach().numpy())

with mlflow.start_run():
    # Log the model with the signature and an input example
    mlflow.pytorch.log_model(
        model,
        name="pytorch_model",
        signature=signature,
        input_example=input_example.numpy()
    )

```
