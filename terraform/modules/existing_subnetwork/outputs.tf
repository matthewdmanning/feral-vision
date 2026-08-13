output "name" {
  description = "Existing subnetwork name."
  value       = google_compute_subnetwork.this.name
}

output "self_link" {
  description = "Existing subnetwork self-link."
  value       = google_compute_subnetwork.this.self_link
}
