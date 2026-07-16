# Architecture — Program Flow

This document is the **single source of truth** for how data becomes a trained model
in this repository. If you are doing architecture or integration work, read this
first. Do not restate, summarize, or re-derive this flow elsewhere (other docs, code
comments, memory files) — link back to this document instead. If code changes make a
section below stale, update this document in the same change.

---

## 1. Data acquisition

`data/fetch.py`, DVC `fetch` stage. `cfg.data.source` selects a fetch strategy and
resolves to the canonical `<root>/images/`, `<root>/annotations/` layout (see
[Dataset Folder Schema](CLAUDE.md#dataset-folder-schema)).

`"coco"` is one example source (`fetch_coco`) among others (`"local"` via
`fetch_data`, and any future remote id). The source is a dispatch point, not a fixed
enum — do not describe or design around `"coco"` as if it were special-cased or the
only supported source.

## 2. Annotation loading

`io_utils.DatasetSource._load_annotation` dispatches by file extension to a
concrete `Annotation` subclass in `data/annotations.py` (`.png/.jpg/.bmp` →
`MaskAnnotation`, `.txt` → `BBoxAnnotation`, etc.). Loaders assume the file is
already in the correct format for its extension — no defensive validation layer.
Malformed files fail naturally inside the loader; that is expected, not a gap to
patch (see the "no redundant guards" convention: only validate at true system
boundaries).

## 3. Augmentation

`data/augmentations.py`. Pure albumentations — a static registry of stock
albumentations transform classes (`_TRANSFORMS`), assembled per `cfg.augmentation`
(`conf/augmentation/default.yaml`) and composed using albumentations' own
composition mechanism directly. There is **no custom Augmentation/Compose wrapper
class** anywhere in this codebase. One existed previously (a hand-rolled fluent
chain class) and was deleted specifically because it replicated logic the
`albumentations` library already provides — do not reintroduce one, and do not
describe this subsystem as if a bespoke composition layer exists.

## 4. Dataset loading

- `io_utils.DatasetSource` — owns all filesystem I/O: scans `images/` +
  `annotations/`, pairs files by stem, dispatches annotation loading. `load(index)
  -> (Tensor, list[Annotation])`.
- `data/dataset.py`'s `AnnotationDataset` / `StreamingAnnotationDataset` — pure
  PyTorch `Dataset`/`IterableDataset` protocol only (`__len__`, `__getitem__`,
  `transform`). Injected with a `DatasetSource`; never touches disk itself.
- `data/annotations.py` — pure data types (`Annotation` and subclasses); no I/O.

## 5. Model acquisition

Each model *source* (HF Hub, torch hub, ultralytics, ...) has a `SourceAdapter`
subclass in `models/sources/` implementing `fetch(cfg) -> nn.Module` and
`inspect(cfg) -> (ModelProperties, dict)`, keyed by a module-level `SOURCE_KEY` and
resolved dynamically via `register_model.get_adapter(source)`. In-repo architectures
(`nn.Module` subclasses defined in this codebase, e.g. `models/default.py`) instead
register into `models/registry.py`'s `@register`/`build_model`/`get_model`
architecture registry, selected by `cfg.model.arch`.

**Weights are independent of architecture source.** `ModelConfig.weights:
Optional[WeightsConfig]` is a separate config branch from
`ModelConfig.architecture: SourceConfig`. This matters for two real cases:

- A custom in-repo `nn.Module` architecture that has no weights of its own and needs
  them fetched from a `WeightsConfig`-declared source.
- Resuming training or loading a previous checkpoint instead of an architecture's
  default/pretrained weights — also a `WeightsConfig`, not a re-fetch of the
  architecture.

`register_model.py`'s `register_model()` / `load_model_registry()` persist a named
model's config + `ModelProperties` to `model_registry.json` at the project root —
the durable metadata store (see [[project-model-registry]]).

## 6. Training — single canonical path

**`training/trainer.py` is the only correct training path.** `build_trainer(cfg)`
wires `build_model` (`models/registry.py`) and `build_optimizer` /
`build_scheduler` / `build_loss_fn` (`training/optim.py`, all thin
`hydra.utils.instantiate` wrappers over `conf/train/{optim,scheduler,loss_fn}/*.yaml`)
into a `Trainer`. `Trainer.fit(dataloader, val_dataset)` runs the epoch loop, logs
each metric to MLflow via `_try_log_metric` (a no-op if no run is active), tracks
the best score, and writes the best checkpoint to `models/registry/best.pt`.

The loss function is config-selected (`conf/train/loss_fn/*.yaml`:
`cross_entropy`, `mse`, `l1`, `nll`, `bce_with_logits`). `training/losses.py`'s
`segmentation_loss` (Dice + CE + optional KL distillation against `teacher_logits`)
is *one possible* loss implementation, not the default, and its distillation branch
is a holdover from the deleted student/teacher model design. Do not describe or
default to `segmentation_loss`/distillation as canonical training behavior.

**`training/train.py` (direct `ultralytics.YOLO(...).train()`) is a known,
non-canonical competing path.** It bypasses `Trainer`/`build_trainer` entirely, so
runs through it are not wired to the same model/optimizer/loss config path as
everything else — this breaks reproducibility (two divergent ways to produce a
"trained model" from the same config). It is **not** a valid alternative flow; it
is an inconsistency to be resolved (removed or folded into `trainer.py`) as a
follow-up. Until then, treat `trainer.py` as the only source of truth for "how
training happens," and flag any doc/config/PR that treats `train.py` as equivalent.

## 7. Tooling boundaries

| Tool | Owns |
|---|---|
| **DVC** | **Data only** — raw, processed, and augmented data artifacts. Never training/evaluation runs, checkpoints, or metrics. |
| **MLflow** | Everything generated by or about a model during a training or inference run: metrics, hardware metrics, checkpoints/model artifacts, run metadata, and the model-version ↔ data-version link for that run. |
| **Scripts / source code** | Workflow control — what actually invokes what. |
| **Hydra** | All tunables live in `conf/`. |
| **`model_registry.json`** | Static model metadata (access point, API params, architecture) — not run-time artifacts. |

"Model artifacts" (anything produced by or describing a specific training/inference
run — checkpoints included) belong to MLflow, never DVC. See
[[dvc-mlflow-integration]] for the linking patterns (log a `.dvc` tracker file or
`dvc.api.get_url()` param into MLflow — never a raw data directory).

**Known gap:** `dvc.yaml` currently declares `train` and `evaluate` stages
(`feral_segmentor.pipelines.*`, a module that no longer exists post-reconciliation).
Per the boundary above, DVC should not own training or evaluation stages at all —
this is a real inconsistency in the pipeline definition, not yet fixed.
