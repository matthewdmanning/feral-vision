# test_cloud_preflight.py

## Module-level tests

### test_get_compute_instance_calls_selected_compute_endpoint

Purpose: Verify cloud preflight requests and returns the manifest-selected Compute Engine instance.

Load-bearing: True

Occurrence probability: 3

Rationale: A preflight is operationally important, but this test covers only
the successful request path rather than the complete readiness decision.

#### default
