output "router_name" {
  description = "Cloud Router name."
  value       = google_compute_router.this.name
}

output "router_region" {
  description = "Cloud Router region."
  value       = google_compute_router.this.region
}

output "nat_source_subnetwork_ip_ranges_to_nat" {
  description = "Cloud NAT subnetwork source range mode."
  value       = google_compute_router_nat.this.source_subnetwork_ip_ranges_to_nat
}
