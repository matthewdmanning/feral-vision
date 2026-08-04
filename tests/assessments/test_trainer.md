# test_trainer.py

## Module-level tests

### test_fit_runs_and_returns_history_for_each_epoch

Purpose: Verify Trainer.fit completes the configured epoch count and returns finite training history.

Load-bearing: True

Occurrence probability: 5

#### tmp_path

#### epochs

### test_fit_best_loss_is_minimum_train_loss_when_no_validation

Purpose: Verify training loss determines the best loss when validation is absent.

Load-bearing: True

Occurrence probability: 3

#### tmp_path

### test_fit_writes_best_checkpoint

Purpose: Verify training persists a loadable best-model checkpoint at the configured path.

Load-bearing: True

Occurrence probability: 4

#### tmp_path

### test_fit_creates_nested_parent_dir_for_checkpoint

Purpose: Verify checkpoint persistence creates missing parent directories for a nested target path.

Load-bearing: True

Occurrence probability: 3

#### tmp_path

### test_fit_tracks_metrics_and_best_checkpoint_in_configured_mlflow_run

Purpose: Verify a training run logs its model signature, DVC lineage, resolved configuration, checkpoint model, and registry version to MLflow.

Load-bearing: True

Occurrence probability: 3

#### tmp_path

### test_fit_logs_best_model_weights_not_final_epoch_weights

Purpose: Verify MLflow receives the selected best weights rather than the final epoch weights.

Load-bearing: True

Occurrence probability: 3

#### tmp_path

### test_scheduler_steps_once_per_epoch

Purpose: Verify the scheduler advances exactly once per training epoch.

Load-bearing: True

Occurrence probability: 4

#### tmp_path

#### epochs

#### gamma

### test_base_validate_returns_empty_dict_and_falls_back_to_train_loss

Purpose: Verify the base validation hook preserves train-loss checkpoint selection when it reports no validation metrics.

Load-bearing: True

Occurrence probability: 3

#### tmp_path

#### trainer_fixture_dataset

### test_validate_metric_is_tracked_per_epoch_using_real_dataset

Purpose: Verify a validation metric from the real dataset is recorded once for every epoch.

Load-bearing: True

Occurrence probability: 3

#### tmp_path

#### trainer_fixture_dataset

#### epochs

### test_validate_metric_drives_checkpoint_selection_over_train_loss

Purpose: Verify a reported validation metric drives best-checkpoint selection instead of training loss.

Load-bearing: True

Occurrence probability: 3

#### tmp_path

#### trainer_fixture_dataset

### test_bbox_net_output_shape_matches_num_boxes

Purpose: Verify the bounding-box network emits four coordinates per configured box across input channels, formats, and image sizes.

Load-bearing: True

Occurrence probability: 3

#### bbox_net_factory

#### in_channels

#### num_boxes

#### box_format

#### image_size

### test_bbox_net_factory_rejects_invalid_box_format

Purpose: Verify the bounding-box network factory rejects unsupported coordinate formats.

Load-bearing: True

Occurrence probability: 2

#### bbox_net_factory

#### invalid_format

### test_fit_trains_bbox_net_toward_real_annotation_boxes

Purpose: Verify the training loop performs finite optimizer updates against targets loaded from real YOLO annotations using configured optimizer and loss variants; it does not prove convergence.

Load-bearing: True

Occurrence probability: 3

#### tmp_path

#### bbox_net_factory

#### box_format

#### batch_size

#### optim_target

#### loss_fn_target

#### rows
