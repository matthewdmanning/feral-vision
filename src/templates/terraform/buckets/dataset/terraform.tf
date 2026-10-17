terraform {
  required_version = "~> 1.15"

  backend "gcs" {
    bucket = "YOUR_OPERATIONS_BUCKET"
    prefix = "terraform/buckets/dataset"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}
