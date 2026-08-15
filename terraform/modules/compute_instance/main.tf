resource "google_compute_instance" "this" {
  name         = var.name
  machine_type = var.machine_type
  zone         = var.zone
  tags         = var.tags
  labels       = var.labels

  scheduling {
    on_host_maintenance         = var.on_host_maintenance
    automatic_restart           = var.automatic_restart
    provisioning_model          = var.provisioning_model
    instance_termination_action = var.instance_termination_action

    dynamic "max_run_duration" {
      for_each = var.max_run_duration_seconds == null ? [] : [var.max_run_duration_seconds]

      content {
        seconds = max_run_duration.value
      }
    }
  }

  dynamic "guest_accelerator" {
    for_each = var.accelerator_type == null ? [] : [var.accelerator_type]

    content {
      type  = guest_accelerator.value
      count = var.accelerator_count
    }
  }

  boot_disk {
    initialize_params {
      image = var.boot_image
      size  = var.boot_disk_size_gb
      type  = var.boot_disk_type
    }
  }

  dynamic "scratch_disk" {
    for_each = var.scratch_disk_interface == null ? [] : [var.scratch_disk_interface]

    content {
      interface = scratch_disk.value
    }
  }

  network_interface {
    subnetwork = var.subnetwork

    dynamic "access_config" {
      for_each = var.access_config

      content {
        nat_ip       = access_config.value.nat_ip
        network_tier = access_config.value.network_tier
      }
    }
  }

  service_account {
    email  = var.service_account_email
    scopes = var.service_account_scopes
  }

  metadata                = var.metadata
  metadata_startup_script = var.metadata_startup_script
}
