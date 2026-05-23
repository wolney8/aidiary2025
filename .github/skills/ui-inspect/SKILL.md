---
name: ui-inspect
description: "Use when reviewing UI components, checking design specifications, inspecting visual mockups, validating layouts, comparing implementation against design files, or auditing component accessibility."
---

# UI Inspection

## When to Use

- Checking whether an implemented component matches its design spec or mockup
- Validating spacing, typography, and colour tokens against a design system
- Auditing a UI for WCAG 2.2 accessibility compliance
- Reviewing Figma exports or design documentation before implementation

## Procedure

### 1. Gather the Spec

- If a Figma or design file URL is provided, use the `web` tool to fetch it.
- Use `context7` to look up component specifications from the design system docs.
- Check the repository for any `design-tokens.*`, `theme.*`, or `*.figma.json` files.

### 2. Inspect the Implementation

- Read the relevant component source files (JSX/TSX, HTML, CSS/SCSS, Tailwind classes).
- Identify all spacing values, colour references, font sizes, and border radii in use.

### 3. Cross-Reference

- Compare each visual property against the spec or design token.
- Flag deviations: wrong colour value, incorrect spacing scale step, missing state (hover, focus, disabled).

### 4. Accessibility Check

- Refer to the `wcag-accessibility` instructions for the full WCAG 2.2 checklist.
- Verify colour contrast meets 4.5:1 (normal text) or 3:1 (large text / UI components).
- Confirm interactive elements meet the 24×24 px minimum target size (SC 2.5.8).
- Confirm focus indicators are visible and not obscured (SC 2.4.11).

### 5. Report Gaps

Output a structured list:

```
Component: <name>
File: <path>:<line>
Issue: <description>
Spec: <expected value>
Actual: <current value>
Severity: blocking | warning
```
