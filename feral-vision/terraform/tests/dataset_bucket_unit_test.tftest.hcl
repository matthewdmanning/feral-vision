# Plan assertions inspect configured values; mocks supply no policy defaults.
mock_provider "google" {}

run "dataset_bucket_preserves_storage_and_access_policy" {
  command = plan
  module { source = "../buckets/dataset" }
  variables {
    bucket_name = "test-dataset-catalogue"
    location    = "US-EAST4"
    project_id  = "test-project"
  }
  assert {
    condition = (
      google_storage_bucket.dataset.name == "test-dataset-catalogue" &&
      google_storage_bucket.dataset.location == "US-EAST4" &&
      output.bucket_name == "test-dataset-catalogue"
    )
    error_message = "Bucket identity, location, and output must preserve caller inputs."
  }
  assert {
    condition = (
      google_storage_bucket.dataset.uniform_bucket_level_access &&
      google_storage_bucket.dataset.public_access_prevention == "enforced"
    )
    error_message = "Dataset access must use uniform IAM and enforce public-access prevention."
  }
  assert {
    condition = (
      google_storage_bucket.dataset.storage_class == "STANDARD" &&
      google_storage_bucket.dataset.enable_object_retention &&
      google_storage_bucket.dataset.versioning[0].enabled == false &&
      google_storage_bucket.dataset.soft_delete_policy[0].retention_duration_seconds == 604800
    )
    error_message = "Dataset storage must retain STANDARD class, Object Retention Lock support, disabled versioning, and seven-day soft delete."
  }
}
