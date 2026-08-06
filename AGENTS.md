# OpenMynd Agent Contract

This is the authoritative entry point for Codex work in this repository. Source code,
tests, and current configuration override historical documentation when they disagree.
Legacy material under `.github/agents/` is not an active orchestration system.

## Project goals

Prioritise work that improves a private, dependable AI-supported diary while preserving:

- user data, privacy, and ownership
- Daily and Dream behavioural consistency where appropriate
- WCAG 2.2 and Material Design 3 interaction quality
- portable media and data contracts suitable for later cloud migration
- maintainable Angular and Flask boundaries with regression coverage
- delivery throughput without mixing unrelated or unverified changes

GitHub issues describe product intent. The checked-out code, tests, and branch history
describe implementation reality. Reconcile both before closing an issue.

## Operating model

- Use one primary coding agent per branch and worktree.
- A delivery batch may contain up to three closely related issues when they share a
  feature area, dependency, or validation path. Do not batch unrelated work merely to
  increase issue count.
- Parallelise read-only investigation and independent checks. Never let two agents edit
  the same branch or worktree concurrently.
- Continue end-to-end without asking for routine implementation choices that can be
  resolved from source, tests, established patterns, or the issue acceptance criteria.
- Collect manual smoke tests into one temporary checklist only when needed. Remove or
  prune completed checklists after sign-off.
- Keep progress updates short and milestone-based. Do not pause after every small edit.

## Authority and escalation

Codex may proceed without further approval to:

- inspect the repository and run non-destructive commands
- implement behaviour already defined by an issue or an explicit user direction
- add or update tests, validation, and concise operational documentation
- fix defects discovered inside the active scope when the intended behaviour is clear
- create focused commits when the user has asked for a commit or authorised the batch

Codex must stop and request a ruling before:

- destructive or irreversible data/database operations
- changing privacy defaults, authentication policy, or security boundaries
- introducing a paid service, new external data processor, or materially higher AI cost
- making a breaking API, export/import, storage, or schema decision not required by scope
- changing acceptance criteria or expanding into an unrelated product feature
- overwriting, reverting, or resolving a direct conflict with unexpected user changes
- merging, deleting branches, closing issues, or releasing unless the current instruction
  authorises that operation

When escalation is required, ask one concise question, state the recommended default,
and continue with any independent safe work.

## Delivery cadence

1. **Reconcile**
   Run `git status --short --branch`. Confirm the active issue, branch, dependencies,
   relevant merged work, and unexpected changes.
2. **Analyse**
   Read affected source, adjacent interfaces, configuration, and existing tests. For AI
   work inspect the route and `server/services/openai_svc.py`; for schema work inspect
   runtime migrations and existing-database compatibility. For every user-facing
   frontend change, apply `.github/skills/enforce-platform-ux/SKILL.md` before planning.
3. **Plan**
   State the batch outcome, issue boundaries, likely files, validation, and any item that
   requires a ruling. Prefer one plan per batch, not one plan per file.
4. **Implement**
   Deliver complete vertical slices in reviewable commits. Preserve established Angular
   standalone, Flask blueprint/service, Material 3, and accessibility patterns.
5. **Review**
   Inspect `git diff --stat` and the actual diff. Check scope, secrets, generated files,
   route/API contracts, existing databases, responsive states, and light/dark themes.
   Repeat the `enforce-platform-ux` review gate for every user-facing frontend diff.
   For shared controls, compare enabled, hover, selected, focused, and disabled states
   across every route that uses the primitive. Do not approve page-local fixes that
   leave equivalent toggles, buttons, icon targets, or paginators inconsistent.
6. **Validate**
   Run targeted checks during implementation and the applicable release-boundary checks
   before handoff. Do not claim lint, tests, or smoke coverage that did not run.
7. **Sign off**
   Report outcome, files changed, checks and results, manual smoke tests still required,
   risks, and the exact next action. After authorised merge, update or close issues and
   start the next branch from current `main`.

## Completion rules

A slice is complete only when implementation, tests, self-review, and relevant docs are
coherent. A batch is merge-ready only when:

- the working tree contains only intended changes
- backend/frontend contracts and existing-data paths are considered
- applicable automated checks pass, or failures are reported precisely
- user-visible changes have a concise combined smoke-test path
- no known blocker is hidden behind a follow-up note
- shared interactive controls use the global Material 3 shape/state tokens; compact
  actions and segmented choices are pill-shaped, icon controls are centred 48px touch
  targets, and cards/dialogs/tables retain appropriate rounded-container shapes
- icon-plus-text controls align to a shared centreline across buttons, rows, cards,
  top-bar actions, menus, and dialogs; dialog leading icons are centred inside their
  circular container and aligned with the title/message block
- user-facing interactive boundaries expose descriptive feature-scoped classes and
  stable `data-testid` hooks where they are needed for tests or precise feedback; never
  depend on generated Angular Material class names as the product-facing selector

Do not call partial implementation complete. Do not keep a branch open for unrelated
polish after its acceptance criteria are met.

## Repository commands

Development servers (run in separate terminals from the repository root):

```bash
cd server && source venv/bin/activate && python -m flask --app app.py --debug run -p 5001
```

```bash
cd client && npm start
```

Primary validation:

```bash
cd server && source venv/bin/activate && PYTHONPATH=. pytest
cd client && npm run build
```

Playwright requires a one-time `cd client && npx playwright install chromium` after setup
or a Playwright version change. `npm run lint` and `npm run test:e2e:smoke` are confirmed
release-boundary commands.

## Supporting guidance and skills

- `docs/playbooks/working-cadence.md`
- `docs/playbooks/feature-development.md`
- `docs/playbooks/bug-fix.md`
- `docs/playbooks/git-safety.md`
- `docs/playbooks/testing-and-validation.md`
- `docs/playbooks/release-governance.md`
- `docs/coding-standards.md`
- `docs/known-issues.md`
- `.github/skills/deliver-issue-batch/SKILL.md`
- `.github/skills/validate-release-boundary/SKILL.md`
- `.github/skills/reconcile-project-state/SKILL.md`
- `.github/skills/enforce-platform-ux/SKILL.md`
- `.github/skills/ui-inspect/SKILL.md`
- `.github/skills/lint-and-analyse/SKILL.md`
