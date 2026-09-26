# Contract tests for terraform/runs/detection.
#
# These run against a mocked Google provider: they prove the configuration's
# own contracts without reaching Google Cloud or needing credentials.
#
#   terraform -chdir=terraform/tests init
#   terraform -chdir=terraform/tests test

mock_provider "google" {}

override_data {
  target = data.google_storage_bucket.dataset
  values = {
    name = "mobile-training-images"
  }
}

override_data {
  target = data.google_compute_network.training
  values = {
    self_link               = "projects/test-project/global/networks/default"
    auto_create_subnetworks = true
  }
}

override_data {
  target = data.google_compute_image.trainer_boot
  values = {
    self_link = "https://www.googleapis.com/compute/v1/projects/deeplearning-platform-release/global/images/pytorch-2-9-cu129-ubuntu-2204-nvidia-580-v20260901"
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

run "single_gpu_trainer_shape_is_fixed" {
  command = plan
  module { source = "../runs/detection" }

  assert {
    condition     = output.trainer_instance_name == "feral-vision-detection-run-20260921-abc"
    error_message = "Trainer instance name must derive from run_id."
  }

  assert {
    condition     = length(output.trainer_instance_name) <= 63
    error_message = "Generated trainer name must fit the Compute Engine 63-character limit."
  }

  assert {
    condition     = google_compute_instance.trainer.machine_type == "n1-standard-4"
    error_message = "The one-off trainer must use the reviewed n1-standard-4 shape."
  }

  assert {
    condition = (
      length(google_compute_instance.trainer.guest_accelerator) == 1 &&
      google_compute_instance.trainer.guest_accelerator[0].type == "nvidia-tesla-t4" &&
      google_compute_instance.trainer.guest_accelerator[0].count == 1
    )
    error_message = "The trainer must attach exactly one NVIDIA T4."
  }

  assert {
    condition = (
      length(google_compute_instance.trainer.scratch_disk) == 1 &&
      google_compute_instance.trainer.scratch_disk[0].interface == "NVME"
    )
    error_message = "The trainer must attach exactly one NVMe Local SSD."
  }

  assert {
    condition = (
      google_compute_instance.trainer.scheduling[0].provisioning_model == "FLEX_START" &&
      google_compute_instance.trainer.scheduling[0].on_host_maintenance == "TERMINATE" &&
      google_compute_instance.trainer.scheduling[0].automatic_restart == false &&
      google_compute_instance.trainer.scheduling[0].instance_termination_action == "DELETE"
    )
    error_message = "The disposable GPU trainer must keep the reviewed Flex-start lifecycle."
  }

  assert {
    condition     = length(google_compute_instance.trainer.network_interface[0].access_config) == 1
    error_message = "The trainer needs one ephemeral external address because this root does not manage Cloud NAT."
  }

  assert {
    condition = (
      length(google_compute_instance.trainer.service_account) == 1 &&
      contains(google_compute_instance.trainer.service_account[0].scopes, "cloud-platform")
    )
    error_message = "The trainer must use the existing service account with cloud-platform scope."
  }

  assert {
    condition     = output.boot_image == "https://www.googleapis.com/compute/v1/projects/deeplearning-platform-release/global/images/pytorch-2-9-cu129-ubuntu-2204-nvidia-580-v20260901"
    error_message = "The plan must pin the concrete DLVM image resolved from the NVIDIA-580 family."
  }

  assert {
    condition     = !contains(keys(google_compute_instance.trainer.metadata), "install-nvidia-driver")
    error_message = "The NVIDIA-580 DLVM image already includes the driver; startup must not schedule a first-boot reinstall/reboot."
  }

  assert {
    condition     = output.run_artifact_uri == "gs://feral-vision-operations-us-east4/runs/detection/run-20260921-abc"
    error_message = "Run artifact URI must be scoped to run_id."
  }

  assert {
    condition     = strcontains(google_compute_instance.trainer.metadata_startup_script, "runs/detection")
    error_message = "The startup script must use the single canonical training recipe."
  }

  assert {
    condition     = strcontains(google_compute_instance.trainer.metadata_startup_script, "dataset-artifact.json")
    error_message = "The startup script must preserve the Dataset Artifact manifest seam."
  }

  assert {
    condition = (
      !strcontains(lower(google_compute_instance.trainer.metadata_startup_script), "dvc init") &&
      !strcontains(lower(google_compute_instance.trainer.metadata_startup_script), "dvc repro") &&
      !strcontains(lower(google_compute_instance.trainer.metadata_startup_script), "dvc.lock")
    )
    error_message = "The GPU runtime must not re-version the published Dataset Artifact with DVC."
  }
}

run "dataset_uri_resolves_against_the_dataset_bucket" {
  command = plan
  module { source = "../runs/detection" }

  assert {
    condition     = output.dataset_artifact_uri == "gs://mobile-training-images/datasets/coco/train2017/variant-a"
    error_message = "Dataset Artifact URI must resolve against the dataset-only bucket and the selected prefix."
  }
}

run "trainer_attaches_to_the_read_auto_mode_network" {
  command = plan
  module { source = "../runs/detection" }

  assert {
    condition     = output.trainer_network == "projects/test-project/global/networks/default"
    error_message = "The trainer must attach to the network read from the data source."
  }
}

run "rejects_run_id_that_would_overflow_vm_name" {
  command = plan
  module { source = "../runs/detection" }

  variables {
    run_id = "run-abcdefghijklmnopqrstuvwxyz0123456789x"
  }

  expect_failures = [var.run_id]
}

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
