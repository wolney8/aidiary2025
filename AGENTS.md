# Codex Working Guide

Use this file as the session entry point. Supporting project guidance lives in:

- `docs/architecture.md`
- `docs/coding-standards.md`
- `docs/known-issues.md`
- `docs/roadmap.md`
- `docs/playbooks/working-cadence.md`
- `docs/playbooks/git-safety.md`
- `docs/playbooks/testing-and-validation.md`
- `docs/playbooks/feature-development.md`
- `docs/playbooks/bug-fix.md`
- `docs/adr/0001-initial-architecture.md`
- `docs/research/codex-workflow-findings.md`

## Default cadence

1. Analyse
   Read the relevant files, config, and existing tests before proposing or editing anything.
2. Plan
   State the intended change, affected files, checks to run, and any uncertainty marked `To confirm`.
3. Implement
   Make small, reviewable changes that follow existing patterns.
4. Review
   Inspect your own diff for scope creep, stale assumptions, and unexpected edits.
5. Test
   Run applicable commands from `docs/playbooks/testing-and-validation.md`.
6. Summarise
   Report files changed, checks run, results, and remaining risks.

## Required guardrails

- Inspect the relevant source, config, and test files before editing.
- Run `git status --short --branch` before changes and again before finishing.
- Run `git diff --stat` and inspect the diff before finishing.
- Do not silently overwrite or discard unexpected existing changes. Stop and report them.
- Keep changes small enough to review easily.
- Prefer repository-confirmed commands only. If a command is uncertain or currently broken, say so.
- After any change, give a final summary with:
  - files changed
  - checks run
  - notable risks or follow-up items
