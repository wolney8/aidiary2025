---
name: lint-and-analyse
description: "Use before committing or completing any code task to run linters, type checkers, and static analysis. Covers ESLint, Biome, Ruff, TypeScript compiler, Pyright, and mypy."
---

# Lint and Static Analysis

## When to Use

- After editing any source file, before marking the task complete
- When the Orchestrator asks for a quality check before the next phase
- Before any `git commit` or pull-request step

## Procedure

### 1. Detect Tooling

Check for config files to determine the active toolchain:

| Config file                         | Tool                |
| ----------------------------------- | ------------------- |
| `eslint.config.*`, `.eslintrc.*`    | ESLint              |
| `biome.json`                        | Biome               |
| `tsconfig.json`                     | TypeScript compiler |
| `pyproject.toml` with `[tool.ruff]` | Ruff                |
| `pyproject.toml` with `[tool.mypy]` | mypy                |
| `pyrightconfig.json`                | Pyright             |

### 2. Run Linter

Execute the project's configured linter:

- **JS/TS (ESLint)**: `npx eslint .`
- **JS/TS (Biome)**: `npx biome check .`
- **Python (Ruff)**: `ruff check .`
- **Python (Flake8)**: `flake8`

### 3. Run Type Checker

- **TypeScript**: `npx tsc --noEmit`
- **Python (Pyright)**: `pyright`
- **Python (mypy)**: `mypy .`

### 4. Auto-fix Safe Issues

Apply only safe, auto-fixable corrections:

- `npx eslint . --fix`
- `npx biome check . --write`
- `ruff check . --fix`

### 5. Report

- List any remaining errors with file and line references.
- Do **not** proceed to commit or mark the task complete if blocking errors remain.
- Surface warnings separately from errors.
