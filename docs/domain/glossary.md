# Feral Vision

Feral Vision trains and evaluates computer-vision models from reproducible datasets and run recipes. Its language separates data identity, run configuration, experiment evidence, and model lifecycle so that each trained result can be traced without conflating the systems that store those concerns.

## Data lineage

**Dataset Artifact**:
A file that stores structured metadata for a Dataset's provenance, including its
source Datasets and applicable operations, parameters, image order, and random
seeds. It is Data Lineage.
_Avoid_: Dataset, model artifact

**Dataset**:
A collection of images, with or without annotations. Its adjective specifies its contents and provenance.
_Avoid_: Dataset Artifact, data path

**Dataset Variant**:
A collection derived from a Dataset by subsetting its images, augmenting them, or both.
_Avoid_: Configuration variant

**Data Lineage**:
The structured provenance connection recorded by a Dataset Artifact between a Dataset, its source Datasets, and any applicable operations.
_Avoid_: Data path, run recipe

## Run configuration

**Configuration Variant**:
A single named configuration file containing the key-value choices for one configuration concern.
_Avoid_: Run recipe, configuration group

**Run Recipe**:
The complete, non-redundant collection of Configuration Variants required to run model training or inference, with no required concern missing.
_Avoid_: Configuration variant, source defaults

## Cloud deployment

**Cloud Resource**:
A provisioned cloud asset and its lifecycle configuration, including storage,
container registry, compute, network, identity, and access policy. Terraform
owns the configuration and lifecycle of every Cloud Resource used by the cloud
smoke. Terraform is invoked separately; Hydra does not mirror, override, or
invoke this configuration.
_Avoid_: Training run, Dataset Artifact, Run Recipe

**Terraform State**:
The record Terraform uses to manage Cloud Resources. The first cloud smoke uses
local state; a remote state backend is not part of that deployment.
_Avoid_: Run record, data lineage link

## Experiment tracking

**Experiment**:
A named grouping of related training-script executions used to compare attempts toward a shared objective.
_Avoid_: Training-script execution, model

**Run Record**:
The durable evidence about a training-script execution, including its resolved parameters, metrics, metadata, artifacts, and lineage.
_Avoid_: Run recipe, log file

**Model Artifact**:
A product of a training-script execution.
_Avoid_: Dataset artifact, checkpoint

**Checkpoint**:
Model weights emitted by the training framework at a specific epoch during a training-script execution, usually as a `.pt` file. It does not explicitly contain the model architecture or configuration.
_Avoid_: Model artifact, model configuration

**Experiment Tracking**:
The practice of recording and comparing run records.
_Avoid_: Model lifecycle management, model tracking

## Model identity and lifecycle

**MLflow Model Registry**:
The database containing Registered Models.
_Avoid_: Experiment tracker, run record

**Registered Model**:
A named identity in the MLflow Model Registry that groups its related Model Versions and their lineage.
_Avoid_: Model artifact, training-script execution

**Model Version**:
A distinct pairing of an architecture revision and a learned weight set under a Registered Model. A change to the architecture's shape or to its weights creates a different Model Version.
_Avoid_: Checkpoint, training-script execution, registered model

**Model Family**:
A group of models containing the same types of operations with varying construction hyperparameters.
_Avoid_: Model Zoo, Registered Model

**Model Zoo**:
An online collection of many different models, some with pre-trained weights.
_Avoid_: Model Family, MLflow Model Registry

**Model Lifecycle Management**:
The practice of registering, evaluating, promoting, and retiring Model Versions while preserving registry provenance, the metadata needed to load and run them, and experiment-tracked references to the exact DVC Dataset Artifacts used for training.
_Avoid_: Experiment tracking, model tracking
