# test_postprocess.py

## Module-level tests

### test_clean_mask_removes_isolated_specks_without_eroding_large_components

Purpose: Verify mask cleanup removes isolated foreground specks while preserving large components.

Load-bearing: True

Occurrence probability: 3

#### default

### test_clean_mask_rejects_non_spatial_masks

Purpose: Verify mask cleanup rejects tensors that are not two-dimensional spatial masks.

Load-bearing: True

Occurrence probability: 2

#### shape

### test_masks_to_boxes_returns_exclusive_xyxy_for_each_connected_component

Purpose: Verify each connected mask component becomes an exclusive-coordinate float XYXY box.

Load-bearing: True

Occurrence probability: 3

#### default

### test_masks_to_boxes_filters_components_by_inclusive_pixel_area

Purpose: Verify connected components are filtered using the configured inclusive pixel-area threshold.

Load-bearing: True

Occurrence probability: 3

#### min_box_area

#### expected

### test_masks_to_boxes_returns_empty_float_coordinate_tensor_for_empty_mask

Purpose: Verify an empty mask produces a correctly shaped empty float-coordinate tensor.

Load-bearing: True

Occurrence probability: 2

#### default
