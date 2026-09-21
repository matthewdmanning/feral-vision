# Contract tests for terraform/runs/detection.
#
# These run against a mocked Google provider: they prove the configuration's
# own contracts without reaching Google Cloud or needing credentials.
#
#   terraform -chdir=terraform/tests test

mock_provider "google" {}

override_data {
  target = data.google_storage_bucket.dataset
  values = {
    name = "mobile-training-images"
  }
}

override_data {
  target = data.google_compute_subnetwork.training
  values = {
    self_link = "projects/test-project/regions/us-east4/subnetworks/default"
    network   = "projects/test-project/global/networks/default"
  }
}

variables {
  run_id                       = "run-20260921-abc"
  project_id                   = "test-project"
  service_account_email        = "trainer@test-project.iam.gserviceaccount.com"
  training_image               = "us-east4-docker.pkg.dev/test-project/feral-docker/trainer@sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  dataset_artifact_prefix      = "datasets/coco/train2017/variant-a"
  source_annotation_generation = "1756000000000001"
  artifact_prefix              = "gs://feral-vision-operations-us-east4/runs/detection"
}

# Every run-scoped name must derive from run_id. This is the contract that
# stops two concurrent runs from contending for one VM, router, or NAT.
run "run_scoped_names_derive_from_run_id" {
  command = plan
  module { source = "../runs/detection" }

  assert {
    condition     = output.trainer_instance_name == "feral-vision-detection-run-20260921-abc"
    error_message = "Trainer instance name must derive from run_id."
  }

  assert {
    condition     = output.cloud_nat_router_name == "feral-vision-detection-run-20260921-abc-router"
    error_message = "Cloud Router name must derive from run_id."
  }

  assert {
    condition     = output.run_artifact_uri == "gs://feral-vision-operations-us-east4/runs/detection/run-20260921-abc"
    error_message = "Run artifact URI must be scoped to run_id."
  }
}

# The run trains on exactly one prefix in the dataset-only bucket.
run "dataset_uri_resolves_against_the_dataset_bucket" {
  command = plan
  module { source = "../runs/detection" }

  assert {
    condition     = output.dataset_artifact_uri == "gs://mobile-training-images/datasets/coco/train2017/variant-a"
    error_message = "Dataset Artifact URI must resolve against the dataset-only bucket and the selected prefix."
  }
}

# The subnetwork is read, never owned: the trainer attaches to the value the
# data source returned, so destroying a run cannot reach shared network
# infrastructure.
run "trainer_attaches_to_the_read_subnetwork" {
  command = plan
  module { source = "../runs/detection" }

  assert {
    condition     = module.trainer.subnetwork == "projects/test-project/regions/us-east4/subnetworks/default"
    error_message = "The trainer must attach to the subnetwork read from the data source."
  }
}

# Cloud NAT is optional so a run can reuse existing regional egress instead of
# contending for a router that another configuration already owns.
run "cloud_nat_can_be_disabled" {
  command = plan
  module { source = "../runs/detection" }

  variables {
    create_cloud_nat = false
  }

  assert {
    condition     = output.cloud_nat_router_name == null
    error_message = "Disabling create_cloud_nat must not create a Cloud Router."
  }
}

# --- Input contracts --------------------------------------------------------

run "rejects_artifact_prefix_inside_the_dataset_bucket" {
  command = plan
  module { source = "../runs/detection" }

  variables {
    artifact_prefix = "gs://mobile-training-images/runs/detection"
  }

  expect_failures = [var.artifact_prefix]
}

run "rejects_a_mutable_training_image_tag" {
  command = plan
  module { source = "../runs/detection" }

  variables {
    training_image = "us-east4-docker.pkg.dev/test-project/feral-docker/trainer:latest"
  }

  expect_failures = [var.training_image]
}

run "rejects_a_gs_uri_as_the_dataset_prefix" {
  command = plan
  module { source = "../runs/detection" }

  variables {
    dataset_artifact_prefix = "gs://mobile-training-images/datasets/coco/train2017/variant-a"
  }

  expect_failures = [var.dataset_artifact_prefix]
}

run "rejects_an_unpinned_annotation_generation" {
  command = plan
  module { source = "../runs/detection" }

  variables {
    source_annotation_generation = "latest"
  }

  expect_failures = [var.source_annotation_generation]
}

run "rejects_a_container_mount_that_does_not_match_the_host_mount" {
  command = plan
  module { source = "../runs/detection" }

  variables {
    dataset_host_mount_dir      = "/mnt/disks/ssd/dataset-artifact"
    dataset_container_mount_dir = "/data/somewhere-else"
  }

  expect_failures = [var.dataset_container_mount_dir]
}

run "rejects_plaintext_http_to_a_remote_mlflow_host" {
  command = plan
  module { source = "../runs/detection" }

  variables {
    mlflow_tracking_uri = "http://mlflow.example.com:5000"
  }

  expect_failures = [var.mlflow_tracking_uri]
}

run "rejects_a_flex_start_trainer_that_is_not_deleted_at_its_limit" {
  command = plan
  module { source = "../runs/detection" }

  variables {
    provisioning_model          = "FLEX_START"
    instance_termination_action = "STOP"
  }

  expect_failures = [var.instance_termination_action]
}
