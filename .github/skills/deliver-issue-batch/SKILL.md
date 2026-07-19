---
name: deliver-issue-batch
description: Use when implementing one to three related AI Diary issues as a continuous delivery batch, including dependency checks, bounded planning, implementation, review, validation, and a combined handoff.
---

# Deliver An Issue Batch

1. Read `AGENTS.md` and run `git status --short --branch`.
2. Confirm each issue is related by feature surface, dependency, or shared validation.
   Split unrelated issues rather than mixing their diffs.
3. Inspect affected source, interfaces, and tests before planning. Identify existing-data,
   privacy, accessibility, responsive, and light/dark-mode implications.
4. State one batch plan with vertical slices, expected files, checks, and rulings needed.
5. Implement each slice completely. Add regression tests alongside behavioural changes.
6. Review the diff after each slice. Commit separately only when commits are authorised.
7. Run targeted checks as work proceeds, then use `validate-release-boundary` once for
   the complete batch.
8. Provide one combined manual smoke path and an exact next action.

Do not pause for routine code choices. Escalate only under the authority rules in
`AGENTS.md`. Do not leave one issue half-built merely to begin another.

