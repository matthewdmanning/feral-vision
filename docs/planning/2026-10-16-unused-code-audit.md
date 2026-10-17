# Unused code audit and removal

Scope: existing `src/`, `scripts/`, and their imports, configuration strings,
exports, shell/deployment entrypoints, tests' reference strings, and current
operator/API documentation. The user requested this audit after the independent
DVC rewrite was committed and pushed as `703d916`. A read-only subagent audit
proposed deletions; the main agent independently checked the references before
applying them. No cloud operations, model acquisition, or Dataset changes were
performed.

## Removed

| Code | Evidence |
| --- | --- |
| `src/feral_vision/data/creator.py` and `FeralDataset.py` | Duplicate Dataset prototypes differing only by a comment; no imports, package exports, configuration targets, or current API/guide references. Remaining mentions were a historical coverage report and a mypy exclusion. |
| `scripts/augment.py` | No caller, launcher, build/deployment reference, or operator documentation. Imports six project augmentation classes that no longer exist, so it cannot start. Current augmentation uses the retained `data.augmentations` functions and preview app. |
| `feral_vision.utils.timing` | No callers, decorators, re-exports, or documented API references. Removed its `functools` and `time` imports. |
| `feral_vision.io_utils.load_image`, `save_image`, `read_json`, `write_json` | No consumers, re-exports, or API documentation. Removed these unused wrappers and their `json`/`Any` imports; retained the Dataset image/index/annotation I/O. |
| `pyproject.toml` mypy exclusion | Referenced only the deleted `creator.py`; removed the stale exclusion and explanatory comment. |

Total: three orphaned files and five unused helpers removed; 871 lines deleted
from existing code/configuration. The independent rewrite's `read_json` is a
separate, actively used function and is retained.

## Retained and why

The current training loader is
`training.trainer -> io_utils.DatasetSource -> data.dataset.AnnotationDataset`.
None of the deleted Dataset prototypes participate in that path.
`utils.get_logger` and `to_dtype` still have callers and remain available.

The old DVC registration and publication code is still used:

- `scripts/data/register.sh` remains documented in the Dataset guide,
  quickstart, program flow, and agent data guidance.
- `deploy/cloudbuild.prepare.yaml` selects the acquisition/publisher images;
  their scripts use `pull_coco_train2017.py` and `data.dataset_artifact`.
- `materialize_detection_variant.sh` calls the retained COCO and augmentation
  functions. Its documented missing publisher integration is a defect, not
  evidence that the path is unused.

`data.schema_convert`, `feral_vision.main`, and `conf/schemas/appearance.yaml`
were inspected but retained. The Python modules expose standalone entrypoints;
no internal references alone do not establish disuse by operators. The absent
JSON example input in `schema_convert` is insufficient grounds to remove a
converter accepting caller-supplied input. No dependencies were removed on the
basis of this bounded audit.

## Validation and limits

- Existing regression tests: **51 passed** across `test_dataset_loading.py`,
  `test_augmentations.py`, and `test_annotations.py`.
- Ruff lint passed over `src/` and `scripts/`; formatting checks passed for the
  two modified Python modules. `git diff --check` passed.
- Mypy passed: no issues in all 37 remaining source files.
- No dangling imports, configuration references, current guide/API references,
  or deployment references to the deleted modules/script were found.
- No Python tests were written or reviewed: the required `write-python-test`
  skill remains unavailable. Existing tests were executed unchanged.
- Guide-impact check: no documented operator workflow or documented API was
  removed; current operator/API guides need no updates. Historical audit
  documents remain historical evidence and were not rewritten.

Tests ran in project-root trial
`.unused-code-audit-279cecf2-cfe2-464c-bd8c-a82e8ca8aaa7/`, with an operations
document, an exact local ignore entry, bounded test commands, and pytest
temporary paths inside that tree. The generated mypy cache was removed too. `data/augmented/` is absent, so these were existing
synthetic-fixture regression tests rather than a supplied-data trial. The trial
and its ignore entry are removed after validation.

The audit establishes absence of repository consumers for the removed code;
it does not inspect unknown external checkouts or operator history. No training,
production GCS, or Terraform execution was used as a discovery mechanism.
