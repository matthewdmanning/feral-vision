# Modules

This document is the authority for the module layout of this repository.
The released library, starter assets, and project implementation follow this split.

## Top-level groups

| Group | Location | In release | Rule |
| --- | --- | --- | --- |
| Library | `src/sightkit_learn/` | Yes | Generic vision-learning code. Not specific to Feral Vision. Imports nothing outside `src/sightkit_learn/`. |
| Templates | `src/templates/` | Yes | Starter files that help users create their own production folder. Nothing imports from it. |
| Production | `feral-vision/` | No | A copy of `src/templates/`, adapted for the Feral Vision project. |
| Development tools | All other paths | No | Not modules. Examples: `pyproject.toml`, `uv.lock`, `tests/`, `docs/`, agent files, `vscode/`. |

**Library**: distribution name `sightkit-learn`, import name `sightkit_learn`.

**Ignored for now**: `mcp/` is a separate tool. It gives agents access to
Hugging Face model signatures.

## Responsibilities after migration

The library retains the training loop, loss execution, inference, annotation
readers, model providers, and generic dataset publication helpers. Hydra
configuration is supplied by the caller; the released trainer does not discover
a repository recipe or choose the Feral Vision experiment.

The concrete COCO animal acquisition (`scripts/fetch.py`), cat-versus-other
conversion (`scripts/coco_detection.py`), and example run logging
(`scripts/log_run.py`) belong in production and starter assets. The preview app,
its reference JSON, schema conversion, and local validation launchers live under
`tools/`. Tests import these implementation files only to verify the retained
workflows; library imports never reach them.

`uv build` includes both library code and non-Python starter assets. It excludes
`feral-vision/`, `tools/`, and tests from the wheel. Copy the starter tree before
editing its recipes and cloud placeholders; it is not a runtime dependency of
the library. Existing `feral_vision.*` MLflow metadata keys remain stable for
persisted records even though Python imports now use `sightkit_learn`.

## Templates tree

`feral-vision/` has the same tree as `src/templates/`.

| Folder | Contents |
| --- | --- |
| `scripts/` | Workflow entry points. |
| `conf/` | Hydra configuration. |
| `terraform/` | Cloud resources. |
| `deploy/` | Container and image build files. |
| `data/` | Local working copy of Datasets. DVC fills it from the remote. |
| `models/` | Model cards and model tracking outputs. |

### `data/`

- The storage bucket is the DVC remote for production data.
- Local tests use a small example Dataset from the same DVC registry.
- Local and cloud runs use the same path. Only the Hydra dataset configuration changes.
- Library test fixtures stay in `tests/`. They are development tools.

### `models/`

- `models/` is an abstract resource. Code reaches it only through an interface.
- The local folder `models/` is one implementation. It is the default, and development uses it.
- A remote store is a second implementation of the same interface. It is not implemented.
