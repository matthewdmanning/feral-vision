# Optimizer Config Group (`conf/train/optim/`)

Each file in this directory is a self-contained Hydra config for a PyTorch optimizer.
Select one at runtime with `train/optim=<name>`.

---

## Format

Every file must include:

```yaml
_target_: torch.optim.<ClassName>   # fully-qualified class path
_partial_: true                      # always true — instantiated with model.parameters() at runtime
<kwarg>: <value>                     # all constructor kwargs except params
```

`_partial_: true` tells `hydra.utils.instantiate()` to return a `functools.partial`
rather than a live object. The training loop calls `opt_factory(model.parameters())`
to complete instantiation.

---

## Available variants

| File | Class | Notes |
|---|---|---|
| `adamw.yaml` | `torch.optim.AdamW` | Default. Decoupled weight decay. |
| `adam.yaml` | `torch.optim.Adam` | Standard Adam; weight_decay=0. |
| `sgd.yaml` | `torch.optim.SGD` | Momentum SGD; classic for CNNs. |
| `rmsprop.yaml` | `torch.optim.RMSprop` | Adaptive; useful for RNNs/recurrent heads. |
| `radam.yaml` | `torch.optim.RAdam` | Rectified Adam; stable early training. |

---

## Usage

```bash
# Default (AdamW)
python -m feral_segmentor.training.train

# Switch to SGD
python -m feral_segmentor.training.train train/optim=sgd

# Override a specific field
python -m feral_segmentor.training.train train/optim=adamw train.optim.lr=3e-4
```

---

## Adding a custom optimizer

Drop a new YAML file — no Python registration required for runtime use:

```yaml
# conf/train/optim/my_optim.yaml
_target_: my_pkg.optimizers.MyOptimizer
_partial_: true
lr: 1e-3
my_kwarg: 0.9
```

For IDE completion and mypy support, also add a subclass of `OptimConfig` in
`src/feral_segmentor/config/schema.py` and register it in `store.py`.
