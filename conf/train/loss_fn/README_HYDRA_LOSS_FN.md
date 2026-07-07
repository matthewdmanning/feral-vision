# Loss Function Config Group (`conf/train/loss_fn/`)

Each file in this directory is a self-contained Hydra config for a PyTorch loss function.
Select one at runtime with `train/loss_fn=<name>`.

---

## Format

Every file must include:

```yaml
_target_: torch.nn.<ClassName>  # fully-qualified class path
<kwarg>: <value>                 # all constructor kwargs
```

No `_partial_` field — loss functions are instantiated directly by
`hydra.utils.instantiate()` with no deferred arguments.

---

## Available variants

| File | Class | Notes |
|---|---|---|
| `cross_entropy.yaml` | `CrossEntropyLoss` | Default. Multi-class; supports `ignore_index` and `label_smoothing`. |
| `bce_with_logits.yaml` | `BCEWithLogitsLoss` | Binary segmentation; numerically stable sigmoid+BCE. |
| `mse.yaml` | `MSELoss` | Regression / reconstruction tasks. |
| `l1.yaml` | `L1Loss` | MAE loss; more robust to outliers than MSE. |
| `nll.yaml` | `NLLLoss` | Expects log-probabilities from `log_softmax`. |

---

## Usage

```bash
# Default (CrossEntropyLoss)
python -m feral_segmentor.training.train

# Switch to BCE for binary segmentation
python -m feral_segmentor.training.train train/loss_fn=bce_with_logits

# Override label smoothing
python -m feral_segmentor.training.train train/loss_fn=cross_entropy train.loss_fn.label_smoothing=0.1
```

---

## Adding a custom loss

Drop a new YAML file — no Python registration required for runtime use:

```yaml
# conf/train/loss_fn/my_loss.yaml
_target_: my_pkg.losses.MyLoss
alpha: 0.25
gamma: 2.0
```

For IDE completion and mypy support, also add a subclass of `LossFnConfig` in
`src/feral_segmentor/config/schema.py` and register it in `store.py`.
