# Cloud Build Artifact Registry upload permission

Date: 2026-08-06

## Failure

Cloud Build `76e4b4fb-1437-49c3-894e-b416bc5cd3c9` successfully built the DVC
publisher image but failed to push it to
`us-east4-docker.pkg.dev/cs-poc-kewg0kffb7uwobgq1rex2af/feral-docker`.
Artifact Registry denied `artifactregistry.repositories.uploadArtifacts` to the
Cloud Build service identity.

## Impact

No deployable image digest exists from this build. The Cloud Run Job remains
uncreated and the raw COCO payload remains unfinalized.

## Correction and required verification

Grant the exact Cloud Build service account `roles/artifactregistry.writer` on
the `feral-docker` repository in `us-east4`, then submit a new immutable-tag
build and resolve the pushed image digest before deploying it.
