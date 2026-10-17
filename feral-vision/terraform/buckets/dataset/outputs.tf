output "bucket_name" {
  description = "Name of the dataset-only bucket."
  value       = google_storage_bucket.dataset.name
}
