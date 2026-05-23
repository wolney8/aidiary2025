---
description: "Use when committing code, creating feature branches, writing commit messages, opening pull requests, or managing git history in any workflow."
---

# Git Workflow

## Local-First Rule (MANDATORY)

**All source code, configuration files, and tests MUST be written to the local workspace first.** Git commits and remote pushes come last — never first.

The correct sequence is:

```
1. Coder writes files locally using local file-creation tools
2. Coder installs dependencies locally (pip install, pnpm install)
3. Coder runs lint, type-check, and tests locally
4. All quality gates pass (see review-quality-gates.instructions.md)
5. Orchestrator halts and hands work to the user for review
6. User approves → THEN commit and push to the remote branch
7. Orchestrator opens PR
8. User merges
```

**GitHub MCP tools (`push_files`, `create_or_update_file`) are FORBIDDEN for writing source code.** They exist solely for project management operations — issues, PRs, labels, and milestones. Using them to write source code bypasses local testing and user review and violates this rule.

---

## Branching

- Create one branch per phase or logical feature: `feature/<task-id>-<short-description>` or `fix/<task-id>-<short-description>`.
- Branch from `main` (or the project's declared primary branch). Never commit directly to `main`.
- Keep branch names lowercase and hyphen-separated.
- Create the remote branch via GitHub MCP **only after** local files are ready and tested — the branch is created immediately before the commit/push step.

## When to Commit

- Commit **once per phase**, after all quality gates pass, all tests pass locally, and the user has reviewed and approved the changes.
- Never commit mid-phase or during remediation iterations.
- One logical change per commit — do not bundle unrelated fixes in a single commit.

## Commit Message Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary in imperative mood>
```

| Type       | Use for                                           |
| ---------- | ------------------------------------------------- |
| `feat`     | New feature or behaviour                          |
| `fix`      | Bug fix                                           |
| `refactor` | Code restructure with no behaviour change         |
| `test`     | Adding or updating tests                          |
| `docs`     | Documentation changes only                        |
| `chore`    | Build scripts, dependency updates, config changes |
| `style`    | Formatting only — no logic change                 |

Example: `feat(auth): add JWT refresh token rotation`

- Summary must be 72 characters or fewer.
- Use imperative mood: "add", not "added" or "adds".
- Reference the related task ID in the body if one exists: `Relates to T3`.

## What Never to Commit

- `.env` files or any file containing secrets, tokens, or API keys
- Build outputs or compiled artefacts (`dist/`, `build/`, `__pycache__/`, `.next/`, etc.)
- Lockfiles without a corresponding dependency change in the manifest
- IDE or OS-specific files (`.DS_Store`, `.idea/`) unless intentionally shared via `.gitignore` exceptions
- Files outside the current phase's agreed scope (the Coder must verify this via `git diff --stat`)

## Pull Requests

- Open one PR per phase or logical feature branch.
- PR title must match the Conventional Commits format.
- Include `Closes #N` in the PR description to auto-link and close the relevant GitHub issue on merge.
- The Orchestrator opens the PR **after** the user has reviewed local changes and confirmed they are ready.
- **The user approves and merges** — agents do not self-merge.
- Squash-merge feature branches into `main` to keep history linear.

## Coder Commit Responsibility

Before committing, the Coder must confirm:

1. All files for this phase exist in the **local workspace** and were written using local file-creation tools.
2. Dependencies are installed locally (`pip install -e ".[dev]"` / `pnpm install`) and all commands run without error.
3. `git diff --stat` shows only files within the current phase's scope.
4. All gate and test results are PASSED (no mid-remediation commits).
5. No files from the "What Never to Commit" list appear in the diff.
6. The user has been presented the local changes and has confirmed approval.

If any of these conditions fail, do not commit — raise a Blocking finding to the Orchestrator.
