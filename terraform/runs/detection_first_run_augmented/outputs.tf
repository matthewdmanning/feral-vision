output "detection_first_run_augmented_trainer_instance_name" {
  description = "Name of the run-specific GPU training instance."
  value       = google_compute_instance.detection_first_run_augmented_trainer.name
}

output "detection_first_run_augmented_trainer_private_ip" {
  description = "Private IPv4 address assigned to the run-specific VM."
  value       = google_compute_instance.detection_first_run_augmented_trainer.network_interface[0].network_ip
}
