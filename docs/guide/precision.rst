Data types and execution precision
=================================

Choose precision for the actual model, device, runtime, and task. Keep four
choices distinct: Dataset storage dtype, model weights, execution/accumulation
precision, and input/output tensor dtypes. A smaller weight file does not prove
that the runtime uses the same arithmetic. Precision changes require accuracy
benchmarking on the same held-out Dataset and task metrics.

Device choices
--------------

.. list-table:: Candidates to evaluate, rather than universal defaults
   :header-rows: 1
   :widths: 23 30 47

   * - Device/runtime
     - Candidate
     - Practical detail
   * - NVIDIA T4
     - FP32 baseline; FP16 mixed precision
     - Turing has FP16 acceleration, without native BF16 arithmetic. A BF16
       tensor being accepted or emulated does not establish BF16 acceleration.
   * - NVIDIA Ampere/Ada/Hopper, such as A100 and L4
     - BF16 or FP16 mixed precision
     - BF16 offers FP32-like exponent range with fewer significant bits. Check
       model/operator and installed backend support. FP8 needs a supported
       accelerator and an established backend recipe; it is not a general cast.
   * - General CPU, including edge CPUs
     - FP32 baseline; backend-supported BF16 or INT8
     - Native low-precision kernels depend on CPU instructions and runtime.
       FP16 is not a universally faster CPU choice.
   * - NVIDIA Jetson
     - TensorRT FP16; calibrated INT8 where supported
     - Check the exact Jetson, JetPack, TensorRT and GPU/DLA combination. DLA
       support and precision differ from the GPU; do not treat all Jetsons as
       one target or assume the newest desktop TensorRT package is compatible.
   * - Apple Core ML
     - ML Program FP16; FP32 for sensitive operations/models
     - ML Programs default to FP16 compute precision. Exported input/output
       types and compute-unit availability are separate choices.
   * - Android/mobile GPU or NPU via LiteRT
     - Delegate-supported FP16 or calibrated integer quantization
     - The selected delegate determines execution. LiteRT's documented FP16
       weight conversion can expand weights to FP32 on CPU, while supported
       GPU execution can use FP16 arithmetic.

These are hardware/runtime considerations, not a list of inference backends
implemented by this package. See NVIDIA's
`hardware support matrix <https://docs.nvidia.com/deeplearning/tensorrt/archives/tensorrt-1001/pdf/TensorRT-Support-Matrix-Guide.pdf>`_,
the `current runtime matrix <https://docs.nvidia.com/deeplearning/tensorrt/latest/getting-started/support-matrix.html>`_,
`Core ML typed execution <https://apple.github.io/coremltools/docs-guides/source/typed-execution.html>`_,
and `LiteRT FP16 conversion <https://ai.google.dev/edge/litert/conversion/tensorflow/quantization/post_training_float16_quant>`_.
An archived hardware table is not evidence that its TensorRT release is the
correct software version for a current deployment.

PyTorch training and inference
------------------------------

Use native ``torch.autocast`` for mixed-precision execution. Keep normal FP32
model/optimizer state when following AMP; do not combine that recipe with
blanket ``model.half()`` and batch conversion. Autocast chooses precision per
operation. CUDA FP16 training normally pairs it with
``torch.amp.GradScaler("cuda")``. BF16 generally does not require FP16-style
gradient scaling. Forward and loss computation run inside autocast; backward
and optimizer steps run outside it. Inference needs no gradient scaler.
See the `PyTorch AMP examples <https://docs.pytorch.org/docs/stable/notes/amp_examples.html>`_
and `AMP API <https://docs.pytorch.org/docs/stable/amp.html>`_.

FP16's smaller exponent range can overflow or underflow where BF16/FP32 does
not. Keep sensitive operations in FP32 using the library's documented
autocast behavior or a local disabled-autocast region when needed. Distillation
probabilities, temperature-scaled logits, logarithms and KL losses need
particular attention; do not reduce teacher-target precision indiscriminately.
BF16's wider range does not guarantee identical accuracy.

For a fixed low-precision exported graph or explicitly low-precision eager
model, obey its declared input types and provider/runtime contract. This differs
from AMP over FP32 weights. CPU/GPU device selection alone does not select
precision. PyTorch's BF16 capability query can include emulation; use its
``including_emulation=False`` option when checking native CUDA support.

FP32 tensors can still use TF32/reduced-precision backend arithmetic on
supported GPUs. Record the actual backend precision settings when creating an
accuracy baseline. See `PyTorch numerical accuracy <https://docs.pytorch.org/docs/stable/notes/numerical_accuracy.html>`_.

Dataset and target handling
---------------------------

Keep source data in its appropriate source representation. Existing TorchVision-backed image
loading preserves decoded channels and supported bit depth: 8-bit inputs return
uint8, while 16-bit PNG can return uint16. Custom sources may also provide
floating data. Image scaling/normalization and compute precision are different
operations. Use the selected processor or TorchVision transforms for scaling;
do not divide a pre-normalized image by 255 again.

Preserve each consumer's target contract. Integer IDs, indices, boolean masks,
continuous coordinates and soft teacher distributions need different dtypes.
A mask containing IDs is different from a probability mask. Do not apply a
floating dtype to every tensor in a structured annotation. Device movement
should retain dtype; configured image transforms or the native execution
backend own intentional conversion. Float64 is available for consumers that
need it, rather than a general CV model default.

INT8 quantization is a calibrated model transformation with scales/zero points
and compatible operators, not ``tensor.to(torch.int8)``. Use the target backend's
PTQ/QAT tooling and representative inputs. Weight-only compression is distinct
from integer activation execution. Re-evaluate the converted model on held-out
data, separate from calibration data. See
`LiteRT integer conversion <https://ai.google.dev/edge/litert/conversion/tensorflow/quantization/post_training_integer_quant>`_.

Current package behavior
------------------------

``utils.to_device`` and labeled inference preserve tensor dtypes. Dataset
processors configure image conversion; ``data.transforms.preprocess`` currently
produces FP32. The Ultralytics training paths currently normalize images to
FP32. ``prediction_loss`` retains structured/soft target dtypes while moving
nested tensors to the model device.

The shared trainer has no AMP/autocast/GradScaler configuration yet. Inference
uses ``inference_mode`` for autograd behavior, which does not choose precision;
it neither autocasts nor changes the loaded model's dtype. Passing a lower
weight dtype through provider construction does not make the remaining
execution path precision-compatible automatically. This review documents
those limits without changing training or inference precision defaults.

Precision choices belong in Hydra when an execution integration is implemented.
Log the requested and effective precision, device/runtime versions, model
identity, Dataset identity, processing and metric settings in MLflow. Compare
task accuracy with the FP32 reference, including relevant classes/slices and
small-object/mask/keypoint behavior. CPU contract tests do not establish GPU
or edge numerical equivalence; validate the exported model on its target
runtime before claiming its accuracy.
