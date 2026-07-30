# OpenMynd Brand Assets

Place app logo assets here so Angular includes them in the production build.

Expected files:

- `openmynd-logo-light.svg`, `openmynd-logo-light.png`, or `openmynd-logo-light.jpg`
- `openmynd-logo-dark.svg`, `openmynd-logo-dark.png`, or `openmynd-logo-dark.jpg`

Usage intent:

- Light logo: shown on dark backgrounds.
- Dark logo: shown on light backgrounds.
- Keep source artwork outside the app only if it contains editable design metadata; commit
  only the optimized runtime asset.

Do not rename these files after wiring them into the shell without updating the top-bar,
side-nav, login, and metadata references.
