# Working Cadence

## Default session flow

1. Analyse
   Run `git status --short --branch`, inspect the relevant files, and confirm the real stack and command surface from project files.
2. Plan
   State the intended change, files likely to change, commands to run, and any `To confirm` items.
3. Implement
   Make the smallest change that satisfies the task. Avoid broad opportunistic edits.
4. Review
   Check `git diff --stat` and inspect the actual diff for unintended changes.
5. Test
   Run relevant checks from `docs/playbooks/testing-and-validation.md`.
6. Summarise
   Report files changed, commands run, results, and remaining risks.

## Non-negotiables

- Inspect before editing.
- Do not overwrite unexpected user changes.
- Stop and report if the repository state contradicts the task.
- Prefer one coherent change set over mixed unrelated edits.
