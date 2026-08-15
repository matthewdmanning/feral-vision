variable "project_id" {
  description = "GCP project that owns the existing training VM infrastructure."
  type        = string
  nullable    = false
}

variable "bucket_name" {
  description = "Existing dataset-only bucket that contains the selected Dataset Artifact."
  type        = string
  default     = "mobile-training-images"
  nullable    = false
}

variable "bucket_project_id" {
  description = "Project that owns the existing dataset-only bucket."
  type        = string
  default     = "cs-poc-kewg0kffb7uwobgq1rex2af"
  nullable    = false
}

variable "region" {
  description = "Regional location of the existing training infrastructure."
  type        = string
  default     = "us-east4"
  nullable    = false
}

variable "zone" {
  description = "Compute Engine zone for this detection run."
  type        = string
  default     = "us-east4-c"
  nullable    = false
}

variable "vm_name" {
  description = "Unique Compute Engine instance name for the detection run."
  type        = string
  default     = "feral-vision-detection-trainer"
  nullable    = false
}

variable "machine_type" {
  description = "Compute Engine machine type for the GPU trainer with one attached local SSD."
  type        = string
  default     = "n1-standard-4"
  nullable    = false
}

variable "flex_start_max_run_duration_seconds" {
  description = "Maximum duration of the Flex-start training VM before Compute Engine deletes it."
  type        = number
  default     = 86400
  nullable    = false

  validation {
    condition = (
      var.flex_start_max_run_duration_seconds >= 600 &&
      var.flex_start_max_run_duration_seconds <= 604800
    )
    error_message = "flex_start_max_run_duration_seconds must be between 600 seconds (10 minutes) and 604800 seconds (7 days)."
  }
}

variable "gpu_type" {
  description = "Compute Engine accelerator type for the GPU trainer."
  type        = string
  default     = "nvidia-tesla-t4"
  nullable    = false
}

variable "deep_learning_image_family" {
  description = "GPU-enabled PyTorch Deep Learning VM image family."
  type        = string
  default     = "pytorch-2-9-cu129-ubuntu-2204-nvidia-580"
  nullable    = false
}

variable "deep_learning_image_project" {
  description = "Google-managed project that publishes the VM image family."
  type        = string
  default     = "deeplearning-platform-release"
  nullable    = false
}

variable "network_self_link" {
  description = "Existing VPC network that owns the training subnet."
  type        = string
  default     = "projects/cs-poc-kewg0kffb7uwobgq1rex2af/global/networks/default"
  nullable    = false
}

variable "subnetwork_ip_cidr_range" {
  description = "Existing IPv4 CIDR range of the imported training subnet."
  type        = string
  default     = "10.150.0.0/20"
  nullable    = false

  validation {
    condition     = can(cidrhost(var.subnetwork_ip_cidr_range, 0))
    error_message = "subnetwork_ip_cidr_range must be a valid IPv4 CIDR range."
  }
}

variable "subnetwork_name" {
  description = "Name of the existing training subnetwork."
  type        = string
  default     = "default"
  nullable    = false
}

variable "network_tier" {
  description = "External network tier for the detection VM's ephemeral public IPv4 address."
  type        = string
  default     = "PREMIUM"
  nullable    = false

  validation {
    condition     = contains(["PREMIUM", "FIXED_STANDARD", "STANDARD"], var.network_tier)
    error_message = "network_tier must be PREMIUM, FIXED_STANDARD, or STANDARD."
  }
}

variable "instance_tags" {
  description = "Network tags applied to the detection VM."
  type        = list(string)
  default     = ["cloud-detection-gpu"]
  nullable    = false
}

variable "on_host_maintenance" {
  description = "Compute Engine host-maintenance action for the detection VM."
  type        = string
  default     = "TERMINATE"
  nullable    = false
}

variable "automatic_restart" {
  description = "Whether Compute Engine automatically restarts the detection VM."
  type        = bool
  default     = false
  nullable    = false
}

variable "provisioning_model" {
  description = "Compute Engine provisioning model for the detection VM."
  type        = string
  default     = "FLEX_START"
  nullable    = false
}

variable "instance_termination_action" {
  description = "Action when the detection VM reaches its maximum Flex-start duration."
  type        = string
  default     = "DELETE"
  nullable    = false
}

variable "accelerator_count" {
  description = "Number of GPU accelerator cards attached to the detection VM."
  type        = number
  default     = 1
  nullable    = false

  validation {
    condition     = var.accelerator_count > 0
    error_message = "accelerator_count must be positive."
  }
}

variable "boot_disk_size_gb" {
  description = "Detection VM boot disk size in gigabytes."
  type        = number
  default     = 100
  nullable    = false

  validation {
    condition     = var.boot_disk_size_gb > 0
    error_message = "boot_disk_size_gb must be positive."
  }
}

variable "boot_disk_type" {
  description = "Detection VM boot disk type."
  type        = string
  default     = "pd-ssd"
  nullable    = false
}

variable "scratch_disk_interface" {
  description = "Local SSD interface attached to the detection VM."
  type        = string
  default     = "NVME"
  nullable    = false
}

variable "instance_metadata" {
  description = "Metadata values applied to the detection VM."
  type        = map(string)
  default = {
    enable-oslogin        = "TRUE"
    install-nvidia-driver = "True"
  }
  nullable = false
}

variable "service_account_email" {
  description = "Existing VM service account with reviewed dataset-read and image-pull access."
  type        = string
  nullable    = false
}

variable "training_image" {
  description = "Digest-pinned detection training image built from deploy/runs/detection."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9._/@:-]*@sha256:[0-9a-f]{64}$", var.training_image))
    error_message = "training_image must be a lowercase, digest-pinned container image reference."
  }
}

variable "dataset_artifact_prefix" {
  description = "Source Dataset Artifact prefix containing the selected image payload and manifest."
  type        = string
  default     = "datasets/coco/train2017/raw-20260806-800-animals-v2"
  nullable    = false

  validation {
    condition     = can(regex("^datasets/[A-Za-z0-9._/-]+$", var.dataset_artifact_prefix))
    error_message = "dataset_artifact_prefix must be a datasets/ prefix without a gs:// URI."
  }
}

variable "source_annotation_generation" {
  description = "Retained source annotation generation copied to the training SSD with the selected image payload."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[0-9]+$", var.source_annotation_generation))
    error_message = "source_annotation_generation must be a Cloud Storage object generation number."
  }
}

variable "dataset_host_mount_dir" {
  description = "Host SSD path used to stage the Dataset payload and locally generated DVC files."
  type        = string
  default     = "/mnt/disks/ssd/dataset-artifact"
  nullable    = false

  validation {
    condition     = startswith(var.dataset_host_mount_dir, "/mnt/disks/ssd/")
    error_message = "dataset_host_mount_dir must be beneath the mounted local SSD."
  }
}

variable "dataset_container_mount_dir" {
  description = "Container path mapped to dataset_host_mount_dir through the local SSD bind mount."
  type        = string
  default     = "/data/dataset-artifact"
  nullable    = false

  validation {
    condition     = startswith(var.dataset_container_mount_dir, "/data/")
    error_message = "dataset_container_mount_dir must be beneath the /data SSD bind mount."
  }
}

variable "run_config_name" {
  description = "Hydra Run Recipe consumed by the detection training container."
  type        = string
  default     = "runs/detection"
  nullable    = false

  validation {
    condition     = can(regex("^runs/[A-Za-z0-9_-]+$", var.run_config_name))
    error_message = "run_config_name must name a Run Recipe below conf/runs/."
  }
}

variable "labels" {
  description = "Labels applied to the run-specific training VM."
  type        = map(string)
  default = {
    managed-by = "terraform"
    purpose    = "detection-training"
  }
  nullable = false
}
