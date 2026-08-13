# Agent-instructions overlap audit

## Scope and method

Reviewed every tracked Markdown guide under `docs/agents/` as present on
2026-08-01, including `project_instructions.md`.  Findings below require a
duplicate or contradictory factual or behavioral rule, command, ownership
assignment, or requirement.  References to the same broad topic alone were not
reported.

## Findings

### 1. Cloud-operations ownership and credential rules are duplicated

- **References:** `cloudops.md:6-10`; `mlops.md:16-26`.
- **Rule:** Both assign cloud-service lifecycle/configuration to Terraform,
  workload configuration to Hydra, and use of provisioned services to scripts.
  Both also require `.env.local` to be loaded only into the invoking process,
  prohibit exposing its values, and reject `GCP_API_KEY` as a cloud identity in
  favor of ADC or equivalent `gcloud` identity.
- **Classification:** overlap.
- **Severity:** high — a security-sensitive operational policy is maintained in
  two purportedly focused guides.

### 2. Cloud implementation map is duplicated

- **References:** `cloudops.md:12-20`; `mlops.md:28-38`.
- **Rule:** Both identify Terraform as declaring the GCP resources/access rules,
  `deploy/cloudbuild.yaml` as image-build input, `scripts/cloud/image_operations.sh` as
  `build`/`push` dispatcher, the `base -> training` image graph,
  `deploy/compose.yaml` local base reuse, `deploy/cloudbuild.build.yaml` remote
  base/final-image publishing, and `stage_model.sh` Cloud Storage staging.
- **Classification:** overlap.
- **Severity:** medium — parallel maintenance can make the operational map
  inaccurate.

### 3. Git session checks and clean-branch procedure are duplicated

- **References:** `git.md:8-15`; `github.md:5-8`.
- **Rule:** Both require checking `gh`, `origin`, MCP availability, and task
  scripts before dependent work; fetching `origin`; fast-forwarding only a
  clean local `main` from `origin/main` before branching; and avoiding updates
  to a dirty worktree or feature branch without task-specific intent.
- **Classification:** overlap.
- **Severity:** high — this is a core repository-safety rule expressed in two
  guides.

### 4. GitHub access, PR, and commit policy are duplicated

- **References:** `git.md:19-23`, `git.md:32-38`, `git.md:44-46`;
  `github.md:10-16`.
- **Rule:** Both prefer the connected GitHub app with `gh` as fallback,
  authenticate `gh` from `.env.local` without exposing its token and verify its
  status, prohibit direct pushes to `main`, require Conventional Commit messages
  and PR publication, require local integration/resolution of `origin/main` and
  verification before PR updates, and require the repository PR template.
- **Classification:** overlap.
- **Severity:** high — duplicate instructions cover authentication and the
  publishing safety boundary.

### 5. Issue-tracker operating rules are duplicated

- **References:** `issue-tracker.md:3-12`, `issue-tracker.md:20-22`;
  `github.md:18-21`.
- **Rule:** Both state that issues/PRDs live in GitHub Issues, prefer the
  connected GitHub app with `gh issue` fallback, require preservation of issue
  bodies/comments/labels while gathering context, and require resolving an
  ambiguous issue/PR number before acting.
- **Classification:** overlap.
- **Severity:** medium — two sources define the same ticket-operation behavior.

### 6. Wayfinding ticket contract is duplicated

- **References:** `issue-tracker.md:24-32`; `wayfinding.md:5-11`.
- **Rule:** Both define the `wayfinder:map` label, child-type labels, native
  sub-issues with `Part of #<map>` fallback, native dependencies with
  `Blocked by:` fallback, the frontier definition, and claim/resolution by
  assignment, comment, closure, and a linked map decision.
- **Classification:** overlap.
- **Severity:** medium — exact process rules are maintained in an issue guide
  and a dedicated wayfinding guide.

### 7. Implementation requirements are duplicated from the shared router

- **References:** `project_instructions.md:18-33`, `project_instructions.md:37-48`;
  `implementation.md:5-11`.
- **Rule:** Both require NumPy-style docstrings for functions over three lines
  and classes, shell-only CLIs, reuse of an existing dependency unless a project
  boundary is needed, canonical-documentation updates for substantive contracts,
  `docs/guide/` updates for user-visible workflow changes, and GitHub Actions
  rather than local Sphinx output validation.
- **Classification:** overlap.
- **Severity:** high — the router duplicates the content of the focused
  implementation guide instead of routing to it.

### 8. DVC/Hydra/MLflow ownership and raw-data prohibition are duplicated

- **References:** `program-flow.md:76-82`; `tracking.md:6-10`;
  `mlops.md:9-12`.
- **Rule:** `tracking.md` repeats that DVC owns Datasets/Dataset Artifacts,
  MLflow owns metrics/artifacts/checkpoints/metadata/model-version links, Hydra
  owns tunables in `conf/`, and raw data directories must not be logged to
  MLflow. `mlops.md` also repeats the raw-data/Dataset-Artifact prohibition and
  directs readers to the same tool-ownership boundary.
- **Classification:** overlap.
- **Severity:** high — data lineage and tool ownership have three maintenance
  locations.

### 9. Dataset layout contract is duplicated

- **References:** `data.md:6-9`; `program-flow.md:10-14`.
- **Rule:** Both require a dataset root/payload containing `images/` and
  `annotations/`, and make the data-source dispatch resolve to that canonical
  layout.  `data.md` supplies annotation-file details, while `program-flow.md`
  supplies cloud tracker placement.
- **Classification:** overlap.
- **Severity:** medium — the same layout invariant is stated in both test/data
  guidance and the canonical flow.

### 10. The designated cloud-operations authority conflicts with routing text

- **References:** `program-flow.md:3-6`; `mlops.md:6-7`;
  `development.md:29-30`; `project_instructions.md:59`.
- **Rule:** `program-flow.md` says cloud configuration/identity/lifecycle belong
  in `cloudops.md`; `mlops.md` independently calls itself the canonical agent
  reference for exactly that subject; `development.md` and the project router
  link readers to `mlops.md` for it.
- **Classification:** conflict.
- **Severity:** high — mutually incompatible claims of canonical ownership make
  it unclear which security and infrastructure rules govern.

### 11. The router’s Program Flow link is internally inconsistent

- **References:** `project_instructions.md:53`; `program-flow.md:1-6`.
- **Rule:** The router link target is `docs/agents/program-flow.md`, which is
  resolved relative to `docs/agents/project_instructions.md` and therefore
  points to a nonexistent nested path; the actual guide is `program-flow.md`.
- **Classification:** conflict.
- **Severity:** medium — the canonical routing document fails to route to the
  stated program-flow authority.

## Result

Eleven concrete overlaps or conflicts were found.  No finding above is based
solely on two documents mentioning the same object or subject.
