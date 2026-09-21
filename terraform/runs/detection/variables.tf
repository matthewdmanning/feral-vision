# ---------------------------------------------------------------------------
# Run identity
# ---------------------------------------------------------------------------

variable "run_id" {
  description = "Unique identifier for this detection training run. Every run-scoped Cloud Resource name is derived from it so two runs can never contend for the same resource."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z]([a-z0-9-]{1,48}[a-z0-9])$", var.run_id))
    error_message = "run_id must be 3-50 characters, lowercase alphanumeric or hyphen, and start with a letter and end with a letter or digit."
  }
}

variable "project_id" {
  description = "GCP project that owns the training VM, Cloud Router, and Cloud NAT created by this root."
  type        = string
  nullable    = false
}

variable "region" {
  description = "Region containing the training subnetwork, Cloud Router, and Cloud NAT."
  type        = string
  default     = "us-east4"
  nullable    = false
}

variable "zone" {
  description = "Compute Engine zone for the training VM. Must be inside var.region."
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
  description = "Dataset Artifact prefix below the dataset bucket, for example datasets/coco/train2017/<artifact>. Every training input is derived from this one prefix; the startup script never searches other prefixes for images."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^datasets/[A-Za-z0-9._/-]+$", var.dataset_artifact_prefix))
    error_message = "dataset_artifact_prefix must be a datasets/ prefix without a gs:// URI or a trailing slash."
  }

  validation {
    condition     = !endswith(var.dataset_artifact_prefix, "/")
    error_message = "dataset_artifact_prefix must not end with a slash."
  }
}

variable "source_annotation_generation" {
  description = "Retained Cloud Storage object generation of payload/annotations/instances.json, copied directly to the training SSD so the run pins an immutable annotation."
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
  description = "Writable gs:// prefix for MLflow outputs, checkpoints, Model Artifacts, and training evidence. ADR 0002 requires this to be an operational location that is not the dataset bucket."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^gs://[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]/[A-Za-z0-9._/-]+$", var.artifact_prefix))
    error_message = "artifact_prefix must be a gs://<bucket>/<prefix> URI."
  }

  validation {
    condition     = split("/", trimprefix(var.artifact_prefix, "gs://"))[0] != var.bucket_name
    error_message = "artifact_prefix must not live in the dataset bucket; the dataset bucket is never used for MLflow artifacts or operational storage."
  }
}

# ---------------------------------------------------------------------------
# Network (read-only; this root never owns a subnetwork)
# ---------------------------------------------------------------------------

variable "subnetwork_name" {
  description = "Name of the existing subnetwork the training VM attaches to. It is read through a data source and is never managed, imported, or modified by this root."
  type        = string
  default     = "default"
  nullable    = false
}

variable "create_cloud_nat" {
  description = "Whether this root creates a run-scoped Cloud Router and Cloud NAT for egress. Set to false when the subnetwork already has regional NAT egress, so two roots never contend for one NAT."
  type        = bool
  default     = true
  nullable    = false
}

variable "instance_tags" {
  description = "Network tags applied to the training VM."
  type        = list(string)
  default     = ["cloud-detection-gpu"]
  nullable    = false
}

# ---------------------------------------------------------------------------
# VM shape and lifecycle
# ---------------------------------------------------------------------------

variable "machine_type" {
  description = "Compute Engine machine type for the GPU trainer."
  type        = string
  default     = "n1-standard-4"
  nullable    = false
}

variable "gpu_type" {
  description = "Compute Engine accelerator type attached to the trainer."
  type        = string
  default     = "nvidia-tesla-t4"
  nullable    = false
}

variable "accelerator_count" {
  description = "Number of GPU accelerator cards attached to the trainer."
  type        = number
  default     = 1
  nullable    = false

  validation {
    condition     = var.accelerator_count > 0
    error_message = "accelerator_count must be positive; this root only provisions GPU trainers."
  }
}

variable "provisioning_model" {
  description = "Compute Engine provisioning model for the trainer."
  type        = string
  default     = "FLEX_START"
  nullable    = false

  validation {
    condition     = contains(["STANDARD", "SPOT", "FLEX_START"], var.provisioning_model)
    error_message = "provisioning_model must be STANDARD, SPOT, or FLEX_START."
  }
}

variable "instance_termination_action" {
  description = "Action when the trainer reaches its maximum run duration."
  type        = string
  default     = "DELETE"
  nullable    = false

  validation {
    condition     = contains(["DELETE", "STOP"], var.instance_termination_action)
    error_message = "instance_termination_action must be DELETE or STOP."
  }

  validation {
    condition     = var.provisioning_model != "FLEX_START" || var.instance_termination_action == "DELETE"
    error_message = "A FLEX_START trainer must use instance_termination_action = DELETE."
  }
}

variable "max_run_duration_seconds" {
  description = "Maximum trainer run duration before Compute Engine applies instance_termination_action. This is the cost ceiling on a disposable VM, not a training-time estimate."
  type        = number
  default     = 86400
  nullable    = false

  validation {
    condition     = var.max_run_duration_seconds >= 600 && var.max_run_duration_seconds <= 604800
    error_message = "max_run_duration_seconds must be between 600 (10 minutes) and 604800 (7 days)."
  }
}

variable "on_host_maintenance" {
  description = "Compute Engine host-maintenance action. A GPU trainer cannot live-migrate, so this must be TERMINATE."
  type        = string
  default     = "TERMINATE"
  nullable    = false

  validation {
    condition     = var.on_host_maintenance == "TERMINATE"
    error_message = "on_host_maintenance must be TERMINATE; an instance with an attached GPU cannot live-migrate."
  }
}

variable "automatic_restart" {
  description = "Whether Compute Engine automatically restarts the trainer. A disposable run VM must not silently restart and repeat training."
  type        = bool
  default     = false
  nullable    = false

  validation {
    condition     = var.provisioning_model == "STANDARD" || var.automatic_restart == false
    error_message = "automatic_restart must be false for a SPOT or FLEX_START trainer."
  }
}

variable "deep_learning_image_family" {
  description = "GPU-enabled PyTorch Deep Learning VM image family used for the boot disk."
  type        = string
  default     = "pytorch-2-9-cu129-ubuntu-2204-nvidia-580"
  nullable    = false
}

variable "deep_learning_image_project" {
  description = "Google-managed project that publishes the boot image family."
  type        = string
  default     = "deeplearning-platform-release"
  nullable    = false
}

variable "boot_disk_size_gb" {
  description = "Trainer boot disk size in gigabytes. The Dataset payload is staged on the local SSD, not here."
  type        = number
  default     = 100
  nullable    = false

  validation {
    condition     = var.boot_disk_size_gb >= 50
    error_message = "boot_disk_size_gb must be at least 50; the Deep Learning image and CUDA driver do not fit below that."
  }
}

variable "boot_disk_type" {
  description = "Trainer boot disk type."
  type        = string
  default     = "pd-ssd"
  nullable    = false
}

variable "scratch_disk_interface" {
  description = "Local SSD interface. The Dataset payload is staged on this disk, so it is required."
  type        = string
  default     = "NVME"
  nullable    = false

  validation {
    condition     = contains(["NVME", "SCSI"], var.scratch_disk_interface)
    error_message = "scratch_disk_interface must be NVME or SCSI."
  }
}

variable "service_account_email" {
  description = "Existing VM service account with reviewed dataset-read, artifact-write, and image-pull access. This root never creates or modifies IAM."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[^@]+@[^@]+\\.iam\\.gserviceaccount\\.com$", var.service_account_email))
    error_message = "service_account_email must be an existing service account address."
  }
}

variable "instance_metadata" {
  description = "Metadata applied to the trainer."
  type        = map(string)
  default = {
    enable-oslogin        = "TRUE"
    install-nvidia-driver = "True"
  }
  nullable = false
}

variable "labels" {
  description = "Labels applied to the trainer. The run_id label is added automatically."
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
  description = "Digest-pinned detection training image from Artifact Registry. A mutable tag is rejected so a plan always names one immutable image."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9._/@:-]*@sha256:[0-9a-f]{64}$", var.training_image))
    error_message = "training_image must be a lowercase, digest-pinned container image reference."
  }
}

variable "run_config_name" {
  description = "Hydra Run Recipe consumed by the training container."
  type        = string
  default     = "runs/baseline"
  nullable    = false

  validation {
    condition     = can(regex("^runs/[A-Za-z0-9_-]+$", var.run_config_name))
    error_message = "run_config_name must name a Run Recipe below conf/runs/."
  }
}

variable "mlflow_tracking_uri" {
  description = "MLflow tracking URI. Defaults to the local SQLite store on the training SSD; a loopback URI is accepted for a VM-local tracking server. The local store is exported to artifact_prefix before teardown."
  type        = string
  default     = "sqlite:////data/mlflow.db"
  nullable    = false

  validation {
    condition     = can(regex("^(https://|sqlite:|http://127\\.0\\.0\\.1(:[0-9]+)?(/|$)|http://localhost(:[0-9]+)?(/|$))", var.mlflow_tracking_uri))
    error_message = "mlflow_tracking_uri must be an HTTPS endpoint, a SQLite URI, or a loopback HTTP URI. Plaintext HTTP to a remote host is rejected."
  }
}

variable "local_ssd_mount_dir" {
  description = "Host path where the local SSD is mounted."
  type        = string
  default     = "/mnt/disks/ssd"
  nullable    = false
}

variable "dataset_host_mount_dir" {
  description = "Host path on the mounted local SSD that holds the staged Dataset payload and the locally generated DVC tracker and lock."
  type        = string
  default     = "/mnt/disks/ssd/dataset-artifact"
  nullable    = false

  validation {
    condition     = startswith(var.dataset_host_mount_dir, var.local_ssd_mount_dir)
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

  # The local SSD is bind-mounted at /data, so the container path must be the
  # host path with local_ssd_mount_dir swapped for /data. A mismatched pair
  # silently stages the payload where the trainer will not look for it.
  validation {
    condition = var.dataset_container_mount_dir == replace(
      var.dataset_host_mount_dir, var.local_ssd_mount_dir, "/data"
    )
    error_message = "dataset_container_mount_dir must be dataset_host_mount_dir with local_ssd_mount_dir replaced by /data."
  }
}
