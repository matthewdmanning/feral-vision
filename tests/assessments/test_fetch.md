# test_fetch.py

## Module-level tests

### test_fetch_data_returns_resolved_existing_local_directory

Purpose: Verify local data acquisition resolves an existing directory to its canonical path.

Load-bearing: True

Occurrence probability: 4

#### tmp_path

### test_fetch_data_rejects_non_local_uri_schemes

Purpose: Verify the local data boundary rejects unsupported HTTP and object-storage URI schemes.

Load-bearing: True

Occurrence probability: 2

#### source

### test_fetch_data_rejects_missing_local_path

Purpose: Verify local acquisition fails explicitly when the requested path does not exist.

Load-bearing: True

Occurrence probability: 2

#### tmp_path

### test_fetch_coco_filters_animal_records_and_skips_existing_downloads

Purpose: Verify COCO acquisition filters to animal records and is idempotent for cached annotations and images.

Load-bearing: True

Occurrence probability: 2

#### tmp_path

#### monkeypatch
