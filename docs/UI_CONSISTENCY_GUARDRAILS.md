# UI Consistency Guardrails

Purpose: prevent workflow drift between View Entry and Edit Entry, and ensure a single canonical interaction pattern per feature.

## 1) Canonical Rule Set

1. Viewing screens are read-only unless a requirement explicitly states otherwise.
2. Editing is only allowed inside the Edit Entry workflow.
3. If metadata is editable in one place, all edits for that metadata must happen in the same workflow.
4. NLTK/AI enrichment is a first-pass suggestion; user edits are authoritative and persist to DB.
5. Duplicate sections with the same underlying data are not allowed.

## 2) Consistency Matrix Template (Planner Must Fill)

Copy this table into every issue plan before implementation:

| Area     | View Mode                        | Edit Mode         | Editable? | Source of Truth | Persisted Field(s)                      | Notes                     |
| -------- | -------------------------------- | ----------------- | --------- | --------------- | --------------------------------------- | ------------------------- |
| My Tags  | Visible chips                    | Inline chip input | Edit only | DB              | tags                                    | Type + Enter, chip remove |
| People   | Visible chips                    | Inline chip input | Edit only | DB              | daily_people_names / dream_people_names | User override wins        |
| Places   | Visible chips                    | Inline chip input | Edit only | DB              | daily_places / dream_places             | User override wins        |
| Keywords | OPTIONAL: remove if same as tags | N/A               | No        | N/A             | N/A                                     | Do not duplicate My Tags  |

Required planner checks:

- Confirm no duplicated metadata sections in View mode.
- Confirm one and only one edit workflow per metadata type.
- Confirm cancel/discard navigation target.

## 3) Designer Interaction Contract Template

Designer must provide this exact block for each affected screen:

- Screen: [name]
- Mode: [view/edit]
- Allowed actions: [list]
- Forbidden actions: [list]
- Entry points: [buttons/links that open this mode]
- Exit behaviour: [save target, cancel target]
- Error states: [save failure, validation message]
- Accessibility notes: [focus order, keyboard path, button labels]

Non-negotiable:

- Do not introduce new edit controls in View mode.
- Do not create a second visual edit pattern for the same data.

## 4) PR Checklist Text (Copy/Paste)

Use this in every PR touching UI workflows:

- [ ] I updated or confirmed the Consistency Matrix in this issue/PR.
- [ ] View mode is read-only for metadata.
- [ ] Metadata editing is available only in Edit Entry.
- [ ] My Tags, People, and Places use one consistent edit pattern in Edit Entry.
- [ ] No duplicated sections represent the same DB field in View mode.
- [ ] Cancel + discard from Edit Entry returns to the same entry detail page.
- [ ] User overrides are persisted and not overwritten by post-save enrichment.
- [ ] I ran frontend build and smoke-tested Daily + Dream flows.

## 5) Reviewer Gate (Must Pass Before Merge)

Reviewer must verify all items below:

1. Workflow parity:

- Daily and Dream paths both follow the same edit/view rules.

2. State consistency:

- What user sees after save equals what is in DB-backed payload fields.

3. Navigation consistency:

- Cancel/discard and Save routes are deterministic and documented.

4. UX consistency:

- No mixed patterns (for example, inline chips in one place and modal/form-plus-button elsewhere for same action).

## 6) Team Pause Ritual (Use Before New Milestone Work)

Duration: 5 minutes.

1. Planner reads the matrix aloud.
2. Designer confirms interaction contract line-by-line.
3. Coder repeats back the single canonical edit workflow.
4. Reviewer pre-selects two smoke tests to validate consistency.

If any disagreement appears, stop and update this document before coding.
