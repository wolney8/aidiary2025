# Codex Workflow Findings

## Objective

Provide a repeatable single-agent Codex workflow for this repository without relying on the earlier Copilot multi-agent scaffold.

## Findings from repository analysis

- The repository already contains orchestration material under `.github/`, but it describes a different stack and should not be treated as the operational source of truth.
- A disciplined single-agent workflow is a better fit here because the main risks are repository drift, command drift, and runtime/database sensitivity.
- The safest repeatable cadence for this codebase is:
  analyse, plan, implement, review, test, summarise
- Codex should always verify commands from repo files rather than from historical docs alone.
- Codex should always inspect `git status` before and after work because this repository commonly contains local runtime artefacts.

## Recommended prompt pattern for future sessions

Use prompts that:

- name the task clearly
- require the cadence `analyse, plan, implement, review, test, summarise`
- prohibit overwriting unexpected changes
- require `git status` and diff review
- require repository-confirmed commands only

Example:

```text
Use AGENTS.md and the docs/playbooks guidance.
Follow the cadence: analyse, plan, implement, review, test, summarise.
Inspect relevant files before editing.
Run git status before and after changes.
Do not overwrite unexpected local changes.
Keep the change small and reviewable.
Run repository-confirmed checks and report files changed, checks run, and risks.
```

## Practical guidance

- Start with source and config files, not older docs.
- Mark uncertainty as `To confirm`.
- Treat generated files and local databases as non-source artefacts.
- Expect backend and frontend checks to differ in reliability.

## To confirm

- Whether the team wants old `.github/` Copilot material retired, updated, or left as historical reference.
