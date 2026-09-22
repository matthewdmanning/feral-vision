output "run_id" {
  description = "Identifier every run-scoped name derives from."
  value       = var.run_id
}

output "trainer_instance_name" {
  description = "Name of the disposable GPU training instance."
  value       = google_compute_instance.trainer.name
}

output "trainer_zone" {
  description = "Zone of the training instance, needed to read its serial console."
  value       = google_compute_instance.trainer.zone
}

output "trainer_network" {
  description = "Network the training instance attached to."
  value       = google_compute_instance.trainer.network_interface[0].network
}

output "training_image" {
  description = "Digest-pinned training image this run applied."
  value       = var.training_image
}

output "dataset_artifact_uri" {
  description = "Dataset Artifact the run trains on, resolved against the dataset-only bucket."
  value       = local.dataset_base_uri
}

output "run_artifact_uri" {
  description = "Durable, non-dataset prefix holding this run's MLflow outputs, DVC lock, and training evidence."
  value       = local.run_artifact_uri
}
