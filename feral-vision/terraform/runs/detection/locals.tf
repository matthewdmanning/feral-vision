locals {
  vm_name = "feral-vision-detection-${var.run_id}"

  dataset_base_uri = "gs://${data.google_storage_bucket.dataset.name}/${var.dataset_artifact_prefix}"
  run_artifact_uri = "${trimsuffix(var.artifact_prefix, "/")}/${var.run_id}"

  labels = merge(var.labels, { run-id = var.run_id })

  machine_type    = "n1-standard-4"
  gpu_type        = "nvidia-tesla-t4"
  run_config_name = "runs/detection"
}
