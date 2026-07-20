# Data Portability Contract

The fidelity export format is a `.zip` package containing `entries.xlsx`,
`manifest.json`, and media files under `media/<entry_asset_ref>/`. Package format version
1 is re-importable through Settings > Import. Plain `.xlsx` remains a text-only format.

## Preserved

- Daily: date, time, title, user text, and saved AI response
- Dream: date, time, title, plot, cast, location, period, emotion, symbols and imagery,
  insight, action, other notes, and tags
- Daily and Dream hero images, image source, prompt recovery fields, and X/Y framing
- Entry attachments, original filenames, MIME types, and ordering

## Normalised during import

- Blank Daily times become `19:00`; blank Dream times become `08:00`.
- Dates and times are stored in canonical ISO date and `HH:MM` formats.
- Search/NLTK metadata is recalculated from imported text.
- Duplicate detection is user-scoped and requires the same entry type, date, normalised
  title, and normalised body/plot. Accepted duplicates receive the `*Duplicate*` tag.

## Not currently included

- account, Profile, and Customisation settings
- important days and public-holiday preferences
- chat history
- attachment-derived text and audio transcripts
- Daily mood and derived tags, people, and places
- Dream AI summary and interpretation

The manifest carries this contract in machine-readable form. Import reports package
version differences, unexpected workbook columns, missing packaged media, and declared
omissions in its user-facing warning list. Older packages without the portability section
remain supported.

## External import adapters

External sources map into the same normalised import payload before duplicate review and
database insertion. The adapter registry in `server/services/import_adapters.py` isolates
provider-specific parsing from the core import flow.

Daylio CSV is the first adapter. It preserves entry date/time, note title, note, mood, and
activities; activities become searchable tags. Header aliases are tolerated because Daylio
does not publish a versioned CSV schema. Proprietary `.daylio` backup files are not accepted.
Future providers implement the same adapter protocol and register without changing staged
import, duplicate review, or history handling.
