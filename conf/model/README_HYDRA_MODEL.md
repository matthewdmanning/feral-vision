# Model Configuration (`conf/model/`)

This directory defines **model configuration** used by the project.
Each YAML file in this directory is a **Hydra config variant** that specifies *which model is used* and *how it is instantiated*,
including its core hyperparameters.

The intent is to keep model definition **declarative, reproducible, and decoupled** from training/runtime logic.

**`conf/model/` is the single source of truth for model definitions.**

## What belongs here

Each model config should describe:

- **Instantiation target**
  - A Hydra `_target_` pointing to the model or LightningModule class.
- **Model Tasks**
  - An iterable `model_tasks` describing the model's intended functions. Examples: `["classification"]`, `["pose", "seg_instance"]`
- **Architecture source**
  - Where the architecture comes from: HF Hub, YOLO Hub, local class, URL, etc.
- **Weights source** (optional)
  - Where weight files come from. Omit or set `null` if weights are included in the architecture or random init is acceptable.
- **Compiled**
  - Whether `target` has been compiled on data or parameters need to be substantiated.
- **Model-specific hyperparameters**
  - Architecture and optimization parameters intrinsic to the model.

Trainer/runtime concerns (epochs, devices, precision, etc.) must not live here.

---

## Schema

Every model config inherits from the `base_model` structured schema (defined in
`src/feral_vision/config/schema.py`) via `defaults: [base_model, _self_]`.

~~~yaml
defaults:
  - _self_

model_tasks:           # CVTask strings declared for the dataset pipeline
  - seg_instance       # e.g. seg_instance | seg_semantic | detection | classification | pose

architecture:
  source: hf_hub       # source adapter key: hf_hub | yolo_hub | local | url | ...
  id: org/repo-name    # hub repo ID, model name, dotted class path, or URL — interpreted by source adapter
  location: models/registry   # local path the fetch stage writes to / reads from

weights:               # null = pretrained included in architecture, or random init
  source: hf_hub
  id:
    - weights.pt       # list of filenames or asset identifiers
  location: models/checkpoints/<name>
~~~

### Field reference

| Field | Required | Notes |
|---|---|---|-| `model_tasks` | no | Empty list is valid; required for `FeralDataset(target_model=...)` |
| `architecture.source` | yes | Discriminator consumed by source adapter registry |
| `architecture.id` | yes | Interpreted by source adapter — not necessarily a filename |
| `architecture.location` | yes | Local cache dir for fetched architecture files |
| `weights` | no | `null` = pretrained included in architecture, or random init |
| `weights.id` | no | List; supports multi-file models |

### Source adapters

| `source` value | Adapter | Notes |
|---|---|---|-| `hf_hub` | `HubSource` | Downloads via `hf_hub_download`; `id` is a HF repo ID |
| `yolo_hub` | *(add adapter)* | `id` is a YOLO model name e.g. `yolo11m-seg` |
| `local` | *(add adapter)* | `id` is a dotted Python class path |
| `url` | *(add adapter)* | `id` is a direct download URL |

---

## Loading Weights

The fetch-then-load contract:

1. **Fetch stage** (DVC): downloads weights to `weights.location` using the source adapter's `fetch()` method.
2. **Load stage** (training): reads weights from `weights.location` using the source adapter's `load()` method. Raises if weights are missing rather than downloading at runtime.

Source adapter methods per source type:

1. **HF Hub** (`hf_hub`): `snapshot_download(repo_id=..., local_dir=weights.location)` for fetch; `local_files_only=True` for load.
2. **Torch hub** / **YOLO hub**: adapter downloads `.pt` file to `weights.location`.
3. **Local**: no fetch needed; `load()` reads directly from `weights.location`.

---

## Required conventions

- **`architecture` is mandatory** — every model must declare where its architecture comes from.
- **`architecture.source` and `weights.source` may differ** — e.g. local Python class + remote weights.
- **`model_outputs` and per-task metadata are derived from the architecture's properties** — do not store them in config.
- **Model configs must be self-contained** — they should not assume a specific trainer, device, or environment.

---

## LightningModule

- Point `_target_` to a **LightningModule** that encapsulates:
  - the model
  - forward pass
  - loss computation
  - optimizer configuration

This allows the training entrypoint to remain generic and fully config-driven.

## Pure nn.Module

- Training code must wrap or handle optimization explicitly
- the config structure here remains valid

---

## Adding new model variants

1. Copy `base.yaml` to `<model_name>.yaml`
2. Fill in `model_tasks`, `architecture`, and optionally `weights`
3. Add a DVC fetch stage in `dvc.yaml` if weights need downloading

Example for a HF Hub model:

~~~yaml
defaults:
  - base_model
  - _self_

model_tasks:
  - pose
  - detection

architecture:
  source: hf_hub
  id: org/MyModel
  location: models/registry

weights:
  source: hf_hub
  id:
    - model.pt
  location: models/checkpoints/my_model
~~~

## Best practices

- Prefer multiple small variants over one large conditional config.
- Keep model configs free of data- and trainer-specific logic.
- Treat this directory as part of the project's public configuration contract.
- Never modify `base.yaml` files.
