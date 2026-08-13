resource "google_compute_router" "this" {
  name    = var.router_name
  network = var.network
  region  = var.region
}

resource "google_compute_router_nat" "this" {
  name                               = var.nat_name
  router                             = google_compute_router.this.name
  region                             = google_compute_router.this.region
  nat_ip_allocate_option             = var.nat_ip_allocate_option
  source_subnetwork_ip_ranges_to_nat = var.source_subnetwork_ip_ranges_to_nat

  subnetwork {
    name                    = var.subnetwork
    source_ip_ranges_to_nat = var.source_ip_ranges_to_nat
  }
}
