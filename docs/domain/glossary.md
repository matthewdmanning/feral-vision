# Feral Vision

Feral Vision trains and evaluates computer-vision models from reproducible datasets and run recipes. Its language separates data identity, run configuration, experiment evidence, and model lifecycle so that each trained result can be traced without conflating the systems that store those concerns.

## Data lineage

**Dataset Artifact**:
A file for which structured metadata about a Dataset's provenance can be stored
in DVC pipeline files such as `dvc.yaml`, including source Datasets and
applicable operations, parameters, image order, and random seeds. It is Data
Lineage.
_Avoid_: Dataset, model artifact

**Dataset**:
A collection of images, with or without annotations. Its adjective specifies its contents and provenance.
_Avoid_: Dataset Artifact, data path

**Dataset Variant**:
A modification of a Dataset through subsetting, combination, and/or
augmentation. A Dataset Variant is itself a Dataset.
_Avoid_: Configuration variant

**Bounding-box Detection**:
A computer-vision task in which each annotated object is represented by a
class-labelled rectangular bounding box. The selected model architecture and
training data annotations must both support this task.
_Avoid_: Instance segmentation, image classification

**Annotation-aware Augmentation**:
The derivation of a Dataset Variant that applies each geometric image transform
to its corresponding annotations, preserving their alignment with the output
image.
_Avoid_: Image-only augmentation, unchanged bounding boxes

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

**Task Adapter**:
A training-layer boundary that translates a task's Dataset annotations and model
outputs into batches, target assignment, and loss values while leaving the
generic training loop responsible for optimization, tracking, and checkpoints.
_Avoid_: Model Source Adapter, augmentation pipeline

**Native Target Assignment**:
The prediction-to-ground-truth matching policy supplied by a downloaded
detector. A Task Adapter preserves this policy when applying a project-selected
loss, unless a Run Recipe explicitly selects a different matching contract.
_Avoid_: Loss function, annotation-aware augmentation

**Fine-tuning Baseline**:
The first training-script execution for a scope that starts from downloaded
pretrained weights, uses a selected Dataset Variant, and establishes the
reference Run Record and Model Artifact for later comparison.
_Avoid_: From-scratch baseline, downloaded model

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

**Model Source Adapter**:
The boundary that obtains an external model definition and exposes it as a
PyTorch ``nn.Module`` to Feral Vision. The source is distinct from the model's
training task and from the resulting Model Artifact.
_Avoid_: Model architecture, Model Artifact

**Model Lifecycle Management**:
The practice of registering, evaluating, promoting, and retiring Model Versions while preserving registry provenance, the metadata needed to load and run them, and experiment-tracked references to the exact DVC Dataset Artifacts used for training.
_Avoid_: Experiment tracking, model tracking
