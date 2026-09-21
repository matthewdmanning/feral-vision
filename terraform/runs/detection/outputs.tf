output "run_id" {
  description = "Identifier every run-scoped Cloud Resource name derives from."
  value       = var.run_id
}

output "trainer_instance_name" {
  description = "Name of the disposable GPU training instance."
  value       = module.trainer.instance_name
}

output "trainer_zone" {
  description = "Zone of the training instance, needed to read its serial console."
  value       = module.trainer.zone
}

output "trainer_private_ip" {
  description = "Private IPv4 address of the training instance. The instance has no external address."
  value       = module.trainer.private_ip
}

output "trainer_accelerator_type" {
  description = "Accelerator attached to the training instance."
  value       = module.trainer.accelerator_type
}

output "training_image" {
  description = "Digest-pinned training image this run applied."
  value       = var.training_image
}

output "dataset_artifact_uri" {
  description = "Dataset Artifact the run trains on, resolved against the dataset-only bucket."
  value       = "gs://${data.google_storage_bucket.dataset.name}/${var.dataset_artifact_prefix}"
}

output "run_artifact_uri" {
  description = "Durable, non-dataset prefix holding this run's MLflow outputs, DVC lock, and training evidence."
  value       = "${trimsuffix(var.artifact_prefix, "/")}/${var.run_id}"
}

output "cloud_nat_router_name" {
  description = "Run-scoped Cloud Router name, or null when the run reuses existing regional NAT egress."
  value       = var.create_cloud_nat ? module.nat[0].router_name : null
}
