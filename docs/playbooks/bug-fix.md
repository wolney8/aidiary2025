# Bug Fix

## Approach

1. Reproduce the bug from code, tests, logs, or user report.
2. Read the exact feature files and nearby tests before editing.
3. Identify whether the issue is source logic, route/config drift, or environment/runtime behaviour.
4. Implement the smallest safe fix.
5. Review the diff for collateral edits.
6. Run the narrowest relevant checks first, then broader checks if the fix crosses boundaries.
7. Report the root cause, files changed, checks run, and any remaining uncertainty.

## Repository-specific watchpoints

- Missing source files may be part of the defect, not just the symptom.
- SQLite schema assumptions can cause bugs that only appear with existing local databases.
- Startup migrations and NLTK setup can hide or delay failures.
