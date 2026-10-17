variable "bucket_name" {
  description = "Name of the dataset-only bucket that holds Dataset Artifacts."
  type        = string
  nullable    = false
}

variable "location" {
  description = "Location of the dataset-only bucket."
  type        = string
  nullable    = false
}

variable "project_id" {
  description = "Project that owns the dataset-only bucket."
  type        = string
  nullable    = false
}
