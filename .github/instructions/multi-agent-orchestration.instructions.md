---
description: "Use when designing multi-agent systems, orchestration workflows, agent pipelines, subagent delegation, parallel task execution, or fan-out/gather patterns."
---

# Multi-Agent Orchestration

## Architecture Patterns

- **Orchestrator–worker**: one coordinating agent decomposes the task and delegates to specialised workers; workers return structured results.
- **Fan-out / gather**: launch independent subtasks in parallel, aggregate results before proceeding.
- **Sequential chain**: output of one agent becomes the input of the next; use only when strict ordering is required.
- **Hierarchical**: limit nesting to 2–3 levels; deeper trees increase latency and error propagation.

## Context Isolation

- Each subagent receives only the context it needs — avoid passing the full conversation history.
- Subagents communicate via structured outputs (typed objects or JSON), not free-form prose.
- Never share mutable state directly between agents; use explicit handoffs.

## Tool Restrictions

- Assign the minimal tool set required for each agent's role.
- Restrict write/destructive tools to the single agent responsible for side effects.
- Read-only exploration agents must not invoke write or shell tools.

### Coder Agent — File Writing Rule (MANDATORY)

The Coder agent is the **only** agent that writes files. It must follow these rules without exception:

1. **Write all files to the local workspace** (the project root open in VS Code) using local file-creation and file-editing tools provided by VS Code.
2. **Never use GitHub MCP tools** (`push_files`, `create_or_update_file`, `delete_file`) to write source code, tests, configuration files, or instruction files. These tools are reserved for project management operations only (issues, PRs, labels, milestones).
3. **Install dependencies locally** after creating or modifying package manifests — `pip install -e ".[dev]"` for backend changes, `pnpm install` for frontend changes. Run these in the terminal. After installing backend deps, regenerate `backend/requirements.txt` by running `pip freeze > requirements.txt` from inside the `backend/` directory with the venv activated. Commit the updated lockfile as part of the same change.
4. **Run all lint, type-check, and test commands locally** against the files just written. Do not treat a successful GitHub push as a substitute for local validation.
5. **Report completion** to the Orchestrator with: list of files written, commands run, and their pass/fail results. Do not self-approve gate passage.

The Coder must never commit or push to git. That responsibility belongs to the Orchestrator, and only after the user has reviewed and approved.

### Designer Agent — File Writing Rule

The Designer produces specifications, tokens, and visual assets. Any output that results in a file being written (e.g., updating `brand-guidelines.instructions.md`, creating a token CSS file) must follow the same local-first rule as the Coder. The Designer reports its output to the Orchestrator, who delegates file writing to the Coder if needed.

### Orchestrator — No File Writing

The Orchestrator coordinates, delegates, and reports. It does not write source code or configuration files. The only write operations the Orchestrator may perform directly are via GitHub MCP project management tools (issues, PRs, milestones) — and only after the user has approved the phase.

### Planner — Read Only

The Planner researches the codebase and produces plans. It uses only read tools (file search, file read, semantic search, codebase exploration). It does not write files.

## Reliability

- Design each agent to be idempotent where possible.
- Include a fallback or retry strategy at the orchestrator level, not inside workers.
- Surface errors explicitly through structured error fields rather than silent failures.

## Agent Failure Recovery

When a subagent returns an empty response, an unhandled error, or output that does not match the assigned task:

1. **Retry once** with the identical input — transient failures are common.
2. **Decompose** — if the retry fails, break the task into smaller subtasks and delegate each independently.
3. **Escalate** — if decomposition does not resolve the failure after one further attempt, halt and report to the user:
   - Which agent failed and on which task
   - What input was provided
   - What error or missing output was returned
   - A suggested next step (manual intervention or task reformulation)

Never silently substitute a different agent for the intended one, or proceed as if the task completed, without informing the user.

## Single Responsibility

- One concern per agent where possible.
- The deliberate exception in this scaffold: the Coder **executes** tests as a coupled pre-submission step, while the Orchestrator independently **evaluates** results — providing logical separation without an additional agent.
- If an agent's description covers more than one domain beyond this sanctioned exception, split it.
