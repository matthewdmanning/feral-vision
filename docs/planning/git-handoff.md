# Repository recovery handoff — 2026-07-30

## Objective

Repair the shared checkout without losing the current local source tree and
without reintroducing stale architectural decisions. Commit history is not the
priority; the desired outcome is a coherent, validated working tree based on
the current `main`.

## Safety boundary

- A point-in-time backup of the complete repository, including `.git` and
  untracked files, exists at
  `/tmp/feral-vision-recovery-backup-s5jjCQ`.
- Do not inspect, modify, remove, or use that backup as a working directory.
- Do not reset, restore, clean, garbage-collect, force-push, delete branches,
  or merge pull requests while performing recovery.

## What happened

- Work was performed directly in the shared checkout, with branch switching
  and resets, rather than in isolated worktrees.
- Remote branches were deleted using commit reachability as the criterion. That
  was unsafe: the deleted branches and their WIP snapshots supplied context for
  uncommitted work even where committed history had reached `main`.
- Git retains numerous unreachable commit objects and WIP snapshots. The
  current shared working tree appears to be accumulated work carried across
  those branch changes.

## Current evidence

- The shared checkout is on `chore/project-structure` and has a large,
  unattributed working-tree changelist.
- A whole-tree comparison against current `origin/main` would change 57
  tracked files, with 431 additions and 2,658 deletions. In particular, it
  would remove newer augmentation-preview, cloud workflow, documentation, and
  PR #57 test work now in `main`.
- Therefore, the local files are useful evidence but must not replace `main`
  wholesale.

## Recovery plan

1. Preserve recovery evidence.

   Create local recovery refs for the identified unreachable commits and WIP
   snapshots. Do not attempt to recreate or publish every historic branch.

2. Start from current `origin/main` in an isolated recovery worktree.

   Never use the shared checkout for branch switching or reconciliation.

3. Reconcile changes selectively.

   - Keep `main` files by default.
   - Carry over intentional local edits to shared components.
   - Treat every local deletion of a file present in `main` as suspect; retain
     the `main` file unless its removal is demonstrably required.
   - Add genuine local-only source and configuration files individually.
   - Exclude generated coverage outputs, editor state, and Codex workspace
     metadata from the recovered change set.

4. Validate the reconstructed tree.

   Run the relevant style, type, and focused test checks. Inspect the complete
   diff against `main` for accidental removals or stale architecture.

5. Make one local recovery checkpoint.

   Create one recovery commit on a new branch based on current `main`, then
   switch the shared checkout to it so the changelist is clean. Do not push,
   open a pull request, or merge without explicit user direction.

## Existing temporary worktrees

- `/root/feral-vision-recovery-worktree` is an isolated checkout based on
  current `main`; it currently contains an uncommitted whole-tree copy used
  only for comparison. Do not commit that copy wholesale.
- `/tmp/feral-vision-main-merge-GcBRVV` contains unrelated handoff edits and
  must not be removed without reviewing those changes.
