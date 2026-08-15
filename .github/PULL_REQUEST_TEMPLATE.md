## Summary

<!-- Keep each answer brief. -->

- What changed?
- Why was it needed?

## Change type

- [ ] Bug fix
- [ ] Feature
- [ ] Refactor
- [ ] Configuration
- [ ] Terraform / cloud infrastructure
- [ ] Documentation
- [ ] Tests
- [ ] CI / tooling

## Related issues or context

<!-- Link issues, discussions, incidents, or design notes. -->

## Change map

| Area | Changed? | Reviewer notes |
| --- | --- | --- |
| Application code | [ ] | |
| Configuration / Hydra | [ ] | |
| Data / DVC | [ ] | |
| Training / deployment | [ ] | |
| Terraform / cloud | [ ] | |
| Tests | [ ] | |
| Documentation | [ ] | |

## Key changes

-
-

## Interfaces and contracts

<!-- Include only when APIs, schemas, config contracts, resource addresses, or file boundaries changed. -->

- Changed interfaces or contracts:
- Migration or compatibility notes:

## Risk and operations

| Question | Answer |
| --- | --- |
| Breaking change? | None / Yes: |
| Creates, modifies, or destroys cloud resources? | None / Details: |
| Data, Dataset Artifact, or model-lineage impact? | None / Details: |
| Rollback or migration required? | No / Details: |
| Secrets or credentials involved? | No / Details: |

<!-- For cloud changes, state the relevant identity, region, quota, state, and lifecycle assumptions. -->

## Validation

| Check | Command or evidence | Result |
| --- | --- | --- |
| Unit / integration tests | | |
| Terraform formatting | | |
| Terraform validation or plan | | |
| Terraform tests (`terraform/tests/` only) | | |
| Python tests (`tests/`) | | |
| CI or manual verification | | |

## Optional workflow details

<details>
<summary>Terraform / cloud</summary>

- Terraform roots or modules changed:
- Provider and version changes:
- Plan / apply status:
- Resource lifecycle or state impact:
- Identity, region, quota, or provider-plugin assumptions:

</details>

<details>
<summary>Training / data</summary>

- Hydra or Run Recipe changes:
- Dataset or DVC lineage changes:
- Image, VM, GPU, storage, or startup changes:
- MLflow impact:

</details>

<details>
<summary>Additional evidence</summary>

<!-- Add only useful evidence: logs, screenshots, metrics, or follow-up links. -->

</details>

## Reviewer checklist

- [ ] Scope and motivation are clear.
- [ ] Key changes and affected areas are identified.
- [ ] Validation commands and results are recorded.
- [ ] Breaking changes and operational risks are documented.
- [ ] Tests are placed in the correct project boundary.
- [ ] Documentation is updated where needed.
- [ ] No secrets are committed.
- [ ] CI status is recorded.
