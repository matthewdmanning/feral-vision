output "run_id" {
  description = "Identifier every run-scoped name derives from."
  value       = var.run_id
}

output "project_id" {
  description = "Project that owns the disposable trainer."
  value       = var.project_id
}

output "trainer_instance_name" {
  description = "Name of the disposable GPU training instance."
  value       = google_compute_instance.trainer.name
}

output "trainer_zone" {
  description = "Zone of the training instance."
  value       = google_compute_instance.trainer.zone
}

output "trainer_machine_type" {
  description = "Fixed machine type for this single-instance training root."
  value       = google_compute_instance.trainer.machine_type
}

output "trainer_gpu_type" {
  description = "Fixed GPU accelerator type for this single-instance training root."
  value       = google_compute_instance.trainer.guest_accelerator[0].type
}

output "trainer_network" {
  description = "Network the training instance attaches to."
  value       = google_compute_instance.trainer.network_interface[0].network
}

output "network_name" {
  description = "Configured existing auto-mode VPC name."
  value       = var.network_name
}

output "trainer_service_account" {
  description = "Existing service account attached to the trainer."
  value       = var.service_account_email
}

output "boot_image" {
  description = "Concrete Deep Learning VM image self-link resolved during planning."
  value       = data.google_compute_image.trainer_boot.self_link
}

output "training_image" {
  description = "Digest-pinned training image this run applies."
  value       = var.training_image
}

output "dataset_artifact_uri" {
  description = "Dataset Artifact the run trains on, resolved against the dataset-only bucket."
  value       = local.dataset_base_uri
}

output "source_annotation_generation" {
  description = "Pinned generation of payload/annotations/instances.json."
  value       = var.source_annotation_generation
}

output "run_artifact_uri" {
  description = "Durable, non-dataset prefix holding this run's MLflow outputs, dataset-artifact.json provenance record, and terminal training evidence."
  value       = local.run_artifact_uri
}
