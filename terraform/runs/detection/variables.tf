variable "project_id" {
  description = "GCP project that owns the existing training VM infrastructure."
  type        = string
  nullable    = false
}

variable "bucket_name" {
  description = "Existing dataset-only bucket that contains the selected Dataset Variant Artifact."
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
  description = "Google-managed project that publishes the VM image family."
  type        = string
  default     = "deeplearning-platform-release"
  nullable    = false
}

variable "subnetwork_self_link" {
  description = "Existing private subnet with reviewed NAT access."
  type        = string
  default     = "projects/cs-poc-kewg0kffb7uwobgq1rex2af/regions/us-east4/subnetworks/default"
  nullable    = false
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
  description = "Immutable Dataset Variant Artifact prefix containing payload, manifest, and tracker."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^datasets/[A-Za-z0-9._/-]+$", var.dataset_artifact_prefix))
    error_message = "dataset_artifact_prefix must be a datasets/ prefix without a gs:// URI."
  }
}

variable "dataset_mount_dir" {
  description = "SSD path used to stage the selected immutable Dataset Variant Artifact."
  type        = string
  default     = "/data/dataset-artifact"
  nullable    = false
}

variable "mlflow_tracking_uri" {
  description = "Managed non-secret MLflow tracking endpoint for this run."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^https://", var.mlflow_tracking_uri))
    error_message = "mlflow_tracking_uri must be an HTTPS managed tracking endpoint."
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
