# Harness root for Terraform contract tests.
#
# This directory holds no infrastructure of its own. Each run block in a
# *.tftest.hcl file points at the run module under test, which keeps every
# Terraform test file in terraform/tests/ as the testing boundary requires.
terraform {
  required_version = "~> 1.15"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}
