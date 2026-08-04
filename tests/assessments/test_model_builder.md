# test_model_builder.py

## Module-level tests

### test_model_builder_builds_local_model_with_batched_logits

Purpose: Verify the configured local model builds as a PyTorch module and emits ten-class logits for arbitrary supported batch sizes.

Load-bearing: True

Occurrence probability: 3

Rationale: Model construction occurs per run, but this test checks only type and
output shape, not task semantics or learned behavior.

#### built_local_model

#### local_model_input
