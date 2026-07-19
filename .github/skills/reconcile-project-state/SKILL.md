---
name: reconcile-project-state
description: Use when returning after a break, choosing the next AI Diary work, cleaning branches, or deciding whether GitHub issues can close by reconciling live issue state with commits, tests, and current implementation.
---

# Reconcile Project State

1. Inspect the working tree, active branch, upstream, divergence from `main`, recent
   commits, and merged/unmerged local branches.
2. Fetch live GitHub issue and milestone state when access is available. Treat issue text
   as intent and repository evidence as delivery reality.
3. Classify relevant issues:
   - `close`: acceptance criteria are present in merged or merge-ready tested code
   - `update`: meaningful scope remains and the issue body should describe only that gap
   - `superseded`: another issue/branch owns the remaining work
   - `ready`: dependencies are complete and it is suitable for the next batch
4. Identify branches that are merged, superseded, divergent, or still contain unique work.
   Never delete or merge without current authorisation.
5. Recommend one exact direction of travel: current branch action, next coherent batch,
   validation gate, and user action if any.
6. Avoid creating a permanent status document. Use GitHub plus git as the durable record;
   create only a temporary consolidated smoke checklist when needed.

Do not estimate project completion from raw open-issue count when issue hygiene is stale.
Explain uncertainty and name the evidence needed to resolve it.
