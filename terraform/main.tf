provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

resource "google_storage_bucket" "cloud_smoke" {
  name                        = var.bucket_name
  project                     = var.project_id
  location                    = var.location
  force_destroy               = false
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  labels                      = var.labels

  versioning {
    enabled = true
  }
}

resource "google_service_account" "gpu_trainer" {
  account_id   = var.service_account_id
  display_name = "Service account for the cloud-smoke GPU trainer"
}

resource "google_storage_bucket_iam_member" "gpu_trainer_object_access" {
  bucket = google_storage_bucket.cloud_smoke.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.gpu_trainer.email}"
}

resource "google_artifact_registry_repository_iam_member" "gpu_trainer_image_pull" {
  project    = var.project_id
  location   = var.region
  repository = var.artifact_repository
  role       = "roles/artifactregistry.reader"
  member     = "serviceAccount:${google_service_account.gpu_trainer.email}"
}

resource "google_compute_firewall" "iap_ssh" {
  name    = "${var.vm_name}-iap-ssh"
  network = var.network_self_link

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["cloud-smoke-gpu"]
}

resource "google_compute_instance" "gpu_trainer" {
  name         = var.vm_name
  machine_type = var.machine_type
  zone         = var.zone
  tags         = ["cloud-smoke-gpu"]
  labels       = var.labels

  scheduling {
    on_host_maintenance = "TERMINATE"
    automatic_restart   = true
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
    network = var.network_self_link

    access_config {}
  }

  service_account {
    email  = google_service_account.gpu_trainer.email
    scopes = ["cloud-platform"]
  }

  metadata = {
    enable-oslogin        = "TRUE"
    install-nvidia-driver = "True"
    shutdown-script = templatefile("${path.module}/templates/archive_on_shutdown.sh.tftpl", {
      bucket_name         = google_storage_bucket.cloud_smoke.name
      coco_archive_prefix = var.coco_archive_prefix
      coco_data_dir       = var.coco_data_dir
      training_image      = var.training_image
    })
  }

  metadata_startup_script = templatefile("${path.module}/templates/trainer_startup.sh.tftpl", {
    bucket_name         = google_storage_bucket.cloud_smoke.name
    coco_archive_prefix = var.coco_archive_prefix
    coco_batch_size     = var.coco_batch_size
    coco_data_dir       = var.coco_data_dir
    coco_max_epochs     = var.coco_max_epochs
    project_id          = var.project_id
    training_image      = var.training_image
  })

  depends_on = [
    google_artifact_registry_repository_iam_member.gpu_trainer_image_pull,
    google_storage_bucket_iam_member.gpu_trainer_object_access,
  ]
}
