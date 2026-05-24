---
description: "Use when coordinating multi-agent workflows that include code generation, enforcing review gates after code changes, running code quality or accessibility validation, or managing remediation loops. Defines the mandatory halt-and-review cycle the Orchestrator must follow after any Coder task."
---

# Review & Quality Gates

## Scope

Every workflow in which the Coder agent modifies or creates files is subject to this loop. The Orchestrator owns enforcement — the Coder must **never** self-approve phase completion.

---

## Precondition — Local Workspace (MANDATORY)

Before any gate can run, the following must be true:

1. **All files modified or created in this phase exist in the local workspace.** Files written only to a remote GitHub branch via API do not satisfy this precondition.
2. **Dependencies are installed locally.** For backend changes: `pip install -e ".[dev]"` must have run without error. For frontend changes: `pnpm install` must have run without error.
3. **The Coder is operating against the local filesystem**, not a remote API.

If the precondition is not met, the Coder has not completed its task. The Orchestrator must halt and instruct the Coder to write files locally before gates begin. Do not attempt to run gates remotely or treat a GitHub push as a substitute for local execution.

---

## Rule 1 — HALT After Code Changes

After the Coder returns from any code-producing task, the Orchestrator MUST:

1. **Halt further generation** — do not proceed to the next phase, task, or parallel branch.
2. **Declare a Review Phase** explicitly in the progress report.
3. Verify the local workspace precondition is met.
4. Run all quality gates (§ Gate 1, Gate 2, Gate 3) before resuming.

> In parallel phases: if any parallel task produced code, the entire phase pauses at completion and all gates run before the next phase begins.

---

## Rule 2 — Gate Sequence

Gates run **in this order**. All must pass; they cannot run concurrently.

### Gate 1 — Code Quality

|              |                                                                                       |
| ------------ | ------------------------------------------------------------------------------------- |
| **Executor** | Coder agent                                                                           |
| **Method**   | Invoke the `#lint-and-analyse` skill against every file modified in the current phase |
| **Pass**     | Zero blocking lint errors; type checker returns no errors after auto-fix              |
| **Fail**     | Any blocking lint error or type error persists after auto-fix                         |

### Gate 2 — Accessibility Compliance

|                       |                                                                                                                                                                                                                                                                      |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Executor**          | Coder agent                                                                                                                                                                                                                                                          |
| **Applicability**     | Only when modified files include frontend source files — markup, templates, component files, or stylesheets. Refer to the `Frontend` field in the **Stack Declaration** section of `copilot-instructions.md` to determine which file types qualify for this project. |
| **Method**            | Use the Context7 MCP server to fetch current WCAG 2.2 success criteria for each modified component or pattern — query: `use context7` → search `"WCAG 2.2 <component or criterion name>"`. Validate each component against the returned criteria.                    |
| **Compliance target** | WCAG 2.2 Level AA minimum. For criteria, POUR principles, and the new SC table, refer to `wcag-accessibility.instructions.md` — do not duplicate them here.                                                                                                          |
| **Pass**              | All relevant AA success criteria are met for every modified component                                                                                                                                                                                                |
| **Fail**              | Any AA violation is identified                                                                                                                                                                                                                                       |
| **Not applicable**    | No frontend files modified — record as "N/A" and proceed                                                                                                                                                                                                             |

### Gate 3 — Security

|                    |                                                                                                                                                                        |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Executor**       | Coder agent                                                                                                                                                            |
| **Applicability**  | All phases where code was modified                                                                                                                                     |
| **Method**         | Detect available security tooling from the table below and run the appropriate scanner. Also scan all modified files for hard-coded credentials, API keys, or secrets. |
| **Pass**           | No high or critical severity findings; no credentials or secrets detected in source files                                                                              |
| **Fail**           | Any high or critical severity vulnerability; any credential or secret found in source                                                                                  |
| **Not applicable** | Only documentation or non-executable config files modified with no dependency changes                                                                                  |

#### Security Tool Detection

| Config file present                     | Tool to run                    |
| --------------------------------------- | ------------------------------ |
| `package.json`                          | `npm audit --audit-level=high` |
| `pyproject.toml` or `requirements*.txt` | `pip-audit`                    |
| `go.mod`                                | `govulncheck ./...`            |
| `Gemfile`                               | `bundle audit`                 |
| Any (if installed)                      | `semgrep --config auto`        |

If no tool is available, perform a manual review of modified files against OWASP Top 10 patterns — refer to the Security finding type in `testing-and-feedback.instructions.md`.

---

## Rule 3 — Remediation Loop

When either gate fails, execute this loop:

1. **Raise a structured finding** containing:
   - Which gate failed (Code Quality / Accessibility)
   - The specific file(s) and rule(s) violated
2. **Delegate to the Coder** with the finding as the sole input. The Coder addresses only the flagged items — no new features or unrelated changes.
3. **Re-run Gate 1, Gate 2, then Gate 3** after the Coder returns, regardless of which gate originally failed.
4. Repeat until both gates pass or the iteration cap is reached.

### Iteration Cap

- **Maximum 3 remediation iterations** per phase.
- If both gates have not passed after 3 iterations, **halt immediately and escalate to the user** with a structured report:
  - Which gate failed
  - Which files are affected
  - Remaining violations listed verbatim
- **Do not proceed** to the next phase under any circumstances until gates pass or the user explicitly overrides.

---

## Rule 4 — Gate Ownership

| Role              | Responsibility                                                                                |
| ----------------- | --------------------------------------------------------------------------------------------- |
| **Orchestrator**  | Initiates each gate, evaluates pass/fail, tracks iteration count, escalates if cap is hit     |
| **Coder**         | Executes `#lint-and-analyse`, runs Context7 WCAG lookup, runs security scan, implements fixes |
| **Neither agent** | Self-approves gate passage — only the Orchestrator records a gate as passed                   |

---

## Rule 5 — User Handoff Before Git Operations

Once all gates pass, the Orchestrator MUST:

1. **Present the local changes to the user** — summarise what files were created or modified, what the tests confirmed, and the gate results.
2. **Await explicit user approval** before any git operation (commit, push, branch creation, PR).
3. Only after approval: instruct the Coder to commit locally, push to the remote branch, and open the PR via GitHub MCP.

This rule exists to ensure the user can inspect, run, and verify the application locally before the changes become part of the permanent git history.

---

## Rule 6 — Phase Completion Report

Once all gates pass and the user has approved, include a gate summary in the phase completion report:

```
Gate 1 (Code Quality): PASSED — N issues auto-fixed, 0 remaining
Gate 2 (Accessibility): PASSED / NOT APPLICABLE
Gate 3 (Security):     PASSED / NOT APPLICABLE
User handoff:          APPROVED by user on [date]
```

If a gate triggered remediation, note the iteration count: `PASSED after 2 iterations`.
