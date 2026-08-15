output "detection_trainer_instance_name" {
  description = "Name of the run-specific GPU training instance."
  value       = module.trainer.instance_name
}

output "detection_trainer_private_ip" {
  description = "Private IPv4 address assigned to the run-specific VM."
  value       = module.trainer.private_ip
}

output "detection_trainer_public_ip" {
  description = "Ephemeral public IPv4 address assigned to the run-specific VM."
  value       = module.trainer.public_ip
}
