terraform {
  required_version = "~> 1.16"

  backend "gcs" {
    bucket = "YOUR_OPERATIONS_BUCKET"
    prefix = "terraform/runs/detection"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.0"
    }
  }
}
