# Agent-context routing audit (temporary)

## Scope

Read-only audit of the durable documentation reachable from
`docs/agents/project_instructions.md`. Per the request, this excludes
`docs/agents/implementation/`, `docs/planning/`, `conf/runs/`, `docs/guide/`,
`docs/api/`, and `docs/_build/`.

## Outcome

The landing page is a good small shared-policy document, but it is not yet a
complete router: three durable agent references and the ADR decision path are
not reachable from it. It also embeds cloud-specific material into every
agent's mandatory context. The most serious current contradiction is the
definition of when a cloud workflow is ready for verification.

## Findings

### P0 — contradictory cloud-verification gate

`docs/agents/cloudops.md:44-48` says that merely referencing the documentation
changes an unvalidated workflow to "Ready for Cloud Verification." In contrast,
the accepted decision in `docs/adr/0002-first-augmented-detection-cloud-run.md:83-85`
requires a reviewed plan with a digest-pinned image, immutable Variant, selected
VM service account, and writable artifact prefix. The latter is an evidence-based
readiness gate and should be authoritative.

**Recommendation:** remove the state-transition rule from `cloudops.md` and
replace it with a link to ADR 0002's preconditions. Documentation review can
identify a next verification action, but cannot establish operational readiness.

### P1 — the landing page cannot route every agent to durable guidance

The landing page lists eight references (`project_instructions.md:55-67`) but
omits the durable guides for cloud work (`cloudops.md`), domain decisions
(`domain.md`), and GitHub triage labels/wayfinding (`triage-labels.md` and
`wayfinding.md`). It also does not route an agent to ADRs, even though
`domain.md:7-10` says relevant ADRs must be read and ADR 0002 is the accepted
cloud-run decision.

**Recommendation:** make the landing-page reference list a task-to-document
table. Include entries for Cloud operations, Domain vocabulary and ADRs, and
Issue triage/Wayfinding. Each entry should say both *when to read it* and the
smallest initial target (for example, `ADR 0002` for `first_run_augmented`).

### P1 — mandatory full-glossary loading conflicts with selective-context policy

`project_instructions.md:13` requires every agent to read the entire glossary,
while lines 15-17 say to read only task-required material. The 134-line glossary
contains many specialized terms unrelated to routine GitHub, documentation, or
test tasks. This increases baseline context and makes the selective-read rule
unreliable.

**Recommendation:** change the landing-page rule to: read the glossary entries
used by the task; read the relevant ADR when changing a named decision or
contract. Add stable heading anchors or a compact terminology index so agents
can load a section rather than the whole glossary.

### P1 — cloud identity guidance is both globally loaded and not navigable

The landing page places detailed GCP identity/role policy at lines 25-40, so
every task pays its context cost. It says to read the "canonical cloud handoff"
at lines 27-29 but provides no link or identifier. The same publisher identity
and role are also in `cloudops.md:69-74`, which is not linked by the landing
page.

**Recommendation:** retain only a one-sentence cloud safety gate on the landing
page and link to `cloudops.md`. Make `cloudops.md` the sole location for the
publisher identity and role, then link its applicable ADR/run contract from
there. This removes duplicate maintenance and makes the claimed handoff
discoverable.

### P2 — routing labels overpromise the content behind them

The landing page calls `tracking.md` "tracking-specific operational guidance"
(`project_instructions.md:64-65`), but its only operative policy is the raw-data
prohibition (`tracking.md:3-7`). The full DVC/Hydra/MLflow ownership boundary is
instead already in the landing page (`project_instructions.md:42-53`) and
`program-flow.md:13-17`.

**Recommendation:** either reduce the landing-page label to "raw-data logging
boundary" or move concise, tracking-specific routing and ownership details into
`tracking.md`, leaving each rule with one canonical home.

### P2 — general flow mixes a reusable overview with one run's operator path

`program-flow.md:19-26` embeds the `first_run_augmented` topology in the general
architecture guide and links directly to its run contract. It is correct, but
agents reading the general flow for another task receive run-specific cloud
detail.

**Recommendation:** keep the shared architecture and ownership map in
`program-flow.md`; replace the baseline paragraph with a short "Run-specific
decisions" link list. Keep all `first_run_augmented` procedural details in ADR
0002 and the run contract.

### P2 — unclear global file-naming rule

`project_instructions.md:6-9` declares a `YYYY-MM-DD-{activity_name}` format
without naming its objects (handoffs, temporary audit notes, ADRs, or all
files), then instructs an agent to ask about an unknown sprint. The durable
documentation itself uses multiple valid formats, including numbered ADRs and
undated agent guides.

**Recommendation:** scope the rule explicitly (for example, dated session
handoffs only) or remove it from the universal landing page. Do not make a
routine task block on a sprint name unless the task actually creates that
artifact type.

## Proposed routing shape

| Task | Minimal first read | Follow only when needed |
| --- | --- | --- |
| Any task using project terms | Relevant glossary section | Relevant ADR |
| Code or authored docs | `implementation.md` | Domain, data, cloud, config guides affected |
| Python tests | `testing.md` | `data.md` only for dataset fixtures |
| Data ingestion/publication | `data.md` | `cloudops.md`, selected ADR/run contract |
| Hydra/model configuration | `configuration.md` | `hydra.md` concern index |
| Tracking/model registry | `tracking.md` | `program-flow.md`, relevant ADR |
| Cloud/IAM/build/VM work | `cloudops.md` | ADR 0002 and selected run contract |
| GitHub/PR/issue work | `github.md` | `wayfinding.md` or `triage-labels.md` only for that workflow |
| Terminology or architectural decision | `domain.md` | Relevant glossary section and ADR |

## Suggested implementation order

1. Fix the cloud-readiness contradiction.
2. Turn the landing-page references into the task-to-document table and add the
   omitted durable guides.
3. Move cloud identity detail to `cloudops.md` and narrow the universal glossary
   rule.
4. Tighten the tracking label and move run-specific detail out of the general
   flow.
