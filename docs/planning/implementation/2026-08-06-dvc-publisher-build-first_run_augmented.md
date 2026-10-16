# First augmented run publication and image-build evidence

## Scope

This note records the cloud-publication execution after the DVC GCS read
verification, including the successful regional Dataset Artifact preparation
build. It does not claim independent GCS object-listing verification.

## Execution evidence

The active Google Cloud identity was `mattmanningclemson@gmail.com` in project
`cs-poc-kewg0kffb7uwobgq1rex2af`. Artifact Registry had no current
`feral-vision-dvc` image available for the verified raw payload workflow.

The following regional build was submitted:

```bash
gcloud builds submit . --project=cs-poc-kewg0kffb7uwobgq1rex2af --region=us-east4 --config=deploy/cloudbuild.dvc-image.yaml --substitutions=_DVC_IMAGE=us-east4-docker.pkg.dev/cs-poc-kewg0kffb7uwobgq1rex2af/feral-docker/feral-vision-dvc:raw-20260806-800-animals-v2 --quiet
```

Cloud Build ID: `5e533813-b05a-4179-bc28-d998deeefba6`.

The Docker build itself completed and tagged the requested image, but the push
failed with:

```text
denied: Permission 'artifactregistry.repositories.uploadArtifacts' denied
```

The denied resource is the `feral-docker` Artifact Registry repository in
`us-east4`. No image digest was produced, and no dataset-publisher or GCS write
was started.

## IAM authorization result

The operator explicitly authorized a repository-scoped writer grant for the
Cloud Build execution account. The attempted command was:

```bash
gcloud artifacts repositories add-iam-policy-binding feral-docker --location=us-east4 --member=serviceAccount:373124575345-compute@developer.gserviceaccount.com --role=roles/artifactregistry.writer --project=cs-poc-kewg0kffb7uwobgq1rex2af --quiet
```

Google Cloud returned `PERMISSION_DENIED`: the authenticated operator identity
does not have permission to edit the repository IAM policy. The grant was not
applied.

The grant was retried after local ADC refresh and the result was identical:
the active gcloud CLI principal remained `mattmanningclemson@gmail.com` and
Google Cloud again returned `PERMISSION_DENIED`. ADC authentication does not
change the CLI principal used by the IAM command.

## Identity repair identified

The existing custom service account
`feral-vision-ai@cs-poc-kewg0kffb7uwobgq1rex2af.iam.gserviceaccount.com` was
verified as enabled. The failed build instead used the project default Compute
Engine service account. The current operator cannot read `feral-docker` IAM,
so the custom account's current repository roles could not be inspected.

The intended repair is to declare the custom account as the explicit Cloud
Build execution identity and grant that account
`roles/artifactregistry.createOnPushWriter` for the image-publication path.
The account submitting the build also needs `iam.serviceAccounts.actAs` for
that custom account. This keeps the publisher's Registry access on a
purpose-specific identity rather than on the project default Compute Engine
account.

## Current state

**Ready for Cloud Verification.** The corrected publisher and acquisition
images were built and the preparation workflow completed successfully. The
remaining acceptance check is an independent listing and DVC read of the new
GCS artifact prefix.

## Workflow permission inventory

The following inventory is derived from `docs/agents/data.md`,
`docs/agents/cloudops.md`, `deploy/cloudbuild*.yaml`, the publisher script,
and `terraform/runs/detection_first_run_augmented/`.

| Identity | Required role and scope | Evidence |
| --- | --- | --- |
| Selected publisher identity `feral-vision-ai@cs-poc-kewg0kffb7uwobgq1rex2af.iam.gserviceaccount.com` | `roles/artifactregistry.createOnPushWriter` for image publication; Cloud Storage Viewer on the Cloud Build staging bucket; conditional Cloud Storage Viewer plus Creator for the new `datasets/coco/train2017/` artifact prefix | The corrected Cloud Build YAML selects this identity. The Registry role definition includes both create-on-push and artifact upload. |
| Default Cloud Build identity `373124575345-compute@developer.gserviceaccount.com` | No new publisher grant | Historical builds used it only because the configuration omitted `serviceAccount`. Its existing `roles/storage.objectAdmin` on `mobile-training-images` does not make it the selected publisher identity. |
| `data-operations-runner@cs-poc-kewg0kffb7uwobgq1rex2af.iam.gserviceaccount.com` | No publisher grant | It has condition-limited Dataset Artifact GCS access, but is not the documented publisher identity and could not read the Cloud Build staged source object. |
| Detection VM service account, selected at plan time | `roles/artifactregistry.reader` on `feral-docker` and `roles/storage.objectViewer` limited to the immutable Dataset Variant prefix | Required by `trainer_startup.sh.tftpl` to pull the digest-pinned training image and stage `payload/`, manifest, and DVC tracker to VM SSD. The actual service-account email is still a required Terraform input. |
| Terraform operator for the disposable detection VM | Compute instance creation, network attachment, and `roles/iam.serviceAccountUser` on the selected VM account | Required by the detection Terraform root, which creates the private GPU instance and attaches an existing service account. Verify the exact project/subnetwork roles against the resulting plan before apply. |
| MLflow runtime identity | Endpoint-specific write permission only if the managed HTTPS MLflow service requires Google IAM | The run contract requires an HTTPS endpoint but does not define its hosting identity or IAM model; do not grant a generic role until that endpoint is selected. |

Cloud Build log delivery needs no additional manual grant in this inventory: the
existing `CLOUD_LOGGING_ONLY` build emitted logs successfully.

### Role correction

The required Artifact Registry role for the selected
`feral-vision-ai@cs-poc-kewg0kffb7uwobgq1rex2af.iam.gserviceaccount.com`
publisher is `roles/artifactregistry.createOnPushWriter`, not the narrower
Writer role previously recorded. Its live definition includes both
`artifactregistry.repositories.createOnPush` and
`artifactregistry.repositories.uploadArtifacts`.

## Corrected publisher identity

The canonical publisher identity is
`feral-vision-ai@cs-poc-kewg0kffb7uwobgq1rex2af.iam.gserviceaccount.com`, as
recorded in the cloud handoff. The Cloud Build configurations now declare that
identity explicitly. A short-lived attempt to use `data-operations-runner`
was rejected because it could not read the uploaded Cloud Build source object;
that account is not the selected publisher identity.

Besides repository writer access, the selected custom build account must read
the staged source object in `cs-poc-kewg0kffb7uwobgq1rex2af_cloudbuild`. This
is separate from its conditional Dataset Artifact permission on
`mobile-training-images`.

## Post-change verification

After the operator reported that a permission change was made, the DVC image
build `f405465c-2f0d-44a6-9055-0f933b115339` was submitted after an IAM
propagation wait. Docker assembly completed, but the Registry push still
returned `artifactregistry.repositories.uploadArtifacts` denied for
`373124575345-compute@developer.gserviceaccount.com`. That result applies to
the pre-correction configuration, which selected the default identity; it is
not evidence about the documented `feral-vision-ai` publisher account.

## Successful regional publication build

The missing Docker Artifact Registry repository was created at
`us-east4-docker.pkg.dev/cs-poc-kewg0kffb7uwobgq1rex2af/feral-docker`.

The corrected Dataset Artifact Cloud Build configurations select
`feral-vision-ai@cs-poc-kewg0kffb7uwobgq1rex2af.iam.gserviceaccount.com`.
The DVC publisher image build succeeded:

- Build: `435c3b03-b3be-4ba5-a87b-9092f70b2d0f`
- Image: `us-east4-docker.pkg.dev/cs-poc-kewg0kffb7uwobgq1rex2af/feral-docker/feral-vision-dvc@sha256:96e401177b11f2ed67821d90b5726a481ad4c5b214a64d42825e34ac1c126bc6`

The COCO acquisition image build initially exposed a missing
`options.logging: CLOUD_LOGGING_ONLY` declaration required with an explicit
service account. After adding it, the build succeeded:

- Build: `2f7bc457-7c20-409d-b317-753603e7ef4a`
- Image: `us-east4-docker.pkg.dev/cs-poc-kewg0kffb7uwobgq1rex2af/feral-docker/feral-vision-coco-acquire@sha256:81f37791bebb701ba970afa58e508508e88bdf2ed105287db83a2be19734f37d`

The preparation build `bb46c7e9-4360-469b-b58e-6acae88a954c` then completed
with status `SUCCESS` using those immutable image digests and this new artifact
prefix:

`gs://mobile-training-images/datasets/coco/train2017/raw-20260806-800-animals-v2/`

## Successful base and training image build

The first attempt to build the configured base-to-training image graph failed
only when the base image push used the project default Compute Engine service
account. Docker built and tagged the base image successfully; Cloud Build then
returned `artifactregistry.repositories.uploadArtifacts` denied for the
default identity.

`deploy/cloudbuild.build.yaml` was corrected to explicitly select the
documented publisher identity
`feral-vision-ai@cs-poc-kewg0kffb7uwobgq1rex2af.iam.gserviceaccount.com` while
retaining `CLOUD_LOGGING_ONLY`.

The corrected regional Cloud Build completed successfully:

- Build: `3f273590-0f92-4983-bd1a-9f43c740a478`
- Base image:
  `us-east4-docker.pkg.dev/cs-poc-kewg0kffb7uwobgq1rex2af/feral-docker/feral-vision@sha256:e2847fd0979bd711f66b7b418262d9b98472cd8f1b905709c632f0f7ba6f8cce`
- Standard training image:
  `us-east4-docker.pkg.dev/cs-poc-kewg0kffb7uwobgq1rex2af/feral-docker/feral-vision-gcp@sha256:102b1d826e891d87cf982841574db4bb7550aca2c7aee04c44a70a8eb591ea8d`

The first-run-specific training image has not yet been submitted. Its build
must use the published `feral-vision` digest above as `_BASE_IMAGE`.

## Next verification

Independently list the new artifact root and verify `payload/images/`,
`payload/annotations/`, `dataset-artifact.json`, and
`dataset-artifact.dvc`. Then use DVC to confirm the tracker contains
version-aware object generations before treating the raw Dataset Artifact as
accepted.

## Guide impact

No user-facing guide change is needed. The canonical role and image-build
boundaries remain in `docs/agents/cloudops.md` and `docs/agents/data.md`.
