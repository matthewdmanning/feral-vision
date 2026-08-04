# test_optim.py

## Module-level tests

### test_build_optimizer_binds_real_variant_and_updates_image_model

Purpose: Verify every selected optimizer variant binds model parameters and performs an update.

Load-bearing: True

Occurrence probability: 4

#### image_model

#### optimizer_cfg

### test_build_scheduler_binds_every_real_variant

Purpose: Verify every selected scheduler variant binds the constructed optimizer.

Load-bearing: True

Occurrence probability: 3

#### image_model

#### scheduler_cfg

### test_build_scheduler_none_disables_scheduling

Purpose: Verify an absent scheduler configuration disables scheduling without creating a scheduler.

Load-bearing: True

Occurrence probability: 2

#### image_model

### test_build_loss_fn_instantiates_every_real_variant

Purpose: Verify every selectable loss configuration instantiates its declared loss class.

Load-bearing: True

Occurrence probability: 3

#### loss_cfg
