# Deployment Model

1. Authenticate the operator or automation identity. Prefer service-account impersonation locally; attach a custom least-privilege service account to the VM rather than using key files. CLI authentication and ADC are separate mechanisms.

2. Verify capacity before creation:

   - Select a GPU accelerator type and count.
   - Confirm the GPU is available in the target zone.
   - Confirm a compatible machine type.
   - Confirm sufficient GPU quota.

   Context7 exposes the relevant discovery surfaces: `compute accelerator-types list` and `compute machine-types list`.

3. Create the VM with `gcloud compute instances create`, supplying:

   - explicit project and zone;
   - machine type;
   - GPU accelerator type/count;
   - boot image and disk size;
   - network;
   - service account and scopes;
   - container configuration.

4. Prepare the guest OS with NVIDIA drivers/CUDA, then verify GPU visibility from inside the VM before starting training.

The Google Cloud skill requires this exact execution sequence:

- Step 1: Validate the leaf syntax with `gcloud help compute instances create`.
- Step 2: Verify required flags and whether `--dry-run` is supported.
- Step 3: Run a dry run if the command supports it.
- Step 4: Request authorization before creating the VM.

I invoked the required local `gcloud help` command, but this environment returned no help output, so I will not invent a copy-paste deployment command or claim the exact current flag syntax is validated.

Sources:

- [Context7: `gcloud compute instances create`](https://docs.cloud.google.com/sdk/gcloud/reference/compute/instances/create)
- [Context7: accelerator type discovery](https://docs.cloud.google.com/sdk/gcloud/reference/compute/accelerator-types/list)
- [Context7: machine type discovery](https://docs.cloud.google.com/sdk/gcloud/reference/compute/machine-types/list)
- [Google Cloud authentication guidance](https://docs.cloud.google.com/docs/authentication.md.txt)
