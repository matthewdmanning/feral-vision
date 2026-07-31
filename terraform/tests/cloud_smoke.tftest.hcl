mock_provider "google" {}

run "bucket_configuration" {
  command = plan

  variables {
    project_id        = "terraform-skill-smoke"
    bucket_name       = "terraform-skill-smoke-bucket"
    network_self_link = "projects/terraform-skill-smoke/global/networks/cloud-smoke"
    training_image    = "us-east4-docker.pkg.dev/terraform-skill-smoke/feral-vision/feral-vision-gcp@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  }

  assert {
    condition     = google_storage_bucket.cloud_smoke.uniform_bucket_level_access
    error_message = "The bucket must use uniform bucket-level access."
  }

  assert {
    condition     = google_storage_bucket.cloud_smoke.public_access_prevention == "enforced"
    error_message = "The bucket must prevent public access."
  }

  assert {
    condition     = google_storage_bucket.cloud_smoke.versioning[0].enabled
    error_message = "The bucket must retain object versions."
  }

  assert {
    condition     = !google_storage_bucket.cloud_smoke.force_destroy
    error_message = "The bucket must not permit force-destroy."
  }

  assert {
    condition     = google_compute_instance.gpu_trainer.zone == "us-east4-a"
    error_message = "The GPU trainer must default to the us-east4-a zone."
  }

  assert {
    condition     = google_compute_instance.gpu_trainer.guest_accelerator[0].type == "nvidia-tesla-t4"
    error_message = "The GPU trainer must use an NVIDIA T4 accelerator."
  }

  assert {
    condition     = google_compute_instance.gpu_trainer.scheduling[0].on_host_maintenance == "TERMINATE"
    error_message = "A GPU trainer must terminate during host maintenance."
  }

  assert {
    condition     = google_compute_instance.gpu_trainer.boot_disk[0].initialize_params[0].image == "projects/deeplearning-platform-release/global/images/family/pytorch-latest-gpu"
    error_message = "The GPU trainer must use the PyTorch Deep Learning VM image family."
  }

  assert {
    condition     = google_compute_instance.gpu_trainer.metadata["install-nvidia-driver"] == "True"
    error_message = "The Deep Learning VM must install the NVIDIA driver on first boot."
  }

  assert {
    condition     = strcontains(google_compute_instance.gpu_trainer.metadata_startup_script, "export_coco_to_vm.sh")
    error_message = "Terraform must stage COCO through the VM startup script."
  }

  assert {
    condition     = strcontains(google_compute_instance.gpu_trainer.metadata["shutdown-script"], "storage rsync")
    error_message = "Terraform must archive COCO during normal VM shutdown."
  }
}
