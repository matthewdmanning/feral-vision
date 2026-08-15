variable "project_id" {
  description = "GCP project that runs the disposable DVC publisher."
  type        = string
  nullable    = false
}

variable "bucket_name" {
  description = "Existing dataset-only bucket that stores source and published Dataset Artifacts."
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
  description = "Region containing the DVC publisher network."
  type        = string
  default     = "us-east4"
  nullable    = false
}

variable "zone" {
  description = "Zone for the disposable DVC publisher VM."
  type        = string
  default     = "us-east4-c"
  nullable    = false
}

variable "vm_name" {
  description = "Unique name for the DVC publication VM."
  type        = string
  default     = "feral-vision-dvc-publisher-v3"
  nullable    = false
}

variable "machine_type" {
  description = "Machine type for the DVC publication VM."
  type        = string
  default     = "e2-standard-4"
  nullable    = false
}

variable "instance_tags" {
  description = "Network tags applied to the DVC publication VM."
  type        = list(string)
  default     = ["dvc-publication"]
  nullable    = false
}

variable "on_host_maintenance" {
  description = "Compute Engine host-maintenance action for the DVC publication VM."
  type        = string
  default     = "MIGRATE"
  nullable    = false
}

variable "automatic_restart" {
  description = "Whether Compute Engine automatically restarts the DVC publication VM."
  type        = bool
  default     = false
  nullable    = false
}

variable "boot_image" {
  description = "Boot image used by the DVC publication VM."
  type        = string
  default     = "projects/debian-cloud/global/images/family/debian-13"
  nullable    = false
}

variable "boot_disk_size_gb" {
  description = "DVC publication VM boot disk size in gigabytes."
  type        = number
  default     = 50
  nullable    = false

  validation {
    condition     = var.boot_disk_size_gb > 0
    error_message = "boot_disk_size_gb must be positive."
  }
}

variable "boot_disk_type" {
  description = "DVC publication VM boot disk type."
  type        = string
  default     = "pd-ssd"
  nullable    = false
}

variable "instance_metadata" {
  description = "Metadata values applied to the DVC publication VM."
  type        = map(string)
  default = {
    enable-oslogin = "TRUE"
  }
  nullable = false
}

variable "subnetwork_self_link" {
  description = "Existing subnet to host the DVC publication VM."
  type        = string
  default     = "projects/cs-poc-kewg0kffb7uwobgq1rex2af/regions/us-east4/subnetworks/default"
  nullable    = false
}

variable "service_account_email" {
  description = "Existing publisher identity with scoped read/create access to the train2017 Dataset Artifact catalog."
  type        = string
  default     = "data-operations-runner@cs-poc-kewg0kffb7uwobgq1rex2af.iam.gserviceaccount.com"
  nullable    = false
}

variable "source_dataset_artifact_prefix" {
  description = "Immutable v2 Dataset Artifact prefix containing the selected images and metadata."
  type        = string
  default     = "datasets/coco/train2017/raw-20260806-800-animals-v2"
  nullable    = false
}

variable "source_annotation_generation" {
  description = "Retained generation of the v2 COCO annotation object restored into the new immutable artifact."
  type        = string
  default     = "1786043348908657"
  nullable    = false

  validation {
    condition     = can(regex("^[0-9]+$", var.source_annotation_generation))
    error_message = "source_annotation_generation must be a Cloud Storage object generation number."
  }
}

variable "target_dataset_artifact_prefix" {
  description = "New immutable Dataset Artifact prefix published for the binary baseline training run."
  type        = string
  default     = "datasets/coco/train2017/raw-20260806-800-animals-v3"
  nullable    = false

  validation {
    condition     = can(regex("^datasets/[A-Za-z0-9._/-]+$", var.target_dataset_artifact_prefix))
    error_message = "target_dataset_artifact_prefix must be a datasets/ prefix without a gs:// URI."
  }
}

variable "labels" {
  description = "Labels applied to the DVC publication VM."
  type        = map(string)
  default = {
    managed-by = "terraform"
    purpose    = "dvc-publication"
  }
  nullable = false
}
