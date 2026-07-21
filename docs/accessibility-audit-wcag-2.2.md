# WCAG 2.2 AA Accessibility Audit

Audit date: 21 July 2026  
Target: WCAG 2.2 Level A and AA  
Scope: authentication, application shell/navigation, entry list/calendar/search,
entry create/edit/detail, settings, import/export, dialogs, and responsive themes.

This is the single working accessibility record for issue `#52`. It records source
inspection, implemented remediation, automated checks, and the remaining manual or
follow-on work. Do not create a second accessibility handoff document for this issue.

## Method

- Inspected Angular templates and component styles for semantic structure, accessible
  names, keyboard behavior, focus handling, status announcements, target sizing,
  dialog behavior, and theme-token use.
- Compared shared controls against `.github/skills/enforce-platform-ux/SKILL.md`.
- Used the W3C WCAG 2.2 standard and Understanding documents as the authority:
  [WCAG 2.2](https://www.w3.org/TR/WCAG22/),
  [Keyboard](https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html), and
  [Focus Not Obscured](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html).
- Ran frontend lint, production build, focused unit tests, and Playwright smoke tests.
- Manual screen-reader, 200% zoom, and multi-viewport results remain explicit below;
  source inspection alone is not treated as full conformance proof.

## Remediated Findings

| ID | Severity | WCAG | Area | Finding and resolution |
| --- | --- | --- | --- | --- |
| A11Y-001 | Blocking | 2.4.1 A | App shell | No bypass mechanism existed. Added a keyboard-visible skip link targeting the main content landmark. |
| A11Y-002 | Major | 2.4.2 A | All routes | Browser titles did not identify the current route. Added descriptive Angular route titles for public, entry, profile, and settings routes. |
| A11Y-003 | Major | 1.3.1 A, 2.4.6 AA | Primary pages | Authentication, entries, create/edit, detail, and profile lacked consistent level-one page headings. Added or corrected page headings without changing visual hierarchy. |
| A11Y-004 | Blocking | 2.1.1 A, 4.1.2 A | Top-bar search | Recent-search rows were pointer-only `div` elements. Replaced the selection action with a semantic button while preserving a separate remove action. |
| A11Y-005 | Blocking | 2.1.1 A, 4.1.2 A | Entry timeline | Month choices were pointer-only `div` elements. Replaced them with buttons, disabled future months, exposed selection through `aria-current`, and added descriptive accessible names. |
| A11Y-006 | Blocking | 2.1.1 A, 4.1.2 A | Search results | Result cards could only expand by pointer. Added button semantics, keyboard activation, accessible names, and expanded state. |
| A11Y-007 | Major | 3.3.2 A, 4.1.2 A | Global search | Search controls relied on placeholder/icon context. Added explicit accessible names to the search input and submit control. |
| A11Y-008 | Major | 1.4.3 AA, 4.1.3 AA | Authentication | Login/register feedback was not consistently announced and used light-only hardcoded colours. Added alert/status semantics, autocomplete purposes, test hooks, and shared light/dark tokens. |
| A11Y-009 | Major | 2.4.7 AA | Calendar/import | Focus styling was removed from an important-day link and the import drop zone. Restored the shared focus outline and prevented Space from scrolling while activating file selection. |
| A11Y-010 | Major | 4.1.2 A, 2.1.1 A | Calendar | A custom button-like calendar cell contained separate event buttons. Converted the cell to a structural container and added a discrete semantic day-action button. |
| A11Y-011 | Major | 4.1.2 A | Notifications | Focusable notification articles acted as buttons while containing other actions. Kept articles structural and added an explicit keyboard-operable mark-read action. |

## Open Findings

These items should remain in `#52` until remediated or be moved into narrowly scoped
follow-up issues before `#52` closes.

| ID | Severity | WCAG | Area | Required follow-up |
| --- | --- | --- | --- | --- |
| A11Y-012 | Major | 1.4.3 AA, 1.4.11 AA | Search/import/important days | Legacy component styles still contain many route-local colour literals. Migrate semantic surfaces to shared tokens and verify every text, boundary, icon, hover, selected, and disabled pair in both themes with a contrast tool. |
| A11Y-013 | Major | 2.4.11 AA, 1.4.10 AA | Overlays and responsive layout | Manually verify notification, calendar preview, transcript, and import-review overlays at 200% zoom and short viewport heights. Confirm focused controls remain visible and no horizontal page overflow occurs. |
| A11Y-014 | Advisory | Process | Automated coverage | Add `axe-core` Playwright checks for public routes and authenticated representative routes. Current lint/build/smoke coverage does not calculate contrast or validate the accessibility tree comprehensively. |

## Manual Verification Matrix

Status values: `Pending` means the behavior requires an interactive browser or assistive
technology check before issue closure.

| Journey | Keyboard | 200% zoom | Light/dark | Screen reader |
| --- | --- | --- | --- | --- |
| Login and registration | Pending | Pending | Pending | Pending |
| Top bar, search history, notifications, side navigation | Pending | Pending | Pending | Pending |
| Entry cards, timeline, calendar, and preview decks | Pending | Pending | Pending | Pending |
| Create/edit/detail including attachments and AI progress | Pending | Pending | Pending | Pending |
| Customisation, important days, import, and export | Pending | Pending | Pending | Pending |
| Dialogs, transcript viewer, and destructive confirmations | Pending | Pending | Pending | Pending |

## Automated Validation

| Check | Result |
| --- | --- |
| `cd client && npm run lint` | Passed |
| `cd client && npm run build` | Passed; existing unused `autosave.service.ts` warning remains |
| `cd client && npm run test:e2e:smoke` | Passed, 2 tests |
| Focused login unit spec | Inconclusive: the corrected harness compiled, but Chrome Headless disconnected on the rerun before executing tests due to the repository's recurring Karma ping timeout |

## Exit Criteria

- No unresolved Blocking finding.
- Major findings are fixed or represented by accepted, scoped GitHub follow-up issues.
- Keyboard-only smoke passes for all journeys above.
- Focus remains visible and unobscured at desktop and compact widths and 200% zoom.
- Light/dark contrast is verified rather than inferred from theme appearance.
- VoiceOver or NVDA confirms page titles, headings, form errors, status updates, dialogs,
  and custom controls expose useful names, roles, values, and state.
