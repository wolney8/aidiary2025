---
name: validate-release-boundary
description: Use before AI Diary smoke-test handoff, commit, merge, or issue closure to inspect the complete diff, run applicable backend and frontend checks, and produce evidence-based sign-off status.
---

# Validate A Release Boundary

1. Run `git status --short --branch`, `git diff --stat`, and inspect the complete diff.
2. Confirm the change matches issue acceptance criteria and contains no secrets,
   generated artefacts, unrelated edits, or accidental database files.
3. Select checks by impact:
   - backend: `cd server && source venv/bin/activate && PYTHONPATH=. pytest`
   - frontend templates/routes/styles: `cd client && npm run build`
   - focused tests first when they shorten feedback, full applicable checks at boundary
4. For UI changes, inspect keyboard/focus behaviour, narrow widths, Material 3 patterns,
   and both light and dark themes. Use `ui-inspect` for a formal accessibility pass.
5. For database/storage/import work, verify old-data compatibility, ownership, rollback
   or failure behaviour, and portability assumptions.
6. Report:
   - checks run and exact results
   - checks unavailable or not run
   - concise manual smoke tests
   - residual risks
   - `ready`, `not ready`, or `blocked`

Never convert a warning into a pass silently. Do not close an issue based on branch intent;
validate merged or merge-ready behaviour against its acceptance criteria.

