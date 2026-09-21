# Detection training run.
#
# This root provisions one disposable, private GPU VM that trains on a Dataset
# Artifact already published to the dataset-only Cloud Storage bucket. It reads
# the bucket and the subnetwork; it creates only the trainer and, optionally,
# the run-scoped egress path that trainer needs.
#
# Every run-scoped name derives from var.run_id, so concurrent runs cannot
# contend for the same Cloud Resource.

locals {
  resource_prefix = "feral-vision-detection-${var.run_id}"

  vm_name          = local.resource_prefix
  nat_router_name  = "${local.resource_prefix}-router"
  nat_name         = "${local.resource_prefix}-nat"
  dataset_base_uri = "gs://${data.google_storage_bucket.dataset.name}/${var.dataset_artifact_prefix}"

  labels = merge(var.labels, { run-id = var.run_id })
}

# The dataset-only bucket holding the selected Dataset Artifact. Reading it
# fails the plan when the bucket is absent or unreadable by the caller, so a
# plan never promises a run against a bucket that is not there.
data "google_storage_bucket" "dataset" {
  name    = var.bucket_name
  project = var.bucket_project_id
}

# Pre-existing shared network infrastructure. This root reads the subnetwork
# and never owns, imports, or mutates it; a destroy of this run cannot reach it.
data "google_compute_subnetwork" "training" {
  name    = var.subnetwork_name
  project = var.project_id
  region  = var.region
}

# Egress for a VM with no external IP: it must reach Artifact Registry to pull
# the training image. Disable when the subnetwork already has regional NAT.
module "nat" {
  source = "../../modules/cloud_nat"
  count  = var.create_cloud_nat ? 1 : 0

  router_name = local.nat_router_name
  nat_name    = local.nat_name
  network     = data.google_compute_subnetwork.training.network
  region      = var.region
  subnetwork  = data.google_compute_subnetwork.training.self_link
}

module "trainer" {
  source = "../../modules/compute_instance"

  name         = local.vm_name
  machine_type = var.machine_type
  zone         = var.zone
  tags         = var.instance_tags
  labels       = local.labels

  on_host_maintenance         = var.on_host_maintenance
  automatic_restart           = var.automatic_restart
  provisioning_model          = var.provisioning_model
  instance_termination_action = var.instance_termination_action
  max_run_duration_seconds    = var.max_run_duration_seconds

  accelerator_type  = var.gpu_type
  accelerator_count = var.accelerator_count

  boot_image             = "projects/${var.deep_learning_image_project}/global/images/family/${var.deep_learning_image_family}"
  boot_disk_size_gb      = var.boot_disk_size_gb
  boot_disk_type         = var.boot_disk_type
  scratch_disk_interface = var.scratch_disk_interface

  subnetwork            = data.google_compute_subnetwork.training.self_link
  service_account_email = var.service_account_email
  metadata              = var.instance_metadata

  metadata_startup_script = templatefile("${path.module}/templates/trainer_startup.sh.tftpl", {
    run_id                       = var.run_id
    training_image               = var.training_image
    dataset_base_uri             = local.dataset_base_uri
    source_annotation_generation = var.source_annotation_generation
    artifact_prefix              = trimsuffix(var.artifact_prefix, "/")
    local_ssd_mount_dir          = var.local_ssd_mount_dir
    dataset_host_mount_dir       = var.dataset_host_mount_dir
    dataset_container_mount_dir  = var.dataset_container_mount_dir
    mlflow_tracking_uri          = var.mlflow_tracking_uri
    run_config_name              = var.run_config_name
  })

  # The trainer's first action is a docker pull, so egress must exist first.
  depends_on = [module.nat]
}
