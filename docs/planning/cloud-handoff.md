# Cloud Build handoff — 2026-07-25

## Status

No Terraform resources were created. The latest Cloud Build assembled the image
but failed while pushing to Artifact Registry.

## Errors, causes, and fixes

| Error | Cause | Fix |
|---|---|---|
| `manifest unknown` for `pytorch/pytorch:2.8.0-cuda12.4-cudnn9-runtime` | That tag does not exist. | Use the verified `pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime` tag. |
| `mv: cannot stat /root/.cargo/bin/uv` | Current `uv` installer writes to `/root/.local/bin`. | Move `/root/.local/bin/uv` to `/usr/local/bin/uv`. |
| `artifactregistry.repositories.uploadArtifacts` denied | Cloud Build runs as `446310107443-compute@developer.gserviceaccount.com`, which cannot push to `feral-docker`. | Grant that account `roles/artifactregistry.writer` on `us-east4-docker.pkg.dev/feralspotter-f9e51/feral-docker`. |

## Next action

After the Writer grant: upload a fresh archive containing the corrected
`deploy/Dockerfile`, submit `deploy/cloudbuild.build.yaml`, wait for the image
digest, then show the Terraform plan before applying it.
