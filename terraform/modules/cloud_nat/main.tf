resource "google_compute_router" "this" {
  name    = var.router_name
  network = var.network
  region  = var.region
}

resource "google_compute_router_nat" "this" {
  name                   = var.nat_name
  router                 = google_compute_router.this.name
  region                 = google_compute_router.this.region
  nat_ip_allocate_option = var.nat_ip_allocate_option

  # Subnetworks are banned in this project, so Cloud NAT serves every range in
  # the region rather than naming one. The field name is the provider's; this
  # module declares no subnetwork of its own.
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_PRIMARY_IP_RANGES"
}
