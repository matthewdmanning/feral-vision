resource "google_compute_subnetwork" "this" {
  name                     = var.name
  network                  = var.network
  region                   = var.region
  ip_cidr_range            = var.ip_cidr_range
  private_ip_google_access = var.private_ip_google_access

  lifecycle {
    prevent_destroy = true
  }
}
