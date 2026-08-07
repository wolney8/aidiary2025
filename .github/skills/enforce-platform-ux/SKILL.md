---
name: enforce-platform-ux
description: Use for every user-facing frontend change in AI Diary, including pages, routes, dialogs, cards, rows, tables, forms, controls, text, icons, responsive states, and themes. Enforces platform consistency, Material Design 3 patterns, pill-shaped compact affordances, and WCAG 2.2 AA checks before implementation and sign-off.
---

# Enforce Platform UX

Apply this skill before editing user-facing UI and repeat the review before handoff.

## 1. Establish The Existing Pattern

1. Inspect the target component, its parent layout, adjacent screens, shared components,
   and `client/src/styles.scss` tokens.
2. Reuse an established AI Diary pattern when it meets the requirement. Do not create a
   one-off component, icon treatment, spacing system, or colour when a shared equivalent
   exists.
3. Record the expected desktop, narrow-screen, light-theme, dark-theme, loading, empty,
   error, disabled, hover, focus, and selected states relevant to the change.
4. Check route entry, route exit, browser back, saved query/date state, guards, and page
   title/heading behavior when navigation is affected.

## 2. Apply Platform Rules

### Layout and visibility

- Use a clear page hierarchy: one primary heading, grouped content, stable actions, and
  predictable reading/tab order.
- Align related controls to the same grid and spacing rhythm. Avoid isolated offsets and
  magic positioning used to compensate for an incorrect container.
- Use the repository spacing tokens for component padding and gaps. Adjacent actions must
  declare at least `var(--spacing-xs)` between their visible boundaries; never assume a
  Material action container supplies spacing automatically.
- Give repeated cards and rows consistent header, content, and action padding so wrapped
  titles or additional actions do not shift equivalent controls out of alignment.
- Keep content responsive without horizontal page overflow. Verify compact, medium, and
  large layouts; do not merely hide required actions at narrower widths.
- Keep loading, empty, error, and success states in the same layout region as the content
  they replace to prevent page jumps.
- Never leave hidden controls focusable or expose content that is visually clipped.

### Material 3 components and shape

- Prefer Angular Material components and Material 3 interaction/state behavior over
  custom imitations.
- Use `var(--radius-pill)` for chips, tags, filters, status labels, compact segmented
  choices, and suitable compact action buttons. Prefer these pill affordances over
  sharp rectangular boxes.
- Treat button shape and state styling as shared platform primitives. Before adding
  component CSS, inspect global button, icon-button, button-toggle, and paginator rules.
  Do not duplicate those rules per route.
- Do not turn cards, dialogs, tables, text fields, media frames, or page sections into
  pills. Use `--radius-sm`, `--radius-md`, or `--radius-lg` according to their container
  hierarchy.
- Give one action clear primary emphasis. Destructive actions use the established red
  treatment; cancel/back remains visually safe.
- Use app-native dialogs for in-app confirmation and alerts. Keep browser prompts only
  for refresh or tab-close protection.
- App-native dialogs must use the shared Material 3 dialog primitive unless there is a
  documented reason not to. Dialog surfaces use rounded M3 container corners, consistent
  padding, one clear title/message hierarchy, and action buttons aligned to the same
  baseline.

### Modals, rows, and tables

- Dialogs require a concise accessible title, bounded width, scrollable content with a
  visible close path, focus trap/restoration, Escape behavior, and actions that remain
  reachable at 200% zoom and short viewport heights.
- Dialog leading icons must be optically centred inside their circular container and
  aligned with the title/message block. Do not ship a dialog where the icon, title,
  message, or action labels appear vertically offset from their visual row.
- Rows require consistent leading icon/avatar, text hierarchy, metadata alignment, and
  trailing actions. Avoid controls overlapping wrapping titles.
- Use semantic tables for genuinely tabular data, with headers and keyboard-accessible
  actions. Provide a deliberate narrow-screen treatment rather than shrinking text or
  clipping columns.

### Text and iconography

- Use concise labels and helper text. Do not restate obvious product context or rely on
  placeholders as labels.
- Use `mat-icon` and the repository's Material icon family. Do not mix icon libraries or
  use arbitrary Unicode symbols.
- Default icon sizes to the established 18, 20, or 24 px scale. Decorative icons are
  hidden from assistive technology; icon-only controls have an accessible name and
  tooltip where the action is not self-evident.
- Keep paired leading/trailing icons optically aligned and equally inset from container
  edges.
- For every icon-plus-text control, verify the icon and label share the same visual
  centreline. Prefer shared button label alignment rules over component-local margins.
- For Angular Material buttons, verify both DOM shapes: icons inside `.mdc-button__label`
  and icons projected as direct siblings before/after `.mdc-button__label`. Neither may
  render as `<icon>Label` or `Label<icon>` without visible token spacing.
- Do not rely on Angular Material's generated DOM classes as the only alignment fix. If
  a generated wrapper must be targeted, keep the selector broad enough to protect the
  shared Material primitive across Login, Register, dialogs, cards, tables, and settings.

### Stable inspection and test hooks

- Give user-visible components descriptive, feature-scoped class names that describe
  purpose, such as `chat-message-thread` or `import-review-table`. Do not use generated
  Angular Material classes, DOM position, or visual appearance as the component's public
  inspection vocabulary.
- Add stable `data-testid` attributes to primary surfaces, controls, state containers,
  rows, tables, and modal boundaries that automated tests or user feedback must identify.
  Use lowercase kebab-case prefixed by the feature, such as `chat-open-button`.
- Keep `data-testid` independent of translated labels and CSS. Never style from it, and
  do not add IDs to every decorative wrapper; hooks should identify meaningful boundaries.
- Prefer semantic elements and accessible names first. A test ID supplements correct
  roles, labels, and structure; it never replaces them.

### Theme and CSS

- Use repository colour, surface, text, border, radius, and shadow variables. Do not
  hardcode white, black, or light-only surfaces in component CSS.
- Verify every changed surface in light and dark themes, including Material overlays
  rendered outside the component tree: dialogs, menus, selects, tooltips, and snackbars.
- Prefer component-owned styles and shared tokens over broad `!important` overrides.
  Add a global override only when an Angular Material overlay or truly shared primitive
  requires it.
- Preserve readable image overlays with a theme-appropriate gradient and sufficient text
  contrast.

### Shared-control consistency check

For every changed reusable control, compare this state matrix in both themes:

| State | Required distinction |
| --- | --- |
| Enabled | Clearly interactive surface and readable label/icon |
| Hover | Visible state layer without layout movement |
| Selected/current | Strong fill plus non-colour indicator such as weight or border |
| Focused | Unclipped focus outline |
| Disabled/future | Lower emphasis while remaining legible and non-interactive |

- Check the same primitive wherever it appears: list, calendar, search, settings,
  create/edit, detail, import/export, and overlays.
- Segmented filters and view choices must use one rounded group silhouette with no sharp
  outer corners. Selected and available choices must never collapse into the same grey.
- Text actions use pill geometry. Icon-only actions remain circular and centre the
  Material icon within a 48px touch target.
- Pagination uses one shared rounded surface at both the top and bottom of content and
  must blend with the page background in light and dark themes.
- Cards, tables, dialogs, form fields, media frames, and page sections are rounded
  containers, not pills. Do not distort content containers to satisfy a button rule.

## 3. Enforce WCAG 2.2 AA

- Support keyboard-only operation with logical tab order, visible focus, and no keyboard
  trap. Enter and Space activate controls according to their semantics.
- Meet contrast ratios: 4.5:1 for normal text and 3:1 for large text, UI boundaries, and
  meaningful graphics. Do not convey state by colour alone.
- Use semantic HTML before ARIA. Keep names, roles, states, errors, and status updates
  available to assistive technology.
- Maintain at least the WCAG 24 by 24 CSS px target minimum and prefer the platform's
  44-48 px touch target for primary controls.
- Support 200% zoom, text wrapping, reduced motion, and usable focus within scrolling
  containers.

## 4. Review Gate

Before handoff:

1. Inspect the actual diff for one-off CSS, hardcoded colours, duplicated components,
   inconsistent labels, touching controls, uneven container padding, mixed icon styles,
   and desktop-only assumptions.
2. Compare the result with the nearest equivalent AI Diary screen, including icon/text
   baseline alignment in buttons, rows, cards, top-bar actions, and dialogs.
3. Run the applicable frontend build, tests, lint, and smoke checks from
   `docs/playbooks/testing-and-validation.md`.
4. Manually verify affected routes at compact and desktop widths, in light and dark
   themes, using keyboard navigation and 200% zoom.
5. Report any state or viewport not tested. Do not describe a UI slice as signed off
   while a known contrast, focus, overflow, route, or modal-access issue remains.
