# Feral Vision

Feral Vision trains and evaluates computer-vision models from reproducible
Datasets and Run Recipes. Its language separates data identity, run
configuration, experiment evidence, model lifecycle, and cloud delivery so that
each trained result can be traced without conflating the systems that store
those concerns.

Terms may be described with other language. When an agent assumes two terms are
interchangeable, it must state that assumption. A high-confidence mapping does
not block a non-critical change; a low-confidence terminology change requires
user confirmation.

## Data lineage

### Dataset Artifact

#### General

A DVC `dvc.lock` record that identifies a Dataset folder and its structured
provenance, including source Datasets and applicable operations, parameters,
image order, and random seeds. It is Data Lineage.

#### Feral Vision backend

The record is published as `dvc.lock`; DVC manages the Dataset folder in its
remote.

_Avoid_: Dataset, Model Artifact

### Dataset

A collection of images, with or without annotations. Its adjective specifies
its contents and provenance.

_Avoid_: Dataset Artifact, data path

### Data Source Adapter

The boundary that turns a request for a data source into a Dataset, applying
any required transformation or format conversion.

_Avoid_: Model Source Adapter, Dataset Variant

### Dataset Variant

A modification of a Dataset through subsetting, combination, and/or
augmentation. A Dataset Variant is itself a Dataset.

_Avoid_: Configuration Variant

### Publish

#### General

Make a Dataset or Dataset Variant available through the DVC Registry.

#### Feral Vision backend

Publication records the immutable Dataset folder with DVC, pushes its managed
data, and writes `dvc.lock` to a reviewed Dataset Artifact prefix.

_Avoid_: Assuming that acquisition and publishing are interchangeable

### DVC Registry

#### General

A structured DVC repository that exposes versioned Datasets through DVC
metadata. It is distinct from a DVC remote, which stores DVC-managed data.

#### Feral Vision backend

The dataset-only bucket is the Dataset Artifact catalog and DVC remote.
`dvc.lock` identifies the selected Dataset folder version.

_Avoid_: DVC remote, general operational storage

### Bounding-box Detection

A computer-vision task in which each annotated object is represented by a
class-labelled rectangular bounding box. The selected model architecture and
training data annotations must both support this task.

_Avoid_: Instance segmentation, image classification

### Annotation-aware Augmentation

The derivation of a Dataset Variant that applies each geometric image transform
to its corresponding annotations, preserving their alignment with the output
image.

_Avoid_: Image-only augmentation, unchanged bounding boxes

### Data Lineage

The structured provenance connection recorded by a Dataset Artifact between a
Dataset, its source Datasets, and any applicable operations.

_Avoid_: Data path, Run Recipe

## Run configuration

### Configuration Variant

A single named configuration file containing the key-value choices for one
configuration concern.

_Avoid_: Run Recipe, configuration group

### Run Recipe

#### General

One YAML configuration file that names the model and Dataset selected for
training, including the complete, non-redundant Configuration Variants required
to run. A workflow script consumes the file; the file does not perform the
workflow.

#### Feral Vision backend

Complete named recipes live under `conf/runs/`. Input acquisition is a Cloud
Job concern, not a Run Recipe responsibility.

_Avoid_: Configuration Variant, executing workflow, source defaults

### Training Script

#### General

A script that trains the selected model on the selected Dataset.

#### Feral Vision backend

An image entrypoint calls the training script after supplying the Run Recipe
configuration and staged Dataset.

_Avoid_: Hydra trainer, Run Recipe, Cloud Job

### Task Adapter

A training-layer boundary that translates a task's Dataset annotations and model
outputs into batches, target assignment, and loss values while leaving the
generic training loop responsible for optimization, tracking, and checkpoints.

_Avoid_: Model Source Adapter, augmentation pipeline

### Native Target Assignment

The prediction-to-ground-truth matching policy supplied by a downloaded
detector. A Task Adapter preserves this policy when applying a project-selected
loss, unless a Run Recipe explicitly selects a different matching contract.

_Avoid_: Loss function, Annotation-aware Augmentation

### Fine-tuning Baseline

The first Training Script execution for a scope that starts from downloaded
pretrained weights, uses a selected Dataset Variant, and establishes the
reference Run Record and Model Artifact for later comparison.

_Avoid_: From-scratch baseline, downloaded model

## Cloud deployment

### Cloud Job

#### General

A task-neutral cloud execution containing one or more Cloud Operations.

#### Feral Vision backend

A Bash or Python workflow script directs a Cloud Job. A training Cloud Job may
consume a Run Recipe; data augmentation, model training, and data downloading
are separate Cloud Operations within a Cloud Job.

_Avoid_: Cloud Run, Cloud Workflow

### Cloud Operation

An operation performed during a Cloud Job. Examples include data augmentation,
model training, and data downloading.

_Avoid_: Cloud Job, Cloud Resource

### Cloud Workflow

#### General

A forked, directed acyclic workflow that uses orchestration to coordinate Cloud
Jobs and service providers.

#### Feral Vision backend

A Bash or Python workflow script initiates the workflow. Training selection is
provided by a Run Recipe, while other Cloud Jobs may use their own operational
configuration.

_Avoid_: Linear sequence, Cloud Job, Run Recipe

### Orchestration

The coordination of Cloud Operations and Cloud Resources within a Cloud
Workflow.

_Avoid_: Cloud Service Provider, Cloud Workflow

### Cloud Service Provider

#### General

An external provider from which Cloud Resources are obtained.

#### Feral Vision backend

The current Cloud Service Provider is Google Cloud.

_Avoid_: Terraform, Cloud Resource

### Cloud Resource

#### General

A provisioned cloud asset and its lifecycle configuration, including storage,
container registry, compute, network, identity, and access policy.

#### Feral Vision backend

Terraform owns the configuration and lifecycle of every Cloud Resource. Hydra
does not mirror, override, or invoke this configuration.

_Avoid_: Cloud Job, Dataset Artifact, Run Recipe

### Terraform State

#### General

The record Terraform uses to manage Cloud Resources.

#### Feral Vision backend

State is kept in protected operations storage. The detection run module uses a
GCS backend under `feral-vision-operations-us-east4/terraform/runs/detection`.

_Avoid_: Run Record, Data Lineage link

### Training Image Digest

#### General

An immutable content-addressed identifier for a training container image.

#### Feral Vision backend

Cloud Build publishes the base and training images to Artifact Registry. A
successful training-image digest is required before an image-dependent Cloud
Job can start.

_Avoid_: Mutable image tag, Dataset Artifact

## Experiment tracking

### Experiment

A named grouping of related Training Script executions used to compare attempts
toward a shared objective.

_Avoid_: Training Script execution, model

### Run Record

The durable evidence about a Training Script execution, including its resolved
parameters, metrics, metadata, artifacts, and lineage.

_Avoid_: Run Recipe, log file

### Model Artifact

#### General

An internal implementation term for a product of a Training Script execution.
In human-facing communication, name the concrete output first.

#### Feral Vision backend

MLflow records the selected best PyTorch model together with Run Record
evidence. Intermediate checkpoints remain local unless another operation
explicitly publishes them.

_Avoid_: Dataset Artifact, Checkpoint, human-facing status language

### Checkpoint

Model weights emitted by the training framework at a specific epoch during a
Training Script execution, usually as a `.pt` file. It does not explicitly
contain the model architecture or configuration.

_Avoid_: Model Artifact, model configuration

### Experiment Tracking

The practice of recording and comparing Run Records.

_Avoid_: Model Lifecycle Management, model tracking

## Model identity and lifecycle

### MLflow Model Registry

The database containing Registered Models.

_Avoid_: Experiment tracker, Run Record

### Registered Model

A named identity in the MLflow Model Registry that groups its related Model
Versions and their lineage.

_Avoid_: Model Artifact, Training Script execution

### Model Version

A distinct pairing of an architecture revision and a learned weight set under a
Registered Model. A change to the architecture's shape or to its weights creates
a different Model Version.

_Avoid_: Checkpoint, Training Script execution, Registered Model

### Model Family

A group of models containing the same types of operations with varying
construction hyperparameters.

_Avoid_: Model Zoo, Registered Model

### Model Zoo

An online collection of many different models, some with pre-trained weights.

_Avoid_: Model Family, MLflow Model Registry

### Model Source Adapter

The boundary that obtains an external model definition and exposes it as a
PyTorch ``nn.Module`` to Feral Vision. The source is distinct from the model's
training task and from the resulting Model Artifact.

_Avoid_: Model architecture, Model Artifact

### Model Lifecycle Management

The practice of registering, evaluating, promoting, and retiring Model Versions
while preserving registry provenance, the metadata needed to load and run them,
and experiment-tracked references to the exact DVC Dataset Artifacts used for
training.

_Avoid_: Experiment tracking, model tracking
