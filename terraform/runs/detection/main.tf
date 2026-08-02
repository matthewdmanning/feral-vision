provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

data "google_storage_bucket" "dataset" {
  name    = var.bucket_name
  project = var.bucket_project_id
}

resource "google_compute_instance" "detection_trainer" {
  name         = var.vm_name
  machine_type = var.machine_type
  zone         = var.zone
  tags         = ["cloud-detection-gpu"]
  labels       = var.labels

  scheduling {
    on_host_maintenance = "TERMINATE"
    automatic_restart   = false
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
    bucket_name             = data.google_storage_bucket.dataset.name
    dataset_artifact_prefix = var.dataset_artifact_prefix
    dataset_mount_dir       = var.dataset_mount_dir
    mlflow_tracking_uri     = var.mlflow_tracking_uri
    training_image          = var.training_image
  })
}
