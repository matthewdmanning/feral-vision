# test_dataset_loading.py

## Module-level tests

### test_source_len_equals_paired_file_count

Purpose: Verify DatasetSource length equals the number of paired image and annotation files.

Load-bearing: True

Occurrence probability: 4

#### tmp_path

### test_source_load_returns_uint8_tensor

Purpose: Verify source loading returns images as uint8 tensors.

Load-bearing: True

Occurrence probability: 4

#### tmp_path

### test_source_load_image_shape_is_chw

Purpose: Verify source loading converts RGB images to channel-first tensors while preserving dimensions.

Load-bearing: True

Occurrence probability: 4

#### tmp_path

### test_source_load_annotation_count_matches_annotation_files

Purpose: Verify source loading returns the expected annotation objects for a paired sample.

Load-bearing: True

Occurrence probability: 4

#### tmp_path

### test_source_unmatched_image_raises

Purpose: Verify an image without a matching annotation fails during source construction.

Load-bearing: True

Occurrence probability: 2

#### tmp_path

### test_source_partition_slices_are_complete_contiguous_and_ordered

Purpose: Verify worker partitions cover every source sample exactly once in source order.

Load-bearing: True

Occurrence probability: 3

Rationale: Worker partitioning is important for avoiding data loss or
duplication, but the test reaches into private `_index` state rather than
proving the public loading behavior.

#### tmp_path

#### n

#### num_workers

### test_source_partition_is_loadable

Purpose: Verify a worker partition remains loadable and preserves image tensor conventions.

Load-bearing: True

Occurrence probability: 3

#### tmp_path

### test_dataset_len_delegates_to_source

Purpose: Verify AnnotationDataset exposes its source length.

Load-bearing: True

Occurrence probability: 4

#### default

### test_dataset_getitem_returns_source_image

Purpose: Verify AnnotationDataset indexing returns the source sample at the requested index.

Load-bearing: True

Occurrence probability: 4

#### default

### test_dataset_target_transform_applied

Purpose: Verify AnnotationDataset applies a configured target transform.

Load-bearing: True

Occurrence probability: 3

#### default

### test_dataset_image_transform_applied

Purpose: Verify AnnotationDataset applies a configured image transform.

Load-bearing: True

Occurrence probability: 3

#### default

### test_dataset_no_transform_returns_raw_annotations

Purpose: Verify AnnotationDataset returns raw annotations when no target transform is configured.

Load-bearing: True

Occurrence probability: 3

#### default

### test_streaming_dataset_yields_all_samples

Purpose: Verify StreamingAnnotationDataset iterates over every source sample.

Load-bearing: True

Occurrence probability: 3

#### default

### test_streaming_dataset_applies_target_transform

Purpose: Verify StreamingAnnotationDataset applies its target transform to each yielded sample.

Load-bearing: True

Occurrence probability: 3

#### default

### test_fixture_dataset_all_images_load

Purpose: Verify the repository fixture dataset loads every image with the supported uint8 CHW contract.

Load-bearing: False

Occurrence probability: 2

Rationale: This is a repository-fixture check, not an independent
production data contract.

#### fixture_dataset

### test_fixture_dataset_mask_transform_produces_class_id_tensor

Purpose: Verify fixture masks transform into two-dimensional int64 class-ID tensors.

Load-bearing: True

Occurrence probability: 3

#### fixture_dataset_root

#### mask_to_tensor
