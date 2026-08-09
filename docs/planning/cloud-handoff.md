# Cloud smoke handoff — 2026-07-31

## Current state

### DVC smoke evidence

- The first disposable CPU DVC smoke VM terminated without producing a tracker
  or a fixture under `dvc-smoke/`; it is not validation. Its VM, dedicated
  service account, and temporary prefix binding were removed. The existing
  regional router and NAT remain managed in Terraform state.
- A future DVC smoke uses the existing Compute Engine execution identity named
  by `dvc_smoke_service_account_email`; Terraform must not create a new service
  account. Its temporary object-admin binding is constrained to `dvc-smoke/`.
- Its CPU VM uses the pinned
  `projects/debian-cloud/global/images/debian-13-trixie-v20260727` boot image;
  do not substitute the GPU trainer image or a floating Debian family.
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
  `mobile-training-images` bucket, then stores `dataset-artifact.json` and a
  version-aware `dataset-artifact.dvc` tracker in the same artifact prefix.
  The temporary no-SCM DVC workspace only generates that tracker; it is not a
  training dependency. General operational storage is not a Dataset Artifact
  source; Terraform state remains in its protected operations bucket. The
  revised build integration is implemented but is not yet verified, so do not
  claim a published Dataset Artifact.
- The first execution of that revised build,
  `e0219991-be90-45b0-96fa-9deac071d995`, reached terminal `FAILURE` at
  `2026-07-31T17:19:47Z`. Its sole step exited immediately after pulling the
  digest-pinned image, before a payload or tracker was published. Cloud Logging
  was unreachable from the operator environment, so the precise command error
  remains unobserved; do not retry that same image digest without first
  rebuilding or otherwise inspecting its embedded source/runtime. The replacement
  is the independent DVC-only image described below.
- The source-agnostic split was exercised regionally on 2026-07-31. The minimal
  DVC image build `e0e9c526-b4cf-49d6-bb9a-9b16bc10fb8a` succeeded with digest
  `sha256:49e9662ed0376be69107b4e3543c8ebfbfc90c9ff4b0499ccc600628d09323e8`.
  The final COCO acquisition image build
  `02f1dce0-24f5-4175-8d88-4d464e3eef62` succeeded with digest
  `sha256:47de9228e3c9f143c3db87eed1660463fdb4cec115297e1283f784bc80d60baf`.
- Preparation build `7c922c11-9ceb-42f1-8b1a-3605c1a37ab2` verified the
  acquisition side: FiftyOne downloaded and exported all 800 selected COCO
  images in Cloud Build. Its DVC publication step then failed before writing an
  object because the prior Cloud Build execution identity lacked
  `storage.objects.create` on
  `storage.objects.create`. The POC service account now has scoped access to
  `gs://mobile-training-images/datasets/coco/train2017/`.
  No Dataset Artifact, manifest, or tracker is published. Do not retry until a
  reviewed prefix-scoped writer grant is in place.
- The first split build exposed the image-specific prerequisites now addressed:
  Cloud Build starts image commands in `/workspace`, so the COCO entrypoint
  explicitly changes to its embedded `/opt/feral-vision` source; FiftyOne also
  requires a MongoDB runtime, now included only in the COCO acquisition image.
- Terraform state and Cloud Build staging share the regional operations bucket
  `feral-vision-operations-us-east4`, separated by `terraform/` and
  `cloudbuild/` prefixes with prefix-scoped IAM. Dataset archives use the
  separate `mobile-training-images` bucket.
- The preparation configuration is `deploy/cloudbuild.prepare.yaml`. It runs a
  source-specific acquisition image and a source-agnostic DVC publication image
  in the shared source-less Cloud Build workspace. Both `_ACQUISITION_IMAGE`
  and `_DVC_IMAGE` must be immutable digests; do not use a PyTorch/CUDA training
  image or a mutable tag for either step.
- `deploy/Dockerfile.dvc` is now the minimal publication image: Python 3.12,
  DVC-GCS, its Cloud Storage Python dependency, and the publication entrypoint.
  It deliberately has no FiftyOne, OpenCV libraries, `uv`, or Cloud Storage
  CLI. `deploy/Dockerfile.coco-acquire` is the separate COCO/FiftyOne image,
  built through `deploy/cloudbuild.coco-acquire-image.yaml`.
- An acquisition image must write `/workspace/payload/images/`,
  `/workspace/payload/annotations/`, and `/workspace/dataset-input.json`.
  The DVC image validates and publishes that payload, writes its manifest, and
  generates the tracker in a temporary no-SCM workspace. A new source only
  implements this workspace contract; it does not modify the DVC image.
- `_DATASET_ARTIFACT_PREFIX` is a required build-time choice and must name a
  new reviewed prefix. It is not defaulted, so no Cloud Build run can silently
  overwrite a Dataset Artifact selected by training.
- Cloud Build staging required the execution identity
  `feral-vision-ai@cs-poc-kewg0kffb7uwobgq1rex2af.iam.gserviceaccount.com` to have
  `roles/storage.objectViewer` on the Cloud Build staging bucket. The
  identity already has the approved cross-project archive-bucket access.
- `deploy/cloudbuild.training-image.yaml` is the targeted rebuild path. It
  builds only the GCP image layer against the resolved base digest, avoiding a
  needless full base-image rebuild when only `deploy/Dockerfile.gcp` changes.

- Target build project: `cs-poc-kewg0kffb7uwobgq1rex2af`; Artifact Registry and Compute
  region: `us-east4`; intended zone: `us-east4-c`.
- Regional Cloud Build `19d6e4c5-d447-4fe4-8d88-60134fdb7622` succeeded at
  `2026-07-28T22:39:01Z`. It published the custom two-stage training image as
  `us-east4-docker.pkg.dev/cs-poc-kewg0kffb7uwobgq1rex2af/feral-docker/feral-vision-gcp@sha256:9a128b33b2e040e79eb2ce237533775a310b54e435c559c6ff33af4aa3e2e67c`.
- Terraform plans and creates the VM only with that digest-pinned image. Do
  not use the mutable `:smoke` tag.
- No Compute instance was visible in the selected target project at the latest
  API check. Do not infer Terraform state from that observation; inspect the
  intended state backend before any apply.
- Terraform state is remote in the existing `feral-vision-smoke` bucket under
  `terraform/cloud-smoke`. The bucket belongs to
  the POC project, so the workload configuration treats it as an external data
  source rather than recreating it.
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

- `feral-vision-ai@cs-poc-kewg0kffb7uwobgq1rex2af.iam.gserviceaccount.com`

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

- `scripts/cloud/image_operations.sh` submits Cloud Build with the configured
  region; this keeps future builds in `us-east4`.
- `.gcloudignore` keeps Cloud Build source submissions small and honors
  `.gitignore`; do not remove its include directive or send local caches/data.
- `deploy/cloudbuild.prepare.yaml` is the remote-only bounded COCO publication
  workflow. It uses a shared workspace contract and accepts only immutable
  acquisition/DVC image digests; its DVC image has no COCO acquisition runtime.
- `deploy/Dockerfile.coco-acquire` and
  `deploy/cloudbuild.coco-acquire-image.yaml` own the current COCO/FiftyOne
  acquisition image, including its MongoDB runtime. Other download sources add
  their own acquisition image and preserve the same `/workspace/payload` plus
  `dataset-input.json` contract.
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

1. Grant the existing Cloud Build execution identity
   `feral-vision-ai@cs-poc-kewg0kffb7uwobgq1rex2af.iam.gserviceaccount.com` the minimum reviewed
   read/write permissions required by DVC on a new
   `datasets/coco/train2017/<revision>/` prefix in `mobile-training-images`.
   The grant must include `storage.objects.create`; verify the DVC tracker also
   has the required read/list access before retrying. Do not broaden bucket IAM
   without review.
2. Submit the regional preparation build with the recorded immutable image
   digests and a new reviewed `_DATASET_ARTIFACT_PREFIX`. Verify its `payload/`,
   `dataset-artifact.json`, and version-aware `dataset-artifact.dvc` before
   allowing the VM to consume them.
3. Keep the T4 request paused until capacity returns. On a future retry,
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
