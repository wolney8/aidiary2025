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

Profile is for biographical and reflection context:

- `first_name`
- `last_name`
- `age`
- `sex`
- `goals`

### Settings > Personalisation

Settings is for app-level and AI-level preferences:

- `display_name`
- `pronouns`
- `timezone`
- `ai_tone`
- `ai_verbosity`
- `ai_focus`
- `allow_ai_history`
- `chatgpt_daily_diary_coachname`
- `chatgpt_dream_diary_coachname`
- `dailydiary_api_key`
- `dreamdiary_api_key`

## API direction

- Keep `/api/profile` as the current compatibility endpoint for now.
- Extend it to read and write the new settings fields.
- Prefer later extraction into a clearer settings-specific contract only if needed after the UI settles.

## Consequences

- Top-bar naming should prefer `display_name`, then `first_name`, then `username`.
- Settings now becomes a meaningful destination rather than only a host for import/export tools.
- Existing users need runtime-safe schema compatibility for new `users` columns.

## To confirm

- Whether API keys should remain user-managed in-app or move behind a server-managed secret model later.
- Whether coach naming belongs under personalisation or under a separate AI settings section once chat work advances.
