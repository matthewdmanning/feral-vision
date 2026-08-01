variable "project_id" {
  description = "GCP project that owns the GPU trainer resources."
  type        = string
  nullable    = false
}

variable "bucket_name" {
  description = "Existing dataset-only Cloud Storage bucket that holds the COCO archive."
  type        = string
  default     = "mobile-training-images"
  nullable    = false

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]$", var.bucket_name))
    error_message = "bucket_name must be 3-222 lowercase characters and use only letters, digits, dots, underscores, or hyphens."
  }
}

variable "bucket_project_id" {
  description = "GCP project that owns the existing dataset bucket."
  type        = string
  default     = "cs-poc-kewg0kffb7uwobgq1rex2af"
  nullable    = false
}

variable "region" {
  description = "Default GCP region for provider operations."
  type        = string
  default     = "us-east4"
  nullable    = false
}

variable "zone" {
  description = "GCP zone for the GPU trainer."
  type        = string
  default     = "us-east4-c"
  nullable    = false
}

variable "vm_name" {
  description = "Name of the GPU training VM."
  type        = string
  default     = "feral-vision-trainer"
  nullable    = false
}

variable "machine_type" {
  description = "Compute Engine machine type for the GPU trainer."
  type        = string
  default     = "n1-standard-4"
  nullable    = false
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
  description = "Google-managed project that publishes Deep Learning VM images."
  type        = string
  default     = "deeplearning-platform-release"
  nullable    = false
}

variable "network_self_link" {
  description = "Self-link of the VPC network for the GPU trainer."
  type        = string
  default     = "projects/cs-poc-kewg0kffb7uwobgq1rex2af/global/networks/default"
  nullable    = false
}

variable "subnetwork_self_link" {
  description = "Self-link of the subnet used by the private GPU trainer and Cloud NAT."
  type        = string
  default     = "projects/cs-poc-kewg0kffb7uwobgq1rex2af/regions/us-east4/subnetworks/default"
  nullable    = false
}

variable "service_account_id" {
  description = "Account ID for the GPU trainer service account."
  type        = string
  default     = "feral-vision-trainer"
  nullable    = false
}

variable "dvc_smoke_service_account_email" {
  description = "Existing Compute Engine service account used by the disposable DVC smoke VM; Terraform never creates it."
  type        = string
  default     = "feral-vision-ai@cs-poc-kewg0kffb7uwobgq1rex2af.iam.gserviceaccount.com"
  nullable    = false
}

variable "artifact_repository" {
  description = "Artifact Registry repository that contains the training image."
  type        = string
  default     = "feral-docker"
  nullable    = false
}

variable "training_image" {
  description = "Digest-pinned CUDA-enabled PyTorch image for the training VM."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9._/@:-]*@sha256:[0-9a-f]{64}$", var.training_image))
    error_message = "training_image must be a lowercase, digest-pinned container image reference."
  }
}

variable "coco_max_epochs" {
  description = "Maximum training epochs used to size the bounded COCO download."
  type        = number
  default     = 50
  nullable    = false

  validation {
    condition     = var.coco_max_epochs > 0
    error_message = "coco_max_epochs must be positive."
  }
}

variable "coco_batch_size" {
  description = "Batch size used to size the bounded COCO download."
  type        = number
  default     = 16
  nullable    = false

  validation {
    condition     = var.coco_batch_size > 0
    error_message = "coco_batch_size must be positive."
  }
}

variable "coco_data_dir" {
  description = "SSD-mounted directory where the VM exports the COCO subset."
  type        = string
  default     = "/data/coco/train2017"
  nullable    = false

  validation {
    condition     = can(regex("^/[A-Za-z0-9._/-]+$", var.coco_data_dir))
    error_message = "coco_data_dir must be an absolute path using only safe path characters."
  }
}

variable "coco_archive_prefix" {
  description = "Cloud Storage prefix that receives the COCO export before VM shutdown."
  type        = string
  default     = "datasets/coco/train2017"
  nullable    = false

  validation {
    condition     = can(regex("^[A-Za-z0-9._/-]+$", var.coco_archive_prefix))
    error_message = "coco_archive_prefix must use only safe Cloud Storage prefix characters."
  }
}

variable "labels" {
  description = "Labels applied to cloud-smoke resources."
  type        = map(string)
  default = {
    managed-by = "terraform"
    purpose    = "cloud-smoke"
  }
  nullable = false
}
