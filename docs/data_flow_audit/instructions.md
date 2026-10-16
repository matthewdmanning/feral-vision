# Data flow audit: user instructions

Recorded from the session on 2026-10-15. This file organizes the user's
instructions; it does not introduce requirements or select an implementation.
Command investigation evidence is in [dvc_commands.md](dvc_commands.md).

## Authority and session objective

The session goal is to define and validate a DVC workflow that matches this
project. Previous attempts relied too much on DVC example workflows instead of
project requirements. First align on DVC's utility, then assess the agreement,
conflicts, and ambiguities of DVC-related project documentation against the
user's requirements.

The following five requirements are authoritative. The user may add to them;
agents must not modify them or add their own requirements or assumptions. Ask
the user when uncertain. Existing project documentation is not necessarily
correct and does not override these instructions.

The user's analysis rule, verbatim:

> All analysis must use the instructions, especially the data flow of the project, as context for understanding and relevance.

## Original requirements, verbatim

1. Datasets are used for training machine learning models.
2. Datasets must be uniquely identified, one-to-one.
3. The root sources of data in the dataset must be able to be located based on the identifier. Root sources are either published or from an internally created data store.
4. The lineage of the data must be able to be located. A single link to a tracked dataset and any changes applied to each data is sufficient.
5. DVC operations are not responsible for encompassing all deteails of these relationships. They only need identifiers of the sources, such as unique file names.

## Catalogue and identity clarification, verbatim

> the hash of the file might identify the file contents but the lineage must still be identified. dvc does not hold the file itself. it is merely a catalogue of the files.

## Data lifecycle, verbatim

The user corrected an earlier response that described operations rather than
the lifecycle:

```text
1) acquisition from source(registration)
1a) augmentation (registration -- with link to parent), optional
2) Staging data (required dvc files must move with it)
3) Training the model using data (mlflow consumes the dvc files to record which data were used for training)

Training requires individual record references.
```

The user subsequently clarified that both "individual training record" (a term
introduced by the agent) and "individual record references" are descriptive.
Neither phrase specifies the DVC file format or record granularity that training
consumes. The user instructed the agent to search MLflow documentation for DVC
and report the findings about those inputs.

The user further clarified, verbatim:

> the artifact being logged is a dvc output.

The user further required checking the association, verbatim:

> wait. the dvc output must be associated with the training data. verify that this is the case.
> use web search for examples of mlflow and dvc output being used together.
> be careful to avoid examples of dvc being used to trive the training process.

## Acquisition through model inference, verbatim

> Data (images and annotations) can be acquired from model inference. These must be registered with the model identity recorded in the source metadata. The models have their own catalguing system, which must be used to maintain data integrity.

## Storage and training placement, verbatim

> Data are to be stored on google cloud storage buckets. training occurs on google compute engine in the same region.
> Best practices: Download to storage bucket, then move to GCE instance to reduce load times.

The user's clarification, verbatim:

> GCE is ephemeral. Files are always copied to GCE.

The agent reference is [data_flow_reference.md](data_flow_reference.md).
Its first version is a draft. The user permits questions after its creation.

## Investigation instructions

Start with `dvc add` and `dvc push`: investigate their inputs, outputs, and
options. Do not assume existing project documentation correctly describes
them.

The user's warning:

> WARNING: the examples and cookbook used in dvc websites are unreliable. they often contain uses that would cause infinite execution loops in our project

Use actual command behavior as evidence. No DVC example or cookbook workflow
has been adopted as a project requirement.

## Trial rules and supplied data, verbatim

> test runs on this project:
> 1) always use a tempory folder in the project folder. the folder name must contain a unique identifier that you store in your memory. the folder must contain a document concisely detailing the purpose, creation, and other operations. mark it gitignored. when you are finished with the tempory folder, delete it.
> 2) copy @data/augmented/ and use as the data folder for any trials.
> 3) the folder contains both images and image annotation masks. they are paired by filename. annotations filenames also contain the albumentations augmentation applied.

## Document location

Keep all documents for this work, other than trial DVC runs, in
`docs/data_flow_audit/`. Keep the organized user instructions in this file and
the DVC command investigation in [dvc_commands.md](dvc_commands.md).

## Decisions not established by these instructions

The session has not selected an identifier format, a DVC record layout, a
source/parent/model reference schema, or an implementation for staging records
and consuming them in MLflow. These are unresolved implementation questions,
not additional requirements.
