# Feral Vision

Feral Vision trains and evaluates computer-vision models from reproducible datasets and run recipes. Its language separates data identity, run configuration, experiment evidence, and model lifecycle so that each trained result can be traced without conflating the systems that store those concerns.

## Product scope

**Feral-Cat Instance Segmentation**:
The product capability that identifies each feral cat in a mobile-captured
image and produces a separate pixel-level mask for that cat.
_Avoid_: Generic animal detection, semantic segmentation

**Instance Mask**:
A pixel-level mask belonging to one detected feral-cat instance.
_Avoid_: Bounding box, semantic mask

## Data lineage

**Data Artifact**:
A versioned collection of data at a specific lifecycle stage, such as raw, processed, or augmented data.
_Avoid_: Model artifact, run artifact

**Dataset**:
A collection of raw, unaltered images obtained from an open source or uploaded by a user.
_Avoid_: Dataset variant, augmented dataset

**Dataset Variant**:
A collection derived from a Dataset by subsetting its images, augmenting them, or both.
_Avoid_: Dataset, configuration variant

**Dataset Derivation Recipe**:
The complete reproducible description of how a Dataset Variant was derived, including subset selection, augmentation operations and parameters, and any randomness or seed.
_Avoid_: Data lineage link, run recipe

**Data Version**:
The immutable identity of the exact data artifact consumed by a run.
_Avoid_: Dataset variant, data path

**Data Lineage Link**:
The recorded connection from a Dataset Variant to its parent Dataset and the Dataset Derivation Recipe applied to that parent.
_Avoid_: Dataset derivation recipe, data path

**Data Operation**:
A standalone action that acquires, derives, versions, or retrieves a Data Artifact outside any training or inference loop.
_Avoid_: Training step, inference step

## Run configuration

**Configuration Variant**:
A single named configuration file containing the key-value choices for one configuration concern.
_Avoid_: Run recipe, configuration group

**Run Recipe**:
The complete, non-redundant collection of Configuration Variants required to run model training or inference, with no required concern missing.
_Avoid_: Configuration variant, source defaults

## Experiment tracking

**Experiment**:
A named grouping of related runs used to compare attempts toward a shared objective.
_Avoid_: Run, model

**Run**:
One execution of training or inference using a resolved run recipe and a specific data version.
_Avoid_: Experiment, model version

**Run Record**:
The durable evidence about a run, including its resolved parameters, metrics, metadata, artifacts, and lineage.
_Avoid_: Run recipe, log file

**Model Artifact**:
A model architecture, its resolved configuration, and its learned weights treated as one tracked unit. Training produces it; experiment tracking records and stores it together with references to the Data Artifacts that establish its training-data lineage.
_Avoid_: Data artifact, checkpoint

**Checkpoint**:
Model weights emitted by the training framework at a specific epoch during a training run, usually as a `.pt` file. It does not explicitly contain the model architecture or configuration.
_Avoid_: Model artifact, model definition

**Experiment Tracking**:
The practice of recording and comparing run records.
_Avoid_: Model lifecycle management, model tracking

## Model identity and lifecycle

**Model Definition**:
A reusable description of a model's architecture, acquisition source, expected outputs, and optional starting weights, independent of any run.
_Avoid_: Checkpoint, model version

**Model Registry**:
The project's durable collection of Registered Model provenance links and the metadata necessary to load and run each model. It points to complete Model Versions without duplicating their artifacts or training-data lineage.
_Avoid_: Experiment tracker, run record

**Registered Model**:
A named model identity in the Model Registry that groups its related Model Versions and their lineage.
_Avoid_: Model artifact, training run

**Model Version**:
A distinct pairing of an architecture revision and a learned weight set under a Registered Model. A change to the architecture's shape or to its weights creates a different Model Version.
_Avoid_: Checkpoint, run, registered model

**Model Lifecycle Management**:
The practice of registering, evaluating, promoting, and retiring Model Versions while preserving registry provenance, the metadata needed to load and run them, and experiment-tracked references to the exact DVC Data Artifacts used for training.
_Avoid_: Experiment tracking, model tracking
