# test_annotations.py

## Module-level tests

### test_mask_annotation_load_materializes_fixture_pixels

Purpose: Verify lazy mask loading reads fixture pixels into the annotation.

Load-bearing: True

Occurrence probability: 4

#### mask_annotation_path

### test_mask_annotation_load_keeps_preloaded_mask

Purpose: Verify already-materialized masks bypass filesystem loading.

Load-bearing: False

Occurrence probability: 2

Rationale: This verifies an already-materialized optimization path rather than
the on-disk annotation contract used to create a sample.

#### preloaded_mask

### test_mask_annotation_load_missing_file_raises

Purpose: Verify a missing mask path fails explicitly instead of producing invalid data.

Load-bearing: True

Occurrence probability: 2

#### tmp_path

### test_bbox_annotation_load_parses_yolo_rows

Purpose: Verify YOLO rows become normalized boxes and integer class IDs with empty and populated cases.

Load-bearing: True

Occurrence probability: 4

#### tmp_path

#### yolo_rows

### test_bbox_annotation_load_keeps_preloaded_values

Purpose: Verify preloaded bounding boxes and class IDs remain unchanged.

Load-bearing: False

Occurrence probability: 2

Rationale: Preserving preloaded values is a convenience path; malformed or
missing source annotations are the load-bearing failures.

#### default

### test_pose_annotation_load_reports_unsupported_format

Purpose: Verify unsupported pose loading reports an explicit implementation boundary.

Load-bearing: False

Occurrence probability: 1

Rationale: Pose support is not part of the currently supported workflow.

#### tmp_path
