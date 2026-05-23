---
description: "Use when coordinating testing workflows, validating functional correctness after code changes, defining how review or testing agents communicate findings to each other and to the user, or tracking review status in a multi-agent session."
---

# Testing & Feedback

## Scope

This file governs:

- When and how functional tests are written and executed
- How agents structure and communicate findings (the shared finding schema)
- How findings cascade through the team — agent to agent, and agent to user
- When and how the user receives proactive status updates

This file does **not** cover automated quality gates (lint, type-checking, accessibility checks) or the remediation iteration cap — those are defined in `review-quality-gates.instructions.md`.

---

## Rule 1 — Testing Phase

The Orchestrator schedules a Testing Phase **after all quality gates have passed** and before marking any phase complete. The Coder agent executes it.

### What Must Be Tested

| Work type              | Minimum coverage                                                                         |
| ---------------------- | ---------------------------------------------------------------------------------------- |
| New function or module | Unit tests for all exported functions — happy path plus one error or edge case each      |
| Modified function      | Tests for the changed behaviour only; update existing tests rather than duplicating them |
| UI component           | Interaction tests: click, keyboard navigation, and form submission where applicable      |
| API endpoint           | Request/response contract test and one error-path test                                   |
| Integration change     | One end-to-end test covering the primary user journey affected                           |

### Execution Steps

The Coder agent:

1. Writes missing tests before running any.
2. Runs the suite scoped to files touched in the current phase.
3. Returns a **Test Result Report** using the Structured Finding format defined in § Rule 3.

> **Architectural note:** Test execution (Coder) and test evaluation (Orchestrator via the review checklist) are intentionally split across two existing agents. This provides logical separation of concerns without requiring a dedicated Tester agent.

---

## Rule 2 — Functional Review Checklist

After the Testing Phase, the Orchestrator evaluates functional correctness. This is distinct from automated gate checks and is performed by the Orchestrator, not the Coder.

- [ ] All tests pass — no skipped, suppressed, or quarantined failures
- [ ] Implementation matches the Planner's specification: correct files, correct behaviour, correct scope
- [ ] No unintended side effects outside the current phase's files (verify via `git diff --stat`)
- [ ] Edge cases identified in the Planner's output are addressed or explicitly deferred
- [ ] No hard-coded credentials, magic strings, undeclared secrets, or OWASP Top 10 anti-patterns introduced

Each failed item generates a Blocking finding. The Orchestrator then enters the feedback loop (§ Rule 4).

### Advisory Checks

The following items generate **Advisory** findings only — reported to the user but they do not block the next phase:

- [ ] If a public function, class, or API endpoint signature changed, inline documentation reflects the change
- [ ] If this phase's changes affect the `Architecture` section of `copilot-instructions.md`, it has been updated

---

## Rule 3 — Structured Finding Format

Every finding — whether from a failed test, a review checklist failure, a code quality gate, or an accessibility gate — MUST use this schema. This is the single canonical format; findings from `review-quality-gates.instructions.md` use it too.

```
FINDING
Type:      Test Failure | Functional Review | Code Quality | Accessibility | Security | Dependency | Documentation
Severity:  Blocking | Advisory
File(s):   <workspace-relative paths, one per line>
Rule:      <test name, checklist item, gate rule, or WCAG SC reference>
Detail:    <one sentence — what failed and why it matters>
Expected:  <what correct behaviour or output looks like>
```

- **Blocking** — prevents phase sign-off; must be resolved or user-overridden before progression.
- **Advisory** — reported to the user but does not block the next phase.
- When in doubt, default to **Blocking**.

---

## Rule 4 — Feedback Cascade

```
Test result or review checklist
           │
           ▼
Orchestrator evaluates — Blocking or Advisory?
           │
           ├─ Blocking ──► Delegate to responsible agent with finding(s) as sole context
           │                         │
           │                         ▼
           │                   Agent returns fix
           │                         │
           │                         ▼
           │                Re-run tests + review checklist
           │                         │
           │                         └─ Repeat until resolved
           │                            (iteration cap: see review-quality-gates.instructions.md)
           │
           └─ Advisory only ──► Proceed to next phase; include in user status report
```

### No Silent Failures

Agents must never discard, suppress, or omit findings. If a finding cannot be categorised, it is **Blocking** by default.

### Responsible Agent Per Finding Type

| Finding type      | Delegated to                                                                     |
| ----------------- | -------------------------------------------------------------------------------- |
| Test Failure      | Coder                                                                            |
| Functional Review | Coder                                                                            |
| Code Quality      | Coder                                                                            |
| Accessibility     | Coder (with Context7 lookup as required by `wcag-accessibility.instructions.md`) |
| Security          | Coder                                                                            |
| Dependency        | Coder                                                                            |
| Documentation     | Coder                                                                            |
| Design deviation  | Designer                                                                         |

---

## Rule 5 — User Communication

The Orchestrator sends the user a status update at these trigger points only:

| Trigger                                 | What to send                                                                      |
| --------------------------------------- | --------------------------------------------------------------------------------- |
| Phase complete (all gates + tests pass) | Phase completion report (see format below)                                        |
| Blocking finding after iteration cap    | Full escalation report — findings verbatim, files affected, recommended next step |
| Advisory finding                        | Inline note within the phase completion report                                    |
| Open question or ambiguity from Planner | Prompt the user **before** starting implementation — do not assume or proceed     |

### Phase Completion Report Format

```
## Phase [N] Complete — [Phase Name]

**Changes**: <one-line summary of what was built or changed>

**Gates**:
- Code Quality: PASSED (N issues auto-fixed) | PASSED | N/A
- Accessibility: PASSED | NOT APPLICABLE

**Tests**: PASSED — N run, 0 failed
  (or: N run, N failed — findings listed below)

**Advisories**: <bulleted list, or "None">
```

### User Overrides

If the user explicitly overrides a Blocking finding:

1. Record the override in session memory via `vscode/memory`, tagging it `USER-OVERRIDDEN`.
2. Annotate the original finding with `[USER-OVERRIDDEN — <date/phase>]`.
3. Continue to the next phase.

The finding is not cleared — it persists in the session log for traceability.

---

## Rule 6 — Ownership Summary

| Role             | Responsibility                                                                                                 |
| ---------------- | -------------------------------------------------------------------------------------------------------------- |
| **Planner**      | Identifies test-relevant edge cases; includes them in the implementation plan so the Coder knows what to cover |
| **Coder**        | Writes and runs tests; submits Test Result Report; implements fixes for all Blocking findings delegated to it  |
| **Designer**     | Reports UI deviations from spec as Blocking or Advisory findings using the schema in § Rule 3                  |
| **Orchestrator** | Runs the functional review checklist; evaluates all findings; communicates to the user; records overrides      |
