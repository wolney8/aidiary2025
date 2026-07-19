# Release Governance

Use this checklist at each issue-batch or milestone boundary. GitHub records product
status; git and test evidence establish whether work is actually complete.

## Branch lifecycle

- Start from updated `main` using a focused issue or batch branch.
- Keep one writer per branch/worktree and no more than three related issues per batch.
- Commit complete, reviewable slices. Push after automated validation so signed-off work
  is not held only in a local working tree.
- Merge only when acceptance criteria, applicable automated checks, and required manual
  smoke tests pass. Update `main` before the merge and resolve divergence deliberately.
- Delete merged local and remote feature branches only after confirming their tip is
  reachable from `main`. Never delete a divergent branch until its unique commits are
  classified as merge, cherry-pick, or superseded.
- Review unmerged branches at every milestone end and after returning from a long pause.
- Treat stashes as short-lived recovery state. Name intentional stashes, inspect them at
  batch end, and never delete an unknown stash without its owner's approval.

## Issue closure

An issue may close when:

- its acceptance criteria are present in merged code
- regression coverage exists for changed behaviour where practical
- applicable automated checks pass
- user-visible behaviour has passed the agreed smoke test
- documentation and compatibility paths are updated where the contract changed
- remaining work is either absent or tracked in a clearly scoped follow-up issue

Partially delivered issues stay open with their body rewritten to describe only the
remaining gap. Superseded or duplicate issues should link to the owning issue.

## Milestone closure

Before closing a milestone, record:

- owner: the person approving product completion
- implementation evidence: merged branches or commits
- validation evidence: automated checks and manual smoke result
- issue disposition: every scoped issue closed, deferred, or moved explicitly
- exceptions: known risk, reason accepted, and follow-up issue

The milestone owner gives final sign-off after verifying these items. Deferred work must
move to a named milestone or backlog issue; it must not disappear into a handoff document.

## Exception handling

- A failing required check blocks closure unless the failure is proven unrelated and the
  exception is recorded with a follow-up issue.
- Urgent fixes may use a reduced smoke path, but still require diff review, targeted tests,
  and a retrospective full validation run.
- Database, privacy, authentication, paid-provider, and breaking-contract exceptions
  require an explicit user ruling under `AGENTS.md`.
