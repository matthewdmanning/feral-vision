output "instance_name" {
  description = "Name of the Compute Engine instance."
  value       = google_compute_instance.this.name
}

output "private_ip" {
  description = "Private IPv4 address assigned to the instance."
  value       = google_compute_instance.this.network_interface[0].network_ip
}

output "public_ip" {
  description = "Ephemeral public IPv4 address assigned to the instance, when configured."
  value       = try(google_compute_instance.this.network_interface[0].access_config[0].nat_ip, null)
}

output "zone" {
  description = "Zone of the Compute Engine instance."
  value       = google_compute_instance.this.zone
}

output "accelerator_type" {
  description = "Configured accelerator type."
  value       = try(google_compute_instance.this.guest_accelerator[0].type, null)
}

output "on_host_maintenance" {
  description = "Configured host-maintenance action."
  value       = google_compute_instance.this.scheduling[0].on_host_maintenance
}

output "subnetwork" {
  description = "Subnetwork used by the instance."
  value       = google_compute_instance.this.network_interface[0].subnetwork
}

output "boot_image" {
  description = "Configured boot image."
  value       = google_compute_instance.this.boot_disk[0].initialize_params[0].image
}

output "metadata_install_nvidia_driver" {
  description = "NVIDIA driver installation metadata value."
  value       = try(google_compute_instance.this.metadata["install-nvidia-driver"], null)
}

output "metadata_startup_script" {
  description = "Rendered startup script."
  value       = google_compute_instance.this.metadata_startup_script
}

output "metadata_shutdown_script" {
  description = "Rendered shutdown script, when configured."
  value       = try(google_compute_instance.this.metadata["shutdown-script"], null)
}
