mock_provider "google" {}

run "bucket_configuration" {
  command = plan

  variables {
    project_id        = "terraform-skill-smoke"
    bucket_name       = "terraform-skill-smoke-bucket"
    bucket_project_id = "terraform-skill-storage"
    network_self_link = "projects/terraform-skill-smoke/global/networks/cloud-smoke"
    subnetwork_self_link = "projects/terraform-skill-smoke/regions/us-east4/subnetworks/cloud-smoke"
    training_image    = "us-east4-docker.pkg.dev/terraform-skill-smoke/feral-vision/feral-vision-gcp@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  }

  assert {
    condition     = data.google_storage_bucket.cloud_smoke.name == "terraform-skill-smoke-bucket"
    error_message = "The smoke must use the selected existing bucket."
  }

  assert {
    condition     = google_compute_instance.gpu_trainer.zone == "us-east4-c"
    error_message = "The GPU trainer must default to the us-east4-c zone."
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
    condition     = google_compute_instance.gpu_trainer.network_interface[0].subnetwork == "projects/terraform-skill-smoke/regions/us-east4/subnetworks/cloud-smoke"
    error_message = "The GPU trainer must use the private Cloud NAT subnet."
  }

  assert {
    condition     = google_compute_router_nat.cloud_smoke.source_subnetwork_ip_ranges_to_nat == "LIST_OF_SUBNETWORKS"
    error_message = "Cloud NAT must be scoped to the selected subnet."
  }

  assert {
    condition     = google_compute_instance.gpu_trainer.boot_disk[0].initialize_params[0].image == "projects/deeplearning-platform-release/global/images/family/pytorch-2-9-cu129-ubuntu-2204-nvidia-580"
    error_message = "The GPU trainer must use the supported PyTorch GPU Deep Learning VM image family."
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
