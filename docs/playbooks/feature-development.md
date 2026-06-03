# Feature Development

## Approach

1. Inspect the relevant feature area, adjacent services, routes, and tests.
2. Confirm the command surface before changing code.
3. State the intended scope and keep it narrow.
4. Implement in small steps following existing frontend or backend patterns.
5. Review the diff for unrelated edits.
6. Run relevant checks.
7. Summarise files changed, checks run, and residual risks.

## Repository-specific watchpoints

- Frontend routes may not fully match source files.
- Existing docs may describe older structures.
- Database-affecting work needs extra care because runtime migrations are in use.
- AI-related changes should inspect both route code and `server/services/openai_svc.py`.
