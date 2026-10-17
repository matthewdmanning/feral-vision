# MLflow PyTorch publication and inference

Native publication preserves the model's prediction contract. The project's
[training guide](../guide/training.rst) and [inference guide](../guide/inference.rst)
are authoritative for its Hydra configuration and structured CV outputs.

## Native model example

An input example and signature are optional for pickle publication:

```python
import mlflow
import mlflow.pytorch
import torch
from torch import nn

model = nn.Conv2d(3, 2, kernel_size=1).eval()
with mlflow.start_run():
    info = mlflow.pytorch.log_model(
        model, name="pytorch_model", serialization_format="pickle"
    )

loaded = mlflow.pytorch.load_model(info.model_uri)
with torch.inference_mode():
    predictions = loaded(torch.randn(2, 3, 32, 32))
```

Models returning dictionaries, lists, tuples, or provider output objects use
the same native publication/loading path. Do not require tensor-to-NumPy output
conversion or a serving signature of every CV model.

## Optional tensor-serving signature

For a model whose serving contract is a tensor, an explicit signature and
example can describe that interface. This example is specific to the tensor
model above:

```python
from mlflow.models import infer_signature

input_example = torch.randn(2, 3, 32, 32)
with torch.inference_mode():
    tensor_predictions = model(input_example)
signature = infer_signature(input_example.numpy(), tensor_predictions.numpy())

with mlflow.start_run():
    mlflow.pytorch.log_model(
        model,
        name="tensor_serving_model",
        serialization_format="pickle",
        signature=signature,
        input_example=input_example.numpy(),
    )
```

The standard MLflow PyTorch pyfunc wrapper has a separate tensor-serving
contract. Supplying an example may invoke MLflow's own signature inference or
serving validation; absence of a project inference pass does not disable those
upstream checks. Exported `pt2` models have additional example/signature rules.
See the [official API](https://mlflow.org/docs/latest/api_reference/python_api/mlflow.pytorch.html)
and [PyTorch examples](https://mlflow.org/docs/latest/ml/deep-learning/pytorch/index.html).
