# test_losses.py

## Module-level tests

### test_dice_loss_distinguishes_perfect_and_incorrect_predictions

Purpose: Verify Dice loss is near zero for correct segmentation and materially higher for incorrect predictions across target encodings.

Load-bearing: True

Occurrence probability: 4

#### segmentation_batch

### test_segmentation_loss_applies_configured_component_weights

Purpose: Verify combined segmentation loss applies configured Dice and cross-entropy weights and remains differentiable.

Load-bearing: True

Occurrence probability: 4

#### segmentation_batch

#### dice_weight

#### bce_weight
