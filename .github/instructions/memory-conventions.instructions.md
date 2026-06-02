---
description: "Use when writing to or reading from agent memory, deciding what to persist across a session, structuring memory entries, or determining when to prune stale records."
---

# Memory Conventions

## Scope

These conventions apply to all use of `vscode/memory` by any agent. Free-form or unstructured entries are not permitted — all writes must follow the format below.

---

## What to Persist

### Always persist

- User override decisions on Blocking findings (required by `testing-and-feedback.instructions.md`)
- Explicit user decisions made during a session (e.g. "use JWT, not session cookies")
- Stack declarations detected at runtime that extend or differ from `copilot-instructions.md`
- Open questions that are blocking a phase and awaiting user input

### Persist when significant

- Architecture decisions affecting more than one file or module
- Non-obvious bugs that were discovered and fixed (so agents do not repeat the investigation)
- Codebase conventions that deviate from the instruction defaults (e.g. project uses tabs, not spaces)

### Never persist

- Intermediate working notes or drafts
- Gate pass/fail details (these belong in the phase completion report)
- File contents (redundant — use read tools at runtime)
- Anything that can be reconstructed from the codebase in under 30 seconds

---

## Entry Format

Every entry must be a single line in this exact format:

```
[SCOPE][PHASE-N][YYYY-MM-DD] CATEGORY: <concise fact or decision>
```

| Field        | Allowed values                                                                          |
| ------------ | --------------------------------------------------------------------------------------- |
| `SCOPE`      | `SESSION` — current work session only; `REPO` — persists across sessions                |
| `PHASE-N`    | Phase number when the entry was created; use `PHASE-0` for pre-implementation decisions |
| `YYYY-MM-DD` | ISO 8601 date                                                                           |
| `CATEGORY`   | `OVERRIDE` · `DECISION` · `OPEN` · `PATTERN` · `BUG`                                    |

### Examples

```
[SESSION][PHASE-2][2026-05-21] OVERRIDE: User overrode Blocking accessibility finding in LoginForm — contrast ratio 3.8:1 accepted
[REPO][PHASE-1][2026-05-21] DECISION: Using Biome instead of ESLint — confirmed by user
[SESSION][PHASE-3][2026-05-21] OPEN: Awaiting user decision on pagination strategy before Phase 4 can start
[REPO][PHASE-2][2026-05-21] PATTERN: Project uses 2-space indentation in Python (deviation from PEP 8 default)
[REPO][PHASE-1][2026-05-21] BUG: Circular import between auth/middleware and auth/utils — resolved by extracting shared types to auth/types
```

---

## Pruning Rules

| Category   | Retain until                                                                                                          |
| ---------- | --------------------------------------------------------------------------------------------------------------------- |
| `SESSION`  | End of the current work session — propose clearing when the user closes the session or starts a new unrelated feature |
| `OVERRIDE` | 30 days, or until the underlying issue is fully resolved and the affected code is refactored                          |
| `DECISION` | Indefinitely, or until the user explicitly reverses the decision                                                      |
| `OPEN`     | Until the user answers — then convert to a `DECISION` entry and delete the `OPEN` entry                               |
| `PATTERN`  | Indefinitely, or until the codebase convention changes                                                                |
| `BUG`      | Until the root cause is confirmed fixed and the fix is merged                                                         |

**Pruning is always user-confirmed.** An agent may propose pruning stale entries but must never delete them autonomously.
