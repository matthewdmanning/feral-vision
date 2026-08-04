# test_augmentations.py

## Module-level tests

### test_direct_albumentations_pipeline_empty_config_preserves_input

Purpose: Verify an empty augmentation configuration preserves the input image exactly.

Load-bearing: True

Occurrence probability: 3

#### uint8_image

### test_direct_albumentations_pipeline_applies_configured_flip

Purpose: Verify configured horizontal and vertical flips transform pixels on the requested axis.

Load-bearing: True

Occurrence probability: 3

#### uint8_image

#### transform_name

#### axis

### test_direct_albumentations_pipeline_forwards_resize_dimensions

Purpose: Verify configured resize dimensions reach the augmentation pipeline output.

Load-bearing: True

Occurrence probability: 3

#### uint8_image

#### height

#### width

### test_transform_construction_rejects_unknown_transform_names

Purpose: Verify unknown and near-typo transform names fail with actionable configuration errors.

Load-bearing: True

Occurrence probability: 2

#### name

#### message

### test_build_augmentation_previews_returns_all_source_pages_as_grids

Purpose: Verify every source image receives a complete two-dimensional augmentation preview grid.

Load-bearing: False

Occurrence probability: 3

Rationale: This protects human-review tooling rather than model training execution.

#### tmp_path

### test_build_augmentation_previews_rejects_duplicate_sweeps

Purpose: Verify duplicate sweep definitions are rejected so preview dimensions remain distinct.

Load-bearing: False

Occurrence probability: 2

Rationale: Duplicate sweeps affect exploratory review output, not the canonical training artifact.

#### tmp_path

### test_build_augmentation_previews_requires_three_non_binary_values

Purpose: Verify non-binary preview sweeps contain enough values for meaningful review.

Load-bearing: False

Occurrence probability: 2

Rationale: This is a local preview-quality constraint.

#### tmp_path

### test_write_augmentation_preview_html_creates_structured_grid_assets

Purpose: Verify the interactive preview writes its index, controls, source badge, and expected image assets.

Load-bearing: False

Occurrence probability: 3

Rationale: The HTML viewer supports operator inspection but is not part of the training runtime.

#### tmp_path

### test_materialize_detection_variant_cotransforms_yolo_boxes_without_duplication

Purpose: Verify detection augmentation transforms each YOLO box with its image and emits one variant sample per source image.

Load-bearing: True

Occurrence probability: 3

#### tmp_path
