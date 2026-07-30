terraform {
  required_version = "~> 1.15"

  backend "gcs" {
    bucket = "feral-vision-operations-us-east4"
    prefix = "terraform/cloud-smoke"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}
