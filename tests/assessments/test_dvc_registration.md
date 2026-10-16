# test_dvc_registration.py

## test_register_restores_selected_dataset_without_tracking_other_data

Purpose: Run the real registration shell script against DVC and a local remote,
then remove the selected Dataset and cache and prove remote recovery. Verify
another Dataset remains untouched, generated metadata can be tracked by Git,
repeat registration preserves its identity, and the publisher Dockerfile does
not break repository-wide status.

Load-bearing: True

Occurrence probability: 3

Fixture: `dvc_repo`, with one real image/label pair and unrelated local data.

## test_register_rejects_invalid_dataset_before_recording_metadata

Purpose: Reject an incomplete Dataset or a directory outside the selected DVC
repository before creating metadata or cache entries.

Load-bearing: True

Occurrence probability: 3

Fixture: `dvc_repo`, `tmp_path`; incomplete and outside-repository directories.
