output "router_name" {
  description = "Cloud Router name."
  value       = google_compute_router.this.name
}

output "router_region" {
  description = "Cloud Router region."
  value       = google_compute_router.this.region
}

output "nat_name" {
  description = "Cloud NAT name."
  value       = google_compute_router_nat.this.name
}
