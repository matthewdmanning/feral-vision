# Detection training run.
#
# One disposable GPU VM that trains on a Dataset Artifact already published to
# the dataset-only Cloud Storage bucket. Every run-scoped name derives from
# var.run_id.
#
# This root is intentionally narrow: one n1-standard-4 VM, one T4, one NVMe
# Local SSD, Flex-start scheduling, and no managed networking or IAM resources.

locals {
  vm_name = "feral-vision-detection-${var.run_id}"

  dataset_base_uri = "gs://${data.google_storage_bucket.dataset.name}/${var.dataset_artifact_prefix}"
  run_artifact_uri = "${trimsuffix(var.artifact_prefix, "/")}/${var.run_id}"

  labels = merge(var.labels, { run-id = var.run_id })

  machine_type    = "n1-standard-4"
  gpu_type        = "nvidia-tesla-t4"
  run_config_name = "runs/detection"
}

data "google_storage_bucket" "dataset" {
  name    = var.bucket_name
  project = var.bucket_project_id
}

data "google_compute_network" "training" {
  name    = var.network_name
  project = var.project_id
}

# Resolve the reviewed GPU image family during planning and feed the concrete
# image self-link into the VM. A saved plan therefore cannot silently pick up a
# newer family member between review and apply.
data "google_compute_image" "trainer_boot" {
  family  = "pytorch-2-9-cu129-ubuntu-2204-nvidia-580"
  project = "deeplearning-platform-release"
}

resource "google_compute_instance" "trainer" {
  name         = local.vm_name
  machine_type = local.machine_type
  zone         = var.zone
  tags         = var.instance_tags
  labels       = local.labels

  scheduling {
    on_host_maintenance         = "TERMINATE"
    automatic_restart           = false
    provisioning_model          = "FLEX_START"
    instance_termination_action = "DELETE"

    max_run_duration {
      seconds = var.max_run_duration_seconds
    }
  }

  guest_accelerator {
    type  = local.gpu_type
    count = 1
  }

  boot_disk {
    initialize_params {
      image = data.google_compute_image.trainer_boot.self_link
      size  = 100
      type  = "pd-ssd"
    }
  }

  scratch_disk {
    interface = "NVME"
  }

  network_interface {
    network = data.google_compute_network.training.self_link

    # No Cloud NAT is managed by this root. The trainer therefore requires one
    # ephemeral external IPv4 address for Artifact Registry and Cloud Storage.
    access_config {}
  }

  service_account {
    email  = var.service_account_email
    scopes = ["cloud-platform"]
  }

  # The selected Deep Learning VM image includes NVIDIA driver 580. Do not run
  # Google's first-boot driver installer here: it can reboot while startup is
  # staging data or launching the training container.
  metadata = {
    enable-oslogin = "TRUE"
  }

  metadata_startup_script = templatefile("${path.module}/templates/trainer_startup.sh.tftpl", {
    run_id                       = var.run_id
    training_image               = var.training_image
    dataset_base_uri             = local.dataset_base_uri
    source_annotation_generation = var.source_annotation_generation
    run_artifact_uri             = local.run_artifact_uri
    local_ssd_mount_dir          = var.local_ssd_mount_dir
    dataset_host_mount_dir       = var.dataset_host_mount_dir
    dataset_container_mount_dir  = var.dataset_container_mount_dir
    mlflow_tracking_uri          = var.mlflow_tracking_uri
    run_config_name              = local.run_config_name
  })

  lifecycle {
    precondition {
      condition     = length(local.vm_name) <= 63
      error_message = "Generated Compute Engine VM name exceeds the 63-character resource-name limit."
    }

    precondition {
      condition     = data.google_compute_network.training.auto_create_subnetworks
      error_message = "network_name must refer to an auto-mode VPC because this root intentionally does not name a subnetwork."
    }
  }
}
