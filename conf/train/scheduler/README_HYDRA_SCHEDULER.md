# Scheduler Config Group (`conf/train/scheduler/`)

Each file in this directory is a self-contained Hydra config for a PyTorch LR scheduler.
Select one at runtime with `train/scheduler=<name>`.

---

## Format

Every file must include:

```yaml
_target_: torch.optim.lr_scheduler.<ClassName>  # fully-qualified class path
_partial_: true                                   # always true — instantiated with optimizer at runtime
<kwarg>: <value>                                  # all constructor kwargs except optimizer
```

`_partial_: true` tells `hydra.utils.instantiate()` to return a `functools.partial`
rather than a live object. The training loop calls `sched_factory(optimizer)`
to complete instantiation.

---

## Available variants

| File | Class | Notes |
|---|---|---|
| `cosine.yaml` | `CosineAnnealingLR` | Default. `T_max` matches `cfg.train.epochs`. |
| `linear.yaml` | `LinearLR` | Linear warmup from `start_factor` to `end_factor`. |
| `step.yaml` | `StepLR` | Decays LR by `gamma` every `step_size` epochs. |
| `plateau.yaml` | `ReduceLROnPlateau` | Reduces LR when a metric stops improving. |
| `warmrestarts.yaml` | `CosineAnnealingWarmRestarts` | Cosine with periodic restarts (SGDR). |

---

## Usage

```bash
# Default (CosineAnnealingLR)
python -m feral_segmentor.training.train

# Switch to StepLR
python -m feral_segmentor.training.train train/scheduler=step

# Override T_max to match a short run
python -m feral_segmentor.training.train train/scheduler=cosine train.scheduler.T_max=10
```

---

## Adding a custom scheduler

Drop a new YAML file — no Python registration required for runtime use:

```yaml
# conf/train/scheduler/my_sched.yaml
_target_: my_pkg.schedulers.MyScheduler
_partial_: true
my_kwarg: 0.5
```

For IDE completion and mypy support, also add a subclass of `SchedulerConfig` in
`src/feral_segmentor/config/schema.py` and register it in `store.py`.
