variable "name" {
  description = "Unique Compute Engine instance name."
  type        = string
  nullable    = false
}

variable "machine_type" {
  description = "Compute Engine machine type."
  type        = string
  nullable    = false
}

variable "zone" {
  description = "Compute Engine zone for the instance."
  type        = string
  nullable    = false
}

variable "tags" {
  description = "Network tags attached to the instance."
  type        = list(string)
  default     = []
  nullable    = false
}

variable "labels" {
  description = "Labels attached to the instance."
  type        = map(string)
  default     = {}
  nullable    = false
}

variable "on_host_maintenance" {
  description = "Compute Engine host-maintenance action."
  type        = string
  nullable    = false
}

variable "automatic_restart" {
  description = "Whether Compute Engine automatically restarts the instance."
  type        = bool
  nullable    = false
}

variable "provisioning_model" {
  description = "Optional Compute Engine provisioning model."
  type        = string
  default     = null
}

variable "instance_termination_action" {
  description = "Optional action when a Flex-start instance reaches its limit."
  type        = string
  default     = null
}

variable "max_run_duration_seconds" {
  description = "Optional maximum instance run duration in seconds."
  type        = number
  default     = null
}

variable "accelerator_type" {
  description = "Optional accelerator type attached to the instance."
  type        = string
  default     = null
}

variable "accelerator_count" {
  description = "Number of optional accelerator cards attached to the instance."
  type        = number
  default     = 0
}

variable "boot_image" {
  description = "Boot disk image reference."
  type        = string
  nullable    = false
}

variable "boot_disk_size_gb" {
  description = "Boot disk size in gigabytes."
  type        = number
  nullable    = false
}

variable "boot_disk_type" {
  description = "Boot disk type."
  type        = string
  nullable    = false
}

variable "scratch_disk_interface" {
  description = "Optional local SSD interface."
  type        = string
  default     = null
}

variable "subnetwork" {
  description = "Subnetwork self-link for the instance network interface."
  type        = string
  nullable    = false
}

variable "service_account_email" {
  description = "Service account attached to the instance."
  type        = string
  nullable    = false
}

variable "service_account_scopes" {
  description = "OAuth scopes attached to the instance service account."
  type        = list(string)
  default     = ["cloud-platform"]
  nullable    = false
}

variable "metadata" {
  description = "Instance metadata key/value pairs."
  type        = map(string)
  default     = {}
  nullable    = false
}

variable "metadata_startup_script" {
  description = "Optional instance startup script."
  type        = string
  default     = null
}
