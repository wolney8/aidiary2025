---
description: "Use when building web applications, UI components, forms, navigation, interactive widgets, colour contrast, focus management, or any frontend code. Covers WCAG 2.2 accessibility standards and Context7 lookup."
---

# Web Accessibility — WCAG 2.2

## Context7 Lookup

- Before implementing any UI component or interaction pattern, use Context7 MCP to fetch the current WCAG 2.2 success criteria relevant to that component.
- Query with: `use context7` → search "WCAG 2.2 <component or criterion name>".
- Always verify against the authoritative source rather than relying on memorised rules.

## Compliance Target

- Minimum: **WCAG 2.2 Level AA** for all public-facing web applications.
- Strive for AAA on critical journeys (authentication, checkout, primary navigation).

## POUR Principles

| Principle      | Key concerns                                                                    |
| -------------- | ------------------------------------------------------------------------------- |
| Perceivable    | Text alternatives, captions, adaptable layout, 4.5:1 contrast ratio (AA)        |
| Operable       | Keyboard accessible, no seizure triggers, sufficient time limits, visible focus |
| Understandable | Consistent navigation, error identification, labels for all inputs              |
| Robust         | Valid HTML, ARIA used correctly, name/role/value for custom widgets             |

## WCAG 2.2 — New / Changed Criteria

| SC                                         | Level | Rule                                                            |
| ------------------------------------------ | ----- | --------------------------------------------------------------- |
| 2.4.11 Focus Not Obscured (Minimum)        | AA    | Focused component must not be entirely hidden by sticky content |
| 2.4.12 Focus Not Obscured (Enhanced)       | AAA   | Focused component must be fully visible                         |
| 2.4.13 Focus Appearance                    | AAA   | Focus indicator meets minimum size and contrast                 |
| 2.5.7 Dragging Movements                   | AA    | All drag operations have a single-pointer alternative           |
| 2.5.8 Target Size (Minimum)                | AA    | Interactive targets ≥ 24×24 CSS pixels                          |
| 3.2.6 Consistent Help                      | A     | Help mechanisms appear in consistent locations                  |
| 3.3.7 Redundant Entry                      | A     | Do not ask for information already provided in the same session |
| 3.3.8 Accessible Authentication (Minimum)  | AA    | No cognitive function test required to authenticate             |
| 3.3.9 Accessible Authentication (Enhanced) | AAA   | No exception for object recognition or user-content tests       |

## Implementation Checklist

- All images have meaningful `alt` text (or `alt=""` for decorative images).
- All form inputs have a programmatically associated `<label>`.
- Focus order follows a logical reading sequence.
- No content relies solely on colour to convey meaning.
- Custom interactive components expose correct ARIA roles, states, and properties.
- Test with a screen reader (VoiceOver / NVDA) and keyboard-only navigation before shipping.
