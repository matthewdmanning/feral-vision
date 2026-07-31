# Cloud smoke handoff — 2026-07-30

## Current state

### DVC smoke evidence

- The first disposable CPU DVC smoke VM terminated without producing a tracker
  or a fixture under `dvc-smoke/`; it is not validation. Its VM, dedicated
  service account, and temporary prefix binding were removed. The existing
  regional router and NAT remain managed in Terraform state.
- A future DVC smoke uses the existing Compute Engine execution identity named
  by `dvc_smoke_service_account_email`; Terraform must not create a new service
  account. Its temporary object-admin binding is constrained to `dvc-smoke/`.
- The startup script writes `[DVC_SMOKE]` stage and terminal markers to the
  serial console, including success only after the tracker contains
  `version_id:`. Do not accept VM termination alone as a passing result.
- Guide-impact check: no user-facing guide changes are needed for this
  disposable operator diagnostic.

### Source-less Cloud Build

- Source-less Cloud Build mounts an empty `/workspace`, hiding source embedded
  at that path in a container image. The GCP training image copies its project
  tree to `/opt/feral-vision`, and source-less preparation steps begin there.
  This preserves the archive-free build workflow; do not revert to a local
  source submission merely to make scripts visible.

### Cloud data preparation (latest stable stop)

- All Cloud Build work in this handoff is explicitly regional: `us-east4`.
  Do not submit, inspect, or stream a global build.
- The latest remote-only COCO/DVC preparation build,
  `edfb03d6-3e04-4cc5-b5cb-9f65d4b5a166`, reached terminal `FAILURE` at
  `2026-07-29T21:42:34Z`. It completed the bounded COCO selection, downloaded
  800 images, and exported the image/annotation layout entirely in Cloud
  Build. Nothing was staged in the developer workspace.
- The failure was DVC metadata initialization, not the COCO export: the Cloud
  Build source workspace has no `.git`, and `dvc add` therefore exited with
  `ERROR: /workspace is not a git repository`. The archive rsync and `dvc push`
  steps did not run, so do not claim a published Dataset Artifact.
- The adopted replacement is a bucket-backed Dataset Artifact catalog. Cloud
  Build publishes the dataset payload to the versioned
  `mobile-optimized-images` bucket, then stores `dataset-artifact.json` and a
  version-aware `dataset-artifact.dvc` tracker in the same artifact prefix.
  The temporary no-SCM DVC workspace only generates that tracker; it is not a
  training dependency. General operational storage is not a Dataset Artifact
  source; Terraform state remains in its protected operations bucket. The
  revised build integration is implemented but has not yet been executed, so do
  not claim a published Dataset Artifact.
- Terraform state and Cloud Build staging share the regional operations bucket
  `feral-vision-operations-us-east4`, separated by `terraform/` and
  `cloudbuild/` prefixes with prefix-scoped IAM. Dataset archives use the
  separate `mobile-optimized-images` bucket.
- The preparation configuration is
  `deploy/cloudbuild.prepare.yaml`; it uses the immutable training image
  `us-east4-docker.pkg.dev/feralspotter-f9e51/feral-docker/feral-vision-gcp@sha256:00ab0ba68c7434aa7d378e4fd13e89d12f663c1e7d24847706d7c38351d9fd99`.
  Never replace that reference with `:smoke` for a preparation run.
- The image was rebuilt to provide FiftyOne/OpenCV runtime libraries `libgl1`
  and `libglib2.0-0`. `scripts/pull_coco_train2017.py` now uses
  `export_media=True`, which is compatible with the installed FiftyOne
  version; its prior string value `"copy"` is not.
- Cloud Build staging required the execution identity
  `446310107443-compute@developer.gserviceaccount.com` to have
  `roles/storage.objectViewer` on `gs://feralspotter-f9e51_cloudbuild`. The
  identity already has the approved cross-project archive-bucket access.
- `deploy/cloudbuild.training-image.yaml` is the targeted rebuild path. It
  builds only the GCP image layer against the resolved base digest, avoiding a
  needless full base-image rebuild when only `deploy/Dockerfile.gcp` changes.

- Target build project: `feralspotter-f9e51`; Artifact Registry and Compute
  region: `us-east4`; intended zone: `us-east4-c`.
- Regional Cloud Build `19d6e4c5-d447-4fe4-8d88-60134fdb7622` succeeded at
  `2026-07-28T22:39:01Z`. It published the custom two-stage training image as
  `us-east4-docker.pkg.dev/feralspotter-f9e51/feral-docker/feral-vision-gcp@sha256:9a128b33b2e040e79eb2ce237533775a310b54e435c559c6ff33af4aa3e2e67c`.
- Terraform plans and creates the VM only with that digest-pinned image. Do
  not use the mutable `:smoke` tag.
- No Compute instance was visible in the selected target project at the latest
  API check. Do not infer Terraform state from that observation; inspect the
  intended state backend before any apply.
- Terraform state is remote in the existing `feral-vision-smoke` bucket under
  `terraform/cloud-smoke`. The bucket belongs to
  `project-e3d5659d-bc4f-438f-88c`, so the workload configuration treats it as
  an external data source rather than recreating it in `feralspotter-f9e51`.
  This keeps state isolated from the archived dataset.
- Application Default Credentials initialized the backend successfully. The
  original reviewed plan created the service account, Artifact Registry reader
  binding, bucket object-access binding, and IAP-only SSH firewall. The GPU VM
  did not land. A refreshed plan at
  `/tmp/feral-vision-cloud-smoke-retry.tfplan` now shows only that one VM
  creation, with zero changes and zero destroys; it awaits explicit approval.
- The VM-only retry exposed a retired `pytorch-latest-gpu` image family. It is
  replaced with the verified READY
  `pytorch-2-9-cu129-ubuntu-2204-nvidia-580` family; a fresh plan is required
  before retrying the VM creation. That fresh plan is saved at
  `/tmp/feral-vision-cloud-smoke-image-fix.tfplan` and shows one VM addition,
  zero changes, and zero destroys.
- The image-fix apply reached Compute Engine but was rejected by
  `constraints/compute.vmExternalIpAccess`. The approved default subnet has
  Private Google Access disabled and `us-east4` has no Cloud Router/NAT, so a
  private-only VM cannot currently pull the image or synchronize the archive.
  Choose either a scoped organization-policy exception for the VM external IP
  or a reviewed Cloud NAT addition for the default VPC before retrying. Cloud
  NAT is approved: the VM has no external IP, and the router/NAT is scoped to
  the default `us-east4` subnet. The reviewed plan at
  `/tmp/feral-vision-cloud-smoke-nat.tfplan` shows three additions (private
  GPU VM, Cloud Router, and subnet-scoped Cloud NAT), with zero changes and
  zero destroys; it awaits explicit apply approval.
- The first private-VM attempt confirmed that `us-east4-a` lacks current
  `n1-standard-4` plus T4 capacity despite available quota. `us-east4-b` also
  lacks capacity for the same shape, and `us-east4-c` also rejected it. The
  project has unused T4 quota, so this is regional capacity rather than quota.
  No VM or training run exists. Choose a P4 hardware fallback in the existing
  region, a new region with its own subnet/NAT path, or wait and retry T4
  placement before generating another plan.

## IAM applied

Repository-scoped `roles/artifactregistry.writer` was granted to both Cloud
Build identities observed during this work:

- `446310107443@cloudbuild.gserviceaccount.com`
- `446310107443-compute@developer.gserviceaccount.com`

The second identity is the execution identity recorded on the regional build.
The prior build failures occurred in the Docker step that both builds and pushes
the base image; no detailed build-log entry was available through the API.

## One VM lifecycle

Issue #38 is the single empirical run. Do not split it into a dataset VM and a
training VM:

1. Terraform provisions one GPU VM using the digest-pinned custom image.
2. Startup restores the archived COCO subset from bucket storage to VM SSD.
3. If no archive exists, startup exports the existing bounded subset (the
   Terraform defaults yield 800 images).
4. Startup checks CUDA and runs the baseline GPU training container.
5. Normal shutdown archives the SSD dataset back to bucket storage.

The restore and archive commands use checksum comparison, so identical files
are not copied solely because their timestamps differ. The dataset does not
land in the local developer workspace.

## Local changes to preserve

- `scripts/cloud/build.sh` submits Cloud Build with
  `--region=${REGISTRY_REGION}`; this keeps future builds in `us-east4`.
- `.gcloudignore` keeps Cloud Build source submissions small and honors
  `.gitignore`; do not remove its include directive or send local caches/data.
- `deploy/cloudbuild.prepare.yaml` is the remote-only bounded COCO publication
  workflow. It remains digest-pinned and regional; its present in-workspace DVC
  commands are superseded by the planned DVC-scoped repository integration.
- `deploy/cloudbuild.training-image.yaml` builds the GCP image layer against a
  supplied immutable base-image digest.
- `deploy/Dockerfile.gcp` installs `libgl1` and `libglib2.0-0` for the
  FiftyOne/OpenCV export path.
- `scripts/pull_coco_train2017.py` uses `export_media=True` for the supported
  copy behavior in the installed FiftyOne release.
- `terraform/templates/trainer_startup.sh.tftpl` restores the archived dataset
  before downloading it.
- `terraform/templates/archive_on_shutdown.sh.tftpl` and the restore path use
  `gcloud storage rsync --checksums-only`.

Validation completed: `bash -n scripts/cloud/container_train.sh`,
`terraform fmt -check terraform`, `terraform validate`, `terraform test`, and
the observed Cloud Build boundaries listed above. Preserve unrelated
dirty-worktree changes and stage only the files above when preparing a commit.

## Next commands

1. Confirm Object Versioning and dataset-specific lifecycle and IAM policies on
   `mobile-optimized-images`; do not reuse the Terraform-state or general
   artifact bucket. Submit the revised regional preparation build, then verify
   its `payload/`, `dataset-artifact.json`, and version-aware
   `dataset-artifact.dvc` before allowing the VM to consume them.
2. Keep the T4 request paused until capacity returns. On a future retry,
   generate and review a fresh Terraform plan; do not use the saved plans in
   `/tmp`, and apply only with explicit approval.

## Risks and rollback

- Risk: applying from an unknown or stale state can create duplicate cloud
  resources. The backend is initialized and the saved plan has been reviewed;
  apply only that plan artifact.
- Risk: the only currently observed VPC is the default network. Confirm whether
  it is acceptable before placing the VM there; it was explicitly approved for
  this cloud smoke and remains an overridable Terraform input.
- Risk: the new VM service account receives object administration on the
  cross-project archive bucket so it can restore and archive the COCO subset.
  Keep the binding scoped to this service account and bucket.
- Risk: Cloud NAT provides outbound internet egress for every VM using the
  selected default `us-east4` subnet. Its scope is the subnet rather than the
  entire VPC; use a dedicated subnet before adding unrelated workloads.
- Rollback: if the reviewed VM run fails, preserve its logs and image digest,
  then remove only the resources shown in a reviewed destroy plan. Keep the
  archived dataset unless its retention policy says otherwise.
