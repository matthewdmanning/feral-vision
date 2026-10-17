# Production starter

Copy this tree to a `feral-vision/` production directory beside the library
project metadata. It supplies the same scripts/conf/terraform/deploy/data/models
layout as the example implementation. Configure model, Dataset, tracking, and
cloud values before use. `YOUR_PROJECT_ID` and `YOUR_OPERATIONS_BUCKET` are
required placeholders, not deployable defaults. Never copy Terraform state,
credentials, plans, datasets, or trained weights into these starter assets.

Run production commands from that directory. Image-build commands retain the
repository root as Docker context so the package and lockfile are available.
The scripts import `sightkit_learn`; nothing imports the `templates` package.
