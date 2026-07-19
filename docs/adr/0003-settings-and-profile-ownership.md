# ADR 0003: Settings And Profile Ownership

## Status

Accepted as the current UI and API ownership direction.

## Context

The current application mixes personal profile data, AI preferences, coach settings, and integration keys inside a single profile surface and a single `/api/profile` contract. A real Settings area now exists in routing, but until now it only hosted import and export tools.

Open GitHub work also points to this split:

- `#64` Finish Settings experience
- `#69` Settings consolidation plan
- `#71` Personalisation schema and API completion

## Decision

Use this ownership split going forward:

### Profile

Profile is the canonical UI for account identity:

- `first_name`
- `last_name`
- `age`
- `display_name`
- `pronouns`
- `gender`

### Settings > Personalisation

Settings is for app-level and AI-level preferences:

- `timezone`
- `holiday_country_code`
- `show_public_holidays`
- `ai_tone`
- `ai_verbosity`
- `ai_focus`
- `ai_model`
- `allow_ai_history`
- `allow_ai_attachment_context`
- `custom_guidance`

## API direction

- Keep `/api/profile` as the current compatibility endpoint for now.
- Extend it to read and write the new settings fields.
- Prefer later extraction into a clearer settings-specific contract only if needed after the UI settles.

## Consequences

- Top-bar naming should prefer `display_name`, then `first_name`, then `username`.
- Settings now becomes a meaningful destination rather than only a host for import/export tools.
- Existing users need runtime-safe schema compatibility for new `users` columns.
- Legacy coach-name and per-mode API-key columns remain in the compatibility API and
  database, but are not shown in the UI because they are not consumed by the active
  AI service.

## To confirm

- Whether a future bring-your-own-key feature should use encrypted server-side
  credentials or an external secret manager. Plaintext browser round-tripping is not
  an acceptable production design.
- Whether coach naming should return once chat work has a concrete consumer for it.
