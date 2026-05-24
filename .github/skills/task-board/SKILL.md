---
name: task-board
description: "Use when managing project tasks, mapping cross-module dependencies, creating GitHub issues from a plan, updating project boards, tracking phase completion, or identifying blocked work items."
---

# Task Board and Dependency Tracking

## When to Use

- Planning a multi-phase implementation and needing to track what blocks what
- Creating GitHub issues from an Orchestrator or Planner output
- Reporting phase completion status back to the user
- Mapping which modules depend on shared interfaces or outputs from other tasks

## Procedure

### 1. Map Tasks and Dependencies

For each task in the plan, record:

- **ID**: short identifier (e.g. `T1`, `T2`)
- **Description**: one sentence
- **Depends on**: list of IDs that must complete first
- **Assignee**: which agent or role handles it
- **Files touched**: paths affected

Output as a dependency table before execution begins.

### 2. Identify Blockers

- A task is **blocked** if any dependency is incomplete or has an open question.
- A task is **ready** if all dependencies are resolved.
- Escalate persistent blockers to the user before proceeding.

### 3. Create GitHub Issues (using `issue_write`)

**Prerequisites — verify before creating any issues:**

- Confirm labels `phase:N`, `status:ready`, and `status:blocked` exist using `issue_read` (method: `get_labels`) on any existing issue, or `get_label`. These labels have no create tool and **must be created manually in GitHub** before this skill runs.
- Confirm the target milestone exists and note its number. There is no `list_milestones` tool — obtain the milestone number from the GitHub UI or repository settings before proceeding.

For each task, call `issue_write` (method: `create`) with:

- `title`: `[Phase N] <description>`
- `labels`: `["phase:N", "status:ready"]` or `["phase:N", "status:blocked"]`
- `body`: dependencies listed as `Depends on: #<issue-number>`
- `milestone`: milestone number (integer, not name)

After all issues are created, link child task issues to their parent phase issue using `sub_issue_write` (method: `add`), passing the child's issue ID in `sub_issue_id`. This enforces the dependency hierarchy from Step 1 directly in GitHub.

### 4. Update Task State

Whenever a task transitions state, call `issue_write` (method: `update`) to keep GitHub in sync:

- **Unblocked**: swap label `status:blocked` → `status:ready`
- **Completed**: set `state: "closed"` and `state_reason: "completed"`, swap label to `status:done`
- **Cancelled**: set `state: "closed"` and `state_reason: "not_planned"`
- **Duplicate**: set `state_reason: "duplicate"` and pass `duplicate_of: <issue-number>`

Reprioritise sub-issues within a parent phase issue using `sub_issue_write` (method: `reprioritize`) with `after_id` or `before_id` as needed.

### 5. Track In-Session Progress

Use the `todo` tool to mirror task state during the session, and call `issue_write` (method: `update`) alongside each transition to keep GitHub in sync:

- Mark tasks `in-progress` as agents begin work
- Mark `completed` immediately when an agent confirms done
- Never batch completions

### 6. Report Status

Before each new phase, fetch live state from GitHub using `search_issues` with label filters (e.g. `label:phase:2 label:status:blocked repo:owner/repo`), then output:

```
## Phase N Status
Ready:   T3, T4
Blocked: T5 (waiting on T3)
Done:    T1, T2
```
