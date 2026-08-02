output "detection_trainer_instance_name" {
  description = "Name of the run-specific GPU training instance."
  value       = google_compute_instance.detection_trainer.name
}

output "detection_trainer_private_ip" {
  description = "Private IPv4 address assigned to the run-specific VM."
  value       = google_compute_instance.detection_trainer.network_interface[0].network_ip
}
