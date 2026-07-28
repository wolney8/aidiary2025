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
| A11Y-012 | Major | 1.4.3 AA, 1.4.11 AA | Search/import/important days | Migrated legacy semantic surfaces, state text, boundaries, and category accents to shared light/dark theme tokens. Intentional elevation shadows also use shared tokens rather than route-local palettes. |
| A11Y-014 | Advisory | Process | Automated coverage | Added `@axe-core/playwright` checks for login, registration, entry list in both themes, entry creation, populated search, Import, and Important Days. The exact Angular CDK focus-trap sentinel is excluded while `aria-hidden-focus` remains active elsewhere. The gate identified and remediated a hidden but keyboard-focusable Import file input. |
| A11Y-015 | Major | 1.4.3 AA, 3.2.3 AA, 4.1.2 A | Settings/create/calendar | Refreshed the axe route matrix after Settings and Important Days route changes. Fixed active Settings pill contrast in dark mode, labelled the embedded Important Day image file input, and updated On This Day preview coverage to use current-date calendar behavior. |
| A11Y-016 | Major | 1.4.10 AA, 1.4.12 AA, 4.1.2 A | Cards and overlays | Added an automated WCAG text-spacing and horizontal-overflow gate for notification, monthly Important Day, Thought Record, image-modal, and On This Day overlays. The gate caught a nested interactive Cards view pattern; cards are now structural and use explicit open actions instead of exposing the whole card as a button containing child buttons. |
| A11Y-017 | Major | 2.1.1 A, 2.4.3 A, 2.4.7 AA | Shell and calendar previews | Added a compact keyboard journey covering search expansion and submission, notification open/Escape close, and monthly Important Day, Thought Record, and On This Day preview open/Escape close. The gate caught compact search focus timing; the search input is now focused after the expanded compact search field renders. |
| A11Y-018 | Major | 1.4.10 AA, 1.4.12 AA, 4.1.2 A | Import review | Added stable test IDs and automated WCAG text-spacing/horizontal-overflow coverage for the staged import review modal at a short viewport. |

## Open Findings

These items should remain in `#52` until remediated or be moved into narrowly scoped
follow-up issues before `#52` closes.

| ID | Severity | WCAG | Area | Required follow-up |
| --- | --- | --- | --- | --- |
| A11Y-013 | Major | 2.4.11 AA, 1.4.10 AA | Overlays and responsive layout | Automated text-spacing and horizontal-overflow coverage now exists for notification, calendar preview, image, and import-review overlays. Still manually verify transcript overlays at 200% zoom and short viewport heights, and confirm focused controls remain visible. |

## Standards Coverage

| WCAG criterion | Result | Evidence / residual check |
| --- | --- | --- |
| 1.1.1 Non-text Content | Pass by inspection | Meaningful image alternatives and decorative icon treatment reviewed; confirm with screen reader. |
| 1.3.1 Info and Relationships | Pass by inspection | Page headings, landmarks, labels, groups, and tables use semantic structure. |
| 1.3.2 Meaningful Sequence | Pass by inspection | DOM and visual order remain aligned in primary journeys. |
| 1.3.4 Orientation | Pass by inspection | No route forces one device orientation. |
| 1.3.5 Identify Input Purpose | Pass | Authentication fields expose autocomplete purposes. |
| 1.4.1 Use of Colour | Pass by inspection | Selected/error states pair colour with text, icon, weight, or boundary changes. |
| 1.4.3 Contrast Minimum | Automated pass on representative routes | Axe passes light/dark representative routes; manually verify data-dependent states. |
| 1.4.4 Resize Text | Pending manual | Verify all scoped journeys at 200% zoom. |
| 1.4.10 Reflow | Partial automated pass | Notification, calendar preview, image, and import-review overlays are covered by the text-spacing overflow gate; complete short-viewport manual checks for transcript overlays. |
| 1.4.11 Non-text Contrast | Automated pass on representative routes | Shared state/border tokens are now used in audited legacy components. |
| 1.4.12 Text Spacing | Partial automated pass | Notification, calendar preview, image, and import-review overlays are covered by the WCAG text-spacing gate; complete manual route smoke for remaining transcript overlays. |
| 2.1.1 Keyboard | Partial automated pass | Pointer-only timeline, search, and calendar controls were remediated; compact shell and monthly preview keyboard journeys now run in Playwright. Complete full-route manual keyboard smoke. |
| 2.1.2 No Keyboard Trap | Pass by source inspection | Material dialogs trap and restore focus; complete overlay smoke. |
| 2.4.1 Bypass Blocks | Pass | Keyboard-visible skip link targets the main landmark. |
| 2.4.2 Page Titled | Pass | Angular routes define descriptive titles. |
| 2.4.3 Focus Order | Partial automated pass | Compact shell and monthly preview keyboard journeys now run in Playwright. Verify forms, detail pages, and transcript dialogs manually. |
| 2.4.6 Headings and Labels | Pass by inspection | Primary pages expose descriptive level-one headings and labelled controls. |
| 2.4.7 Focus Visible | Partial automated pass | Shared focus outline restored for custom controls; compact keyboard path is covered. Complete visual focus smoke across remaining forms and dialogs. |
| 2.4.11 Focus Not Obscured | Pending manual | Verify sticky/scrolling overlays at 200% zoom and short heights. |
| 2.5.8 Target Size Minimum | Pass by inspection | Primary actions use Material targets; confirm compact layouts manually. |
| 3.2.3 Consistent Navigation | Pass by inspection | Shared top bar and side navigation remain consistent across authenticated routes. |
| 3.3.1 Error Identification | Pass by inspection | Auth/import/create errors use labelled inline or alert/status feedback. |
| 3.3.2 Labels or Instructions | Pass by inspection | Inputs use visible labels; placeholders are supplementary. |
| 4.1.2 Name, Role, Value | Automated pass on representative routes | Axe passes after excluding only the framework-owned CDK focus sentinel. |
| 4.1.3 Status Messages | Pass by inspection | Loading, import, notification, and validation status regions expose live/status semantics where required. |

## Wireframe Gap Analysis

| Wireframe area | Current implementation | Accessibility gap status |
| --- | --- | --- |
| Global shell | Responsive top bar, overlay navigation, skip link, search, account, theme, and notifications are implemented. | Automated representative check passes; keyboard/zoom smoke remains. |
| Timeline scroller | Semantic month buttons expose current/disabled state and use shared control styling. | Source and automated checks pass on the empty entries route. |
| Entry card grid | Daily, dream, thought-record, attachment, and image states extend the original card hierarchy. | Data-dependent card states require final manual light/dark and zoom review. |
| Entry detail | Hero media, attachment controls, metadata, linked reflections, and actions extend the mapped detail layout. | Dialog, expanded image, transcript, and focus-restoration smoke remains. |
| Search results | Keyboard-expandable cards, semantic status states, and tokenised surfaces preserve the mapped result hierarchy. | Test with populated results and 200% zoom remains. |
| Side navigation | Existing destinations and close behavior match the shell mapping. | Keyboard order and focus return require final manual confirmation. |
| Visual theme | Shared semantic tokens now cover audited search/import/important-day legacy states in light and dark modes. | Manual contrast review remains for data-dependent and overlay states. |

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
| `cd client && npm run test:e2e:a11y` | Passed, 18 axe/reflow/keyboard checks across public/authenticated routes, entry filters, entry creation, On This Day previews, populated search, Settings, standalone Important Days, notification overlays, monthly preview decks, import review modal, compact shell keyboard behavior, and light/dark representative routes |
| Focused login unit spec | Inconclusive: the corrected harness compiled, but Chrome Headless disconnected on the rerun before executing tests due to the repository's recurring Karma ping timeout |

## Exit Criteria

- No unresolved Blocking finding.
- Major findings are fixed or represented by accepted, scoped GitHub follow-up issues.
- Keyboard-only smoke passes for all journeys above.
- Focus remains visible and unobscured at desktop and compact widths and 200% zoom.
- Light/dark contrast is verified rather than inferred from theme appearance.
- VoiceOver or NVDA confirms page titles, headings, form errors, status updates, dialogs,
  and custom controls expose useful names, roles, values, and state.
