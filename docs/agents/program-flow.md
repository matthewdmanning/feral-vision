# Program Flow

## Cloud Flows

```mermaid
flowchart TB
    run_recipe["Run Recipe"]
    workflow_script["Bash or Python workflow script"]
    cloud_workflow["forked directed acyclic Cloud Workflow"]

    run_recipe -->|"consumed by"| workflow_script
    workflow_script -->|"initiates"| cloud_workflow

    subgraph terraform_orchestration["Terraform orchestration"]
        terraform["Terraform"]
        cloud_resources["Cloud Resources"]
        vm_lifecycle["VM lifecycle and removal"]
        terraform -->|"owns"| cloud_resources
        terraform -->|"owns"| vm_lifecycle
    end

    cloud_workflow --> terraform
    cloud_workflow -. "conditional branch" .-> data_source_adapter
    cloud_workflow -. "conditional branch" .-> model_source_adapter
    cloud_workflow -. "conditional branch" .-> image_operations

    subgraph data_flow["Data flow"]
        data_source_adapter["Data Source Adapter"]
        data_request["request"]
        data_transform["optional transform or format"]
        dataset["Dataset"]
        dataset_modification["modification"]
        dataset_variant["Dataset Variant is a Dataset"]
        publish["Publish"]
        dvc_registry["DVC Registry"]

        data_source_adapter --> data_request --> data_transform --> dataset
        dataset --> dataset_modification --> dataset_variant
        dataset --> publish
        dataset_variant --> publish --> dvc_registry
    end

    subgraph model_flow["Model flow"]
        model_source_adapter["Model Source Adapter"]
        model["model plus optional weights"]

        model_source_adapter --> model
    end

    subgraph image_builds["Image builds"]
        deployment_config["deployment configuration"]
        image_operations["image operations script"]
        cloud_build["Cloud Build"]
        base_image["base image"]
        training_image["training image"]
        artifact_registry["Artifact Registry"]
        image_digest["immutable training-image digest"]

        deployment_config --> image_operations --> cloud_build
        cloud_build --> base_image --> training_image --> artifact_registry --> image_digest
    end

    subgraph gpu_model_training["GPU model training"]
        training_dataset["selected Dataset or Dataset Variant"]
        training_script["training script"]
        run_record["MLflow Run Record"]
        model_artifact["Model Artifact"]

        training_dataset --> training_script
        model --> training_script
        run_recipe -->|"configures"| training_script
        training_script --> run_record
        training_script --> model_artifact
    end

    dataset --> training_dataset
    dataset_variant --> training_dataset
    image_digest -->|"prerequisite"| training_script
    cloud_resources -->|"required by"| training_script
    terraform -. "can orchestrate" .-> cloud_build
    terraform -. "can orchestrate" .-> training_script
    terraform -. "can orchestrate" .-> other_cloud_operation["other cloud operation"]

    dvc["DVC"] -. "owns Dataset Artifacts and lineage" .-> dvc_registry
    hydra["Hydra"] -. "owns" .-> run_recipe
    mlflow["MLflow"] -. "owns training evidence" .-> run_record
    mlflow -. "owns training evidence" .-> model_artifact
```

Terraform can orchestrate any operation performed in the cloud, whether or not
it includes GPU model training. GPU model training requires
Terraform-provisioned Cloud Resources, but it does not define Terraform's
orchestration behavior. The training script trains the selected model on the
selected Dataset; MLflow does not receive raw Dataset directories.

[Cloud Operations](cloudops.md) · [Terraform](terraform.md) ·
[Configuration](configuration.md) · [Training guide](../guide/training.rst)
