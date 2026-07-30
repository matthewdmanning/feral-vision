output "bucket_name" {
  description = "Name of the existing dataset bucket used by the smoke."
  value       = data.google_storage_bucket.cloud_smoke.name
}

output "bucket_url" {
  description = "Canonical GCS URL of the provisioned bucket."
  value       = data.google_storage_bucket.cloud_smoke.url
}

output "gpu_trainer_instance_name" {
  description = "Name of the provisioned GPU training instance."
  value       = google_compute_instance.gpu_trainer.name
}

output "gpu_trainer_private_ip" {
  description = "Private IPv4 address assigned to the GPU training instance."
  value       = google_compute_instance.gpu_trainer.network_interface[0].network_ip
}
