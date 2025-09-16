# docs/WIREFRAMES.md
# Wireframes Mapping

Wireframe PNGs show the following key components:

## Global Shell
- **Top bar**: hamburger menu + logo + search bar + filters dropdown + user avatar
- **Pill toggle**: "ALL ENTRIES" | "DAILY" | "DREAMS" (purple active state)

## Timeline Scroller
- Horizontal months navigation with arrow controls
- Shows "2024 September", "2024 October", etc.

## Entries List (Card Grid)
- Responsive card layout
- Each card shows:
  - Icon (moon for dreams, book for daily)
  - Title in quotes
  - Date (e.g., "Monday 7th June 2023")
  - Image placeholder (pie chart graphic)
  - Text snippet
  - "VIEW ENTRY" link (purple)

## Entry Detail View
- **Hero image area** at top with upload/regenerate controls
- **Two-column layout**:
  - Left: User's original text (editable)
  - Right: AI Response (with regenerate button)
- **Metadata bar** below:
  - My Tags (chips)
  - Keywords (chips)
  - People Names and Places
  - Image prompt display

## Search Results
- Shows "Search results for 'drive' in Keywords..."
- Highlights matching terms in orange/red
- Maintains card grid layout

## Side Navigation (when open)
- Home
- Daily Diary
- Dream Diary
- Settings
- Logout

## Visual Theme
- Primary colour: Purple (#7B3FF2)
- Card shadows and elevation
- 16px gutters, 24px vertical spacing
- Rounded corners on cards
- Material Design icons