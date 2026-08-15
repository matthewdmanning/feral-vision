output "dvc_publisher_instance_name" {
  description = "Name of the disposable DVC publication instance."
  value       = google_compute_instance.dvc_publisher.name
}
output "target_dataset_artifact_uri" {
  description = "Immutable Dataset Artifact prefix published by the DVC run."
  value       = "gs://${data.google_storage_bucket.dataset.name}/${var.target_dataset_artifact_prefix}"
}
