# Modules

This document is the authority for the module layout of this repository.
The current code does not conform to it yet.

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
