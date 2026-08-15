provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

data "google_storage_bucket" "dataset" {
  name    = var.bucket_name
  project = var.bucket_project_id
}

module "subnetwork" {
  source = "../../modules/existing_subnetwork"

  name          = var.subnetwork_name
  network       = var.network_self_link
  region        = var.region
  ip_cidr_range = var.subnetwork_ip_cidr_range
}

import {
  to = module.subnetwork.google_compute_subnetwork.this
  id = "projects/${var.project_id}/regions/${var.region}/subnetworks/${var.subnetwork_name}"
}

module "trainer" {
  source = "../../modules/compute_instance"

  name                        = var.vm_name
  machine_type                = var.machine_type
  zone                        = var.zone
  tags                        = var.instance_tags
  labels                      = var.labels
  on_host_maintenance         = var.on_host_maintenance
  automatic_restart           = var.automatic_restart
  provisioning_model          = var.provisioning_model
  instance_termination_action = var.instance_termination_action
  max_run_duration_seconds    = var.flex_start_max_run_duration_seconds
  accelerator_type            = var.gpu_type
  accelerator_count           = var.accelerator_count
  boot_image                  = "projects/${var.deep_learning_image_project}/global/images/family/${var.deep_learning_image_family}"
  boot_disk_size_gb           = var.boot_disk_size_gb
  boot_disk_type              = var.boot_disk_type
  scratch_disk_interface      = var.scratch_disk_interface
  subnetwork                  = module.subnetwork.self_link
  access_config               = [{ network_tier = var.network_tier }]
  service_account_email       = var.service_account_email
  metadata                    = var.instance_metadata
  metadata_startup_script = templatefile("${path.module}/templates/trainer_startup.sh.tftpl", {
    bucket_name                  = data.google_storage_bucket.dataset.name
    dataset_artifact_prefix      = var.dataset_artifact_prefix
    source_annotation_generation = var.source_annotation_generation
    dataset_host_mount_dir       = var.dataset_host_mount_dir
    dataset_container_mount_dir  = var.dataset_container_mount_dir
    run_config_name              = var.run_config_name
    training_image               = var.training_image
  })

}

moved {
  from = google_compute_subnetwork.training_default
  to   = module.subnetwork.google_compute_subnetwork.this
}

moved {
  from = google_compute_instance.detection_trainer
  to   = module.trainer.google_compute_instance.this
}
