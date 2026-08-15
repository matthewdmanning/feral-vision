provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

data "google_storage_bucket" "dataset" {
  name    = var.bucket_name
  project = var.bucket_project_id
}

module "publisher" {
  source = "../../modules/compute_instance"

  name                  = var.vm_name
  machine_type          = var.machine_type
  zone                  = var.zone
  tags                  = var.instance_tags
  labels                = var.labels
  on_host_maintenance   = var.on_host_maintenance
  automatic_restart     = var.automatic_restart
  boot_image            = var.boot_image
  boot_disk_size_gb     = var.boot_disk_size_gb
  boot_disk_type        = var.boot_disk_type
  subnetwork            = var.subnetwork_self_link
  service_account_email = var.service_account_email
  metadata              = var.instance_metadata
  metadata_startup_script = templatefile("${path.module}/templates/dvc_publication_startup.sh.tftpl", {
    bucket_name                    = data.google_storage_bucket.dataset.name
    source_dataset_artifact_prefix = var.source_dataset_artifact_prefix
    source_annotation_generation   = var.source_annotation_generation
    target_dataset_artifact_prefix = var.target_dataset_artifact_prefix
  })

}

moved {
  from = google_compute_instance.dvc_publisher
  to   = module.publisher.google_compute_instance.this
}
