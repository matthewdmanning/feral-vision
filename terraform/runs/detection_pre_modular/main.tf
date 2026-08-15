provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}
data "google_storage_bucket" "dataset" {
  name    = var.bucket_name
  project = var.bucket_project_id
}

import {
  to = google_compute_subnetwork.training_default
  id = "projects/${var.project_id}/regions/${var.region}/subnetworks/default"
}

resource "google_compute_subnetwork" "training_default" {
  name                     = "default"
  network                  = var.network_self_link
  region                   = var.region
  ip_cidr_range            = var.subnetwork_ip_cidr_range
  private_ip_google_access = true

  lifecycle {
    prevent_destroy = true
  }
}

resource "google_compute_instance" "detection_trainer" {
  name         = var.vm_name
  machine_type = var.machine_type
  zone         = var.zone
  tags         = ["cloud-detection-gpu"]
  labels       = var.labels

  scheduling {
    on_host_maintenance         = "TERMINATE"
    automatic_restart           = false
    provisioning_model          = "FLEX_START"
    instance_termination_action = "DELETE"

    max_run_duration {
      seconds = var.flex_start_max_run_duration_seconds
    }
  }

  guest_accelerator {
    type  = var.gpu_type
    count = 1
  }

  boot_disk {
    initialize_params {
      image = "projects/${var.deep_learning_image_project}/global/images/family/${var.deep_learning_image_family}"
      size  = 100
      type  = "pd-ssd"
    }
  }

  scratch_disk {
    interface = "NVME"
  }

  network_interface {
    subnetwork = var.subnetwork_self_link
  }

  service_account {
    email  = var.service_account_email
    scopes = ["cloud-platform"]
  }

  metadata = {
    enable-oslogin        = "TRUE"
    install-nvidia-driver = "True"
  }

  metadata_startup_script = templatefile("${path.module}/templates/trainer_startup.sh.tftpl", {
    bucket_name                  = data.google_storage_bucket.dataset.name
    dataset_artifact_prefix      = var.dataset_artifact_prefix
    source_annotation_generation = var.source_annotation_generation
    dataset_host_mount_dir       = var.dataset_host_mount_dir
    dataset_container_mount_dir  = var.dataset_container_mount_dir
    mlflow_tracking_uri          = var.mlflow_tracking_uri
    run_config_name              = var.run_config_name
    training_image               = var.training_image
  })
}
