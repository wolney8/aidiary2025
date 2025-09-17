# Test Results AIDIARY v0.10.3 - By the user


# Issues (v0.10.3)
All items addressed in code:
1. Sidebar links now keep the session alive—Daily/Dream filter the entries list via query params instead of redirecting to `/login`.
2. Timeline scroller renders the most recent four months based on the current date.
3. Daily entries support a title field (stored ahead of the body) so the list/detail screens highlight it consistently with dream entries.
4. "Cancel" on the New Entry screen confirms and returns to the entries list without saving.
5. "My Tags" input added to the creation flow (daily & dream) and persisted to SQLite, so tags appear immediately in the detail view.
