# Artifact Registry IAM grant denied

Date: 2026-08-06

## Failure

The active operator account, `mattmanningclemson@gmail.com`, was denied while
attempting to add `roles/artifactregistry.writer` for Cloud Build service
account `373124575345-compute@developer.gserviceaccount.com` on the
`feral-docker` repository in `us-east4`.

A retry on 2026-08-06 produced the same `PERMISSION_DENIED` result. No IAM
binding was changed by either attempt.

## Impact

The Cloud Build image cannot be pushed, so no image digest is available for the
Cloud Run Dataset Artifact publisher. The server-side COCO data workflow cannot
continue past image publication.

## Required external action

A principal permitted to administer IAM on this Artifact Registry repository
must grant that service account `roles/artifactregistry.writer` on
`feral-docker` in project `cs-poc-kewg0kffb7uwobgq1rex2af`, location
`us-east4`.
