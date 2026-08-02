provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

data "google_storage_bucket" "cloud_smoke" {
  name    = var.bucket_name
  project = var.bucket_project_id
}

resource "google_service_account" "gpu_trainer" {
  account_id   = var.service_account_id
  display_name = "Service account for the cloud-smoke GPU trainer"
}

resource "google_storage_bucket_iam_member" "dvc_smoke_object_access" {
  bucket = data.google_storage_bucket.cloud_smoke.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${var.dvc_smoke_service_account_email}"

  condition {
    title       = "dvc-smoke-prefix-only"
    description = "Permit the smoke check to create and remove only its own objects."
    expression  = "resource.name.startsWith(\"projects/_/buckets/${data.google_storage_bucket.cloud_smoke.name}/objects/dvc-smoke/\")"
  }
}

resource "google_storage_bucket_iam_member" "gpu_trainer_object_access" {
  bucket = data.google_storage_bucket.cloud_smoke.name
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

resource "google_compute_router" "cloud_smoke" {
  name    = "${var.vm_name}-nat-router"
  network = var.network_self_link
  region  = var.region
}

resource "google_compute_router_nat" "cloud_smoke" {
  name                               = "${var.vm_name}-nat"
  router                             = google_compute_router.cloud_smoke.name
  region                             = google_compute_router.cloud_smoke.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"

  subnetwork {
    name                    = var.subnetwork_self_link
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }
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
    subnetwork = var.subnetwork_self_link
  }

  service_account {
    email  = google_service_account.gpu_trainer.email
    scopes = ["cloud-platform"]
  }

  metadata = {
    enable-oslogin        = "TRUE"
    install-nvidia-driver = "True"
    shutdown-script = templatefile("${path.module}/templates/archive_on_shutdown.sh.tftpl", {
      bucket_name         = data.google_storage_bucket.cloud_smoke.name
      coco_archive_prefix = var.coco_archive_prefix
      coco_data_dir       = var.coco_data_dir
      training_image      = var.training_image
    })
  }

  metadata_startup_script = templatefile("${path.module}/templates/trainer_startup.sh.tftpl", {
    bucket_name         = data.google_storage_bucket.cloud_smoke.name
    coco_archive_prefix = var.coco_archive_prefix
    coco_batch_size     = var.coco_batch_size
    coco_data_dir       = var.coco_data_dir
    coco_max_epochs     = var.coco_max_epochs
    project_id          = var.project_id
    training_image      = var.training_image
  })

  depends_on = [
    google_artifact_registry_repository_iam_member.gpu_trainer_image_pull,
    google_compute_router_nat.cloud_smoke,
    google_storage_bucket_iam_member.gpu_trainer_object_access,
  ]
}

resource "google_compute_instance" "dvc_smoke" {
  name         = "feral-vision-dvc-smoke"
  machine_type = "e2-small"
  zone         = var.zone
  tags         = ["cloud-smoke-dvc"]
  labels       = merge(var.labels, { purpose = "dvc-smoke" })

  scheduling {
    automatic_restart   = false
    on_host_maintenance = "MIGRATE"
  }

  boot_disk {
    initialize_params {
      image = "projects/debian-cloud/global/images/debian-13-trixie-v20260727"
      size  = 20
      type  = "pd-standard"
    }
  }

  network_interface {
    subnetwork = var.subnetwork_self_link
  }

  service_account {
    email  = var.dvc_smoke_service_account_email
    scopes = ["cloud-platform"]
  }

  metadata_startup_script = templatefile("${path.module}/templates/dvc_smoke_startup.sh.tftpl", {
    dataset_bucket = data.google_storage_bucket.cloud_smoke.name
    project_id     = var.project_id
  })

  depends_on = [
    google_compute_router_nat.cloud_smoke,
    google_storage_bucket_iam_member.dvc_smoke_object_access,
  ]
}
