# ---------------------------------------------------------------------------
# Run identity
# ---------------------------------------------------------------------------

variable "run_id" {
  description = "Unique identifier for this detection training run. Every run-scoped name derives from it."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z]([a-z0-9-]{1,38}[a-z0-9])$", var.run_id))
    error_message = "run_id must be 3-40 characters, lowercase alphanumeric or hyphen, and start with a letter and end with a letter or digit."
  }
}

variable "project_id" {
  description = "GCP project that owns the training VM."
  type        = string
  nullable    = false
}

variable "zone" {
  description = "Compute Engine zone for the training VM."
  type        = string
  default     = "us-east4-c"
  nullable    = false
}

# ---------------------------------------------------------------------------
# Dataset bucket and Dataset Artifact selection
# ---------------------------------------------------------------------------

variable "bucket_name" {
  description = "Existing dataset-only bucket that holds the selected Dataset Artifact. This root reads it; it never creates or mutates it."
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

variable "dataset_artifact_prefix" {
  description = "Dataset Artifact prefix below the dataset bucket, for example datasets/coco/train2017/<artifact>. The published dataset-artifact.json at this prefix is the upstream provenance contract consumed by training."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^datasets/[A-Za-z0-9._/-]+$", var.dataset_artifact_prefix))
    error_message = "dataset_artifact_prefix must be a datasets/ prefix without a gs:// URI."
  }

  validation {
    condition     = !endswith(var.dataset_artifact_prefix, "/")
    error_message = "dataset_artifact_prefix must not end with a slash."
  }
}

variable "source_annotation_generation" {
  description = "Retained Cloud Storage object generation of payload/annotations/instances.json, so the run trains on an immutable annotation."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[0-9]+$", var.source_annotation_generation))
    error_message = "source_annotation_generation must be a Cloud Storage object generation number."
  }
}

# ---------------------------------------------------------------------------
# Durable evidence destination
# ---------------------------------------------------------------------------

variable "artifact_prefix" {
  description = "Writable gs:// prefix for MLflow outputs, checkpoints, Model Artifacts, and training evidence."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^gs://[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]/[A-Za-z0-9._/-]+$", var.artifact_prefix))
    error_message = "artifact_prefix must be a gs://<bucket>/<prefix> URI."
  }

  validation {
    condition     = split("/", trimprefix(var.artifact_prefix, "gs://"))[0] != var.bucket_name
    error_message = "artifact_prefix must not live in the dataset bucket."
  }
}

# ---------------------------------------------------------------------------
# Existing network and identity
# ---------------------------------------------------------------------------

variable "network_name" {
  description = "Name of the existing auto-mode VPC network the training VM attaches to."
  type        = string
  default     = "default"
  nullable    = false
}

variable "instance_tags" {
  description = "Network tags applied to the training VM so existing firewall policy can select it."
  type        = list(string)
  default     = ["cloud-detection-gpu"]
  nullable    = false
}

variable "service_account_email" {
  description = "Existing VM service account with reviewed dataset-read, artifact-write, and image-pull access."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[^@]+@[^@]+\\.iam\\.gserviceaccount\\.com$", var.service_account_email))
    error_message = "service_account_email must be an existing service account address."
  }
}

# ---------------------------------------------------------------------------
# Fixed single-VM lifecycle
# ---------------------------------------------------------------------------

variable "max_run_duration_seconds" {
  description = "Maximum trainer run duration before Compute Engine deletes the Flex-start VM."
  type        = number
  default     = 86400
  nullable    = false

  validation {
    condition     = var.max_run_duration_seconds >= 600 && var.max_run_duration_seconds <= 604800
    error_message = "max_run_duration_seconds must be between 600 (10 minutes) and 604800 (7 days)."
  }
}

variable "labels" {
  description = "Additional labels applied to the trainer. The run-id label is added automatically."
  type        = map(string)
  default = {
    managed-by = "terraform"
    purpose    = "detection-training"
  }
  nullable = false
}

# ---------------------------------------------------------------------------
# Training container contract
# ---------------------------------------------------------------------------

variable "training_image" {
  description = "Digest-pinned detection training image from Artifact Registry."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9._/@:-]*@sha256:[0-9a-f]{64}$", var.training_image))
    error_message = "training_image must be a lowercase, digest-pinned container image reference."
  }
}

variable "mlflow_tracking_uri" {
  description = "MLflow tracking URI. Defaults to the local SQLite store on the training SSD."
  type        = string
  default     = "sqlite:////data/mlflow.db"
  nullable    = false

  validation {
    condition     = can(regex("^(https://|sqlite:|http://127\\.0\\.0\\.1(:[0-9]+)?(/|$)|http://localhost(:[0-9]+)?(/|$))", var.mlflow_tracking_uri))
    error_message = "mlflow_tracking_uri must be an HTTPS endpoint, a SQLite URI, or a loopback HTTP URI."
  }
}

variable "local_ssd_mount_dir" {
  description = "Host path where the single NVMe Local SSD is mounted."
  type        = string
  default     = "/mnt/disks/ssd"
  nullable    = false

  validation {
    condition     = startswith(var.local_ssd_mount_dir, "/mnt/")
    error_message = "local_ssd_mount_dir must be an absolute mount path below /mnt."
  }
}

variable "dataset_host_mount_dir" {
  description = "Host path on the mounted Local SSD that holds the staged Dataset Artifact payload and its dataset-artifact.json provenance manifest."
  type        = string
  default     = "/mnt/disks/ssd/dataset-artifact"
  nullable    = false

  validation {
    condition     = startswith(var.dataset_host_mount_dir, "${trimsuffix(var.local_ssd_mount_dir, "/")}/")
    error_message = "dataset_host_mount_dir must be beneath local_ssd_mount_dir."
  }
}

variable "dataset_container_mount_dir" {
  description = "Container path mapped to dataset_host_mount_dir through the /data bind mount."
  type        = string
  default     = "/data/dataset-artifact"
  nullable    = false

  validation {
    condition     = startswith(var.dataset_container_mount_dir, "/data/")
    error_message = "dataset_container_mount_dir must be beneath the /data SSD bind mount."
  }

  validation {
    condition = var.dataset_container_mount_dir == replace(
      var.dataset_host_mount_dir, trimsuffix(var.local_ssd_mount_dir, "/"), "/data"
    )
    error_message = "dataset_container_mount_dir must be dataset_host_mount_dir with local_ssd_mount_dir replaced by /data."
  }
}
