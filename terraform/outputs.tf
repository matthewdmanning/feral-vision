output "bucket_name" {
  description = "Name of the provisioned Cloud Storage bucket."
  value       = google_storage_bucket.cloud_smoke.name
}

output "bucket_url" {
  description = "Canonical GCS URL of the provisioned bucket."
  value       = google_storage_bucket.cloud_smoke.url
}

output "gpu_trainer_instance_name" {
  description = "Name of the provisioned GPU training instance."
  value       = google_compute_instance.gpu_trainer.name
}

output "gpu_trainer_external_ip" {
  description = "Ephemeral external IP assigned to the GPU training instance."
  value       = google_compute_instance.gpu_trainer.network_interface[0].access_config[0].nat_ip
}
