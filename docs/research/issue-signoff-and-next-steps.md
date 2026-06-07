# Issue Sign-Off and Next Steps

## Current Branch

- Branch: `feat/93-import-duplicate-reporting`
- Issue: `#93`
- Implementation status: code changed, not yet merged
- Checks already run:
  - `cd server && source venv/bin/activate && PYTHONPATH=. pytest tests/test_import.py -q`
  - `cd client && npm run build`

## Smoke Tests Required Before Sign-Off for `#93`

- Import a workbook with at least one true duplicate.
- Confirm summary counts still render.
- Confirm `Skipped duplicates` section appears.
- Confirm each skipped row shows:
  - human-readable date
  - entry type
  - title
  - preview text
- Confirm long skipped lists collapse to 5 items by default.
- Confirm `Show all skipped duplicates` expands the full list.
- Confirm no regression to non-duplicate imports.

## Ready To Commit When

- The smoke tests above pass.
- No unexpected files appear in `git status`.
- Diff scope remains limited to `#93`.

## Current Backlog Note

- `#93` improves reporting only.
- `#94` is still needed for manual re-add actions.

## Recommended Next-Issue Queue

1. `#93` Import duplicate skip reporting
   - Finish current branch, smoke test, commit, merge.
2. `#94` Review skipped entries and allow manual re-add
   - Depends on `#93`.
   - Use the structured duplicate payload from `#93`.
   - Recommended safe v1:
     - user reviews skipped rows
     - click action opens create-entry prefilled rather than silently forcing import
3. `#91` Dream-entry AI image generation, retry flow, and prompt-hover metadata
   - Self-contained feature
   - Strong user-facing value
   - Builds on existing dream detail and image surfaces
4. `#88` Important days
   - Natural follow-on to calendar/date work
   - Local data model first
5. `#89` Public holidays and locale-based events
   - Depends on `#88` and settings/location decisions
   - External source integration should come after the local important-days model exists
6. `#86` AI prompt/model quality improvements
   - Keep after current UI/data-flow stabilisation
   - Likely broader and more iterative than the issues above
7. Chat cluster later
   - `#43`, `#44`, `#46`, `#47`, `#48`, `#49`, `#50`, `#76`, `#66`, `#68`
   - Treat as a coordinated stream rather than one isolated issue
