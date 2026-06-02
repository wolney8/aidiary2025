---
description: "Use when designing or reviewing any UI component, marketing material, or user-facing content. Defines brand colours, typography, logo usage, spacing, and voice and tone. Customise this file for your organisation before using the Designer agent."
---

# Brand Guidelines

> **Setup required.** Replace all `TODO:` values below with your organisation's brand specifications before using the Designer agent. If no brand guidelines exist yet, leave the defaults and update them incrementally as your design system evolves.

---

## Colours

| Role             | CSS token                 | Value                |
| ---------------- | ------------------------- | -------------------- |
| Primary          | `--colour-primary`        | `TODO: e.g. #0052CC` |
| Primary hover    | `--colour-primary-hover`  | `TODO: e.g. #0747A6` |
| Secondary        | `--colour-secondary`      | `TODO: e.g. #253858` |
| Accent           | `--colour-accent`         | `TODO: e.g. #FF5630` |
| Background       | `--colour-background`     | `TODO: e.g. #FFFFFF` |
| Surface          | `--colour-surface`        | `TODO: e.g. #F4F5F7` |
| Text — primary   | `--colour-text-primary`   | `TODO: e.g. #172B4D` |
| Text — secondary | `--colour-text-secondary` | `TODO: e.g. #5E6C84` |
| Border           | `--colour-border`         | `TODO: e.g. #DFE1E6` |
| Error            | `--colour-error`          | `TODO: e.g. #DE350B` |
| Success          | `--colour-success`        | `TODO: e.g. #00875A` |
| Warning          | `--colour-warning`        | `TODO: e.g. #FF991F` |

All text/background colour pairs must meet WCAG 2.2 AA contrast (4.5:1 for normal text, 3:1 for large text and UI components). Verify using the `#ui-inspect` skill.

---

## Typography

| Role             | Font family                 | Size                  | Weight           | Line height      |
| ---------------- | --------------------------- | --------------------- | ---------------- | ---------------- |
| Heading 1        | `TODO: e.g. Inter`          | `TODO: e.g. 2rem`     | `TODO: e.g. 700` | `TODO: e.g. 1.2` |
| Heading 2        | `TODO`                      | `TODO`                | `TODO`           | `TODO`           |
| Heading 3        | `TODO`                      | `TODO`                | `TODO`           | `TODO`           |
| Body             | `TODO: e.g. Inter`          | `TODO: e.g. 1rem`     | `TODO: e.g. 400` | `TODO: e.g. 1.5` |
| Small / caption  | `TODO`                      | `TODO: e.g. 0.875rem` | `TODO`           | `TODO`           |
| Code / monospace | `TODO: e.g. JetBrains Mono` | `TODO: e.g. 0.875rem` | `TODO: e.g. 400` | `TODO`           |

Minimum interactive target size: 24×24 CSS pixels (WCAG 2.5.8 AA). Strive for 44×44 px on touch interfaces.

---

## Logo

| Usage                           | Asset path or URL                        |
| ------------------------------- | ---------------------------------------- |
| Primary logo — light background | `TODO: e.g. /assets/logo/logo-dark.svg`  |
| Primary logo — dark background  | `TODO: e.g. /assets/logo/logo-light.svg` |
| Icon / favicon                  | `TODO: e.g. /assets/logo/icon.svg`       |

Logo rules:

- `TODO: e.g. Minimum display width 120 px; always maintain aspect ratio`
- `TODO: e.g. Clear space equal to the cap height of the wordmark on all sides`
- `TODO: e.g. Never place the logo on a background with less than 3:1 contrast ratio`

---

## Spacing Scale

`TODO: Replace with your design system's spacing scale.`

Example (8 pt grid): `4px · 8px · 12px · 16px · 24px · 32px · 48px · 64px · 96px`

Border radius: `TODO: e.g. 4px for inputs, 8px for cards, 999px for pills`

---

## Voice and Tone

| Dimension          | Guideline                                                                                      |
| ------------------ | ---------------------------------------------------------------------------------------------- |
| Formality          | `TODO: e.g. Professional but approachable — avoid jargon and acronyms`                         |
| Perspective        | `TODO: e.g. Second person ("you") for UI copy; first person plural ("we") for company content` |
| Sentence length    | `TODO: e.g. Prefer short sentences (≤ 20 words) in UI copy`                                    |
| Error messages     | `TODO: e.g. State what happened, why it matters, and what to do next — never blame the user`   |
| CTA labels         | `TODO: e.g. Use specific verbs: "Save changes", not "Submit"; "Delete account", not "OK"`      |
| Inclusive language | `TODO: e.g. Use gender-neutral terms; avoid ableist metaphors`                                 |

---

## Design System Reference

| Resource                      | URL or path                                           |
| ----------------------------- | ----------------------------------------------------- |
| Component library / Storybook | `TODO: e.g. https://design.example.com`               |
| Figma workspace               | `TODO: e.g. https://figma.com/file/...`               |
| Icon library                  | `TODO: e.g. Lucide Icons — https://lucide.dev`        |
| Design token source file      | `TODO: e.g. /design-tokens/tokens.json`               |
| Brand guidelines PDF          | `TODO: e.g. https://brand.example.com/guidelines.pdf` |
