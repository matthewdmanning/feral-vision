# test_detection_task_adapter.py

## Module-level tests

### test_collate_keeps_variable_box_counts_and_normalized_images

Purpose: Verify detection collation retains variable numbers of labelled boxes and normalizes image batches.

Load-bearing: True

Occurrence probability: 4

#### default

### test_collate_rejects_class_ids_outside_the_selected_taxonomy

Purpose: Verify labels outside the selected taxonomy are rejected before native target assignment.

Load-bearing: True

Occurrence probability: 2

#### default

### test_loss_reuses_native_assignment_and_replaces_box_component_with_giou

Purpose: Verify detection loss preserves native assignment and combines native classification with GIoU.

Load-bearing: True

Occurrence probability: 4

#### default
