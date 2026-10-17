terraform {
  required_version = "~> 1.16"

  backend "gcs" {
    bucket = "feral-vision-operations-us-east4"
    prefix = "terraform/runs/detection"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.0"
    }
  }
}
