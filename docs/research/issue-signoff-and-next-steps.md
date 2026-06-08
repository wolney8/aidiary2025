# Issue Sign-Off and Next Steps

## Current Branch

- Branch: `feat/94-import-manual-readd`
- Issue: `#94`
- Implementation status: code changed, not yet merged
- Checks already run:
  - `cd server && source venv/bin/activate && PYTHONPATH=. pytest tests/test_import.py -q`
  - `cd client && npm run build`

## Smoke Tests Required Before Sign-Off for `#94`

- Import a workbook with no duplicates and confirm it still imports immediately.
- Import a workbook with duplicates and confirm nothing is imported immediately.
- Confirm the screen shows a compact review-required summary plus `Show duplicates`.
- Open the duplicate modal and confirm rows are unchecked by default.
- Confirm the modal table shows:
  - human-readable date
  - entry type
  - title
  - truncated preview text
- Confirm `Accept and import without duplicates` imports only non-duplicate rows.
- Confirm `Accept and import with X duplicates` imports the checked duplicate rows.
- Confirm accepted duplicates receive the searchable tag `*Duplicate*`.
- Confirm the user remains on the import screen throughout duplicate handling.
- Confirm leaving the route before commit warns that the current review will be cancelled and lost.

## Ready To Commit When

- The smoke tests above pass.
- No unexpected files appear in `git status`.
- Diff scope remains limited to `#94`.

## Current Backlog Note

- `#93` improved duplicate reporting and enabled structured preview rows.
- `#94` now uses that payload for staged duplicate review and explicit import acceptance.

## Recommended Next-Issue Queue

1. `#94` Staged duplicate review and import acceptance
   - Finish current branch, smoke test, commit, merge.
2. `#91` Dream-entry AI image generation, retry flow, and prompt-hover metadata
   - Self-contained feature
   - Strong user-facing value
   - Builds on existing dream detail and image surfaces
3. `#88` Important days
   - Natural follow-on to calendar/date work
   - Local data model first
4. `#89` Public holidays and locale-based events
   - Depends on `#88` and settings/location decisions
   - External source integration should come after the local important-days model exists
5. `#86` AI prompt/model quality improvements
   - Keep after current UI/data-flow stabilisation
   - Likely broader and more iterative than the issues above
6. Chat cluster later
   - `#43`, `#44`, `#46`, `#47`, `#48`, `#49`, `#50`, `#76`, `#66`, `#68`
   - Treat as a coordinated stream rather than one isolated issue
