# Train Config Group (`conf/train/`)

This directory defines training configuration composed from four concerns:
runtime knobs (`base.yaml`) and three swappable sub-groups (optimizer, scheduler, loss function).

---

## Structure

```text
<<<<<<< HEAD
config/trainer/
  README.md
  base.yaml
  fast_dev.yaml            # quick sanity/CI runs

  callbacks/
    README.md
    base.yaml              # standard callbacks
    minimal.yaml           # optional: fewer callbacks
=======
conf/train/
  base.yaml              # runtime knobs + default sub-group selections
  fast_dev.yaml          # CI / quick-iteration override (inherits base)

  optim/                 # optimizer configs — see README_HYDRA_OPTIM.md
    adamw.yaml           # default
    adam.yaml
    sgd.yaml
    rmsprop.yaml
    radam.yaml

  scheduler/             # LR scheduler configs — see README_HYDRA_SCHEDULER.md
    cosine.yaml          # default
    linear.yaml
    step.yaml
    plateau.yaml
    warmrestarts.yaml

  loss_fn/               # loss function configs — see README_HYDRA_LOSS_FN.md
    cross_entropy.yaml   # default
    bce_with_logits.yaml
    mse.yaml
    l1.yaml
    nll.yaml
>>>>>>> adb4359 (feat(config): harmonize Hydra train sub-configs with swappable component pattern)
```

---

## `base.yaml`

Holds runtime knobs and selects one default from each sub-group:

```yaml
defaults:
  - base_train            # merges onto TrainConfig structured schema
  - optim: adamw
  - scheduler: cosine
  - loss_fn: cross_entropy

epochs: 50
batch_size: 32
num_workers: 0
device: cuda
```

Override a sub-group at the CLI without touching this file:

```bash
python -m feral_segmentor.training.train train/optim=sgd
python -m feral_segmentor.training.train train/scheduler=plateau
python -m feral_segmentor.training.train train/loss_fn=bce_with_logits
```

---

## `fast_dev.yaml`

Inherits `base` and overrides only the run knobs for CI / quick iteration:

```yaml
defaults:
  - base
  - _self_

epochs: 1
batch_size: 2
device: cpu
num_workers: 0
```

Use with: `train=fast_dev`

---

## Sub-group design

Each sub-group YAML is **self-contained** — it includes `_target_`, `_partial_`
(where applicable), and all constructor kwargs. No registration is required to
use a variant at runtime; registration in `store.py` is for static type checking only.

See the README in each sub-folder for format details and instructions on adding
custom variants.

---

## Best practices

<<<<<<< HEAD
- Keep training logic in code; keep runtime knobs and callback wiring in config.
- Prefer small, composable variants over large monolithic configs.
- Use `fast_dev.yaml` for quick feedback and CI smoke runs.
- Keep checkpoint paths anchored at repo root via `${paths.checkpoints_dir}` (safe with Hydra `chdir=true`).

---

## Usage examples

```bash
# Default training configuration
python -m src.feral-segmentor.core.train

# Quick dev run
python -m src.feral-segmentor.core.train trainer=fast_dev

# Override runtime parameters
python -m src.feral-segmentor.core.train trainer.max_epochs=50 trainer.precision=16
```
=======
- Override fields at the CLI for quick experiments; create a named variant for reproducible runs.
- Never modify `base.yaml` defaults directly — use a named experiment preset under `conf/experiment/`.
- `T_max` in `cosine.yaml` should match `epochs`; sync them via CLI override:
  `train.scheduler.T_max=100 train.epochs=100`
>>>>>>> adb4359 (feat(config): harmonize Hydra train sub-configs with swappable component pattern)
