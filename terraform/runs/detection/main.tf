# Detection training run.
#
# One disposable GPU VM that trains on a Dataset Artifact already published to
# the dataset-only Cloud Storage bucket. Every run-scoped name derives from
# var.run_id, so concurrent runs cannot contend for the same Cloud Resource.
#
# This root is self-contained: it declares no modules and no networking
# resources. Subnetworks and Cloud NAT are banned in this project. The trainer
# reaches Artifact Registry and Cloud Storage over its own external address.

locals {
  vm_name = "feral-vision-detection-${var.run_id}"

  dataset_base_uri = "gs://${data.google_storage_bucket.dataset.name}/${var.dataset_artifact_prefix}"
  run_artifact_uri = "${trimsuffix(var.artifact_prefix, "/")}/${var.run_id}"

  labels = merge(var.labels, { run-id = var.run_id })
}

# The dataset-only bucket holding the selected Dataset Artifact. Reading it
# fails the plan when the bucket is absent or unreadable by the caller, so a
# plan never promises a run against a bucket that is not there.
data "google_storage_bucket" "dataset" {
  name    = var.bucket_name
  project = var.bucket_project_id
}

# Pre-existing network, read and never owned. A destroy plan for this run
# cannot reach it.
data "google_compute_network" "training" {
  name    = var.network_name
  project = var.project_id
}

resource "google_compute_instance" "trainer" {
  name         = local.vm_name
  machine_type = var.machine_type
  zone         = var.zone
  tags         = var.instance_tags
  labels       = local.labels

  scheduling {
    on_host_maintenance         = var.on_host_maintenance
    automatic_restart           = var.automatic_restart
    provisioning_model          = var.provisioning_model
    instance_termination_action = var.instance_termination_action

    max_run_duration {
      seconds = var.max_run_duration_seconds
    }
  }

  guest_accelerator {
    type  = var.gpu_type
    count = var.accelerator_count
  }

  boot_disk {
    initialize_params {
      image = "projects/${var.deep_learning_image_project}/global/images/family/${var.deep_learning_image_family}"
      size  = var.boot_disk_size_gb
      type  = var.boot_disk_type
    }
  }

  # The Dataset payload is staged here, not on the boot disk.
  scratch_disk {
    interface = var.scratch_disk_interface
  }

  # Attaches to the network; Compute Engine selects the regional range. The
  # empty access_config assigns an ephemeral external address, which is how
  # this VM reaches Artifact Registry without Cloud NAT.
  network_interface {
    network = data.google_compute_network.training.self_link

    access_config {
    }
  }

  service_account {
    email  = var.service_account_email
    scopes = var.service_account_scopes
  }

  metadata = var.instance_metadata

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
    run_config_name              = var.run_config_name
  })
}
