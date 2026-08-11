provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

data "google_storage_bucket" "dataset" {
  name    = var.bucket_name
  project = var.bucket_project_id
}

resource "google_compute_router" "dvc_publication" {
  name    = var.nat_router_name
  network = var.network_self_link
  region  = var.region
}

resource "google_compute_router_nat" "dvc_publication" {
  name                               = var.nat_name
  router                             = google_compute_router.dvc_publication.name
  region                             = google_compute_router.dvc_publication.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "LIST_OF_SUBNETWORKS"

  subnetwork {
    name                    = var.subnetwork_self_link
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }
}

resource "google_compute_instance" "dvc_publisher" {
  name         = var.vm_name
  machine_type = var.machine_type
  zone         = var.zone
  tags         = ["dvc-publication"]
  labels       = var.labels

  scheduling {
    automatic_restart   = false
    on_host_maintenance = "MIGRATE"
  }

  boot_disk {
    initialize_params {
      image = "projects/debian-cloud/global/images/family/debian-13"
      size  = 50
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
    enable-oslogin = "TRUE"
  }

  metadata_startup_script = templatefile("${path.module}/templates/dvc_publication_startup.sh.tftpl", {
    bucket_name                    = data.google_storage_bucket.dataset.name
    source_dataset_artifact_prefix = var.source_dataset_artifact_prefix
    source_annotation_generation   = var.source_annotation_generation
    target_dataset_artifact_prefix = var.target_dataset_artifact_prefix
  })

  depends_on = [google_compute_router_nat.dvc_publication]
}
