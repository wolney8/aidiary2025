# OpenMynd Brand Assets

Place app logo assets here so Angular includes them in the production build.

Expected files:

- `openmynd-logo-light.svg` or `openmynd-logo-light.png`
- `openmynd-logo-dark.svg` or `openmynd-logo-dark.png`

Usage intent:

- Light logo: shown on dark backgrounds.
- Dark logo: shown on light backgrounds.
- Keep source artwork outside the app only if it contains editable design metadata; commit
  only the optimized runtime asset.

Do not rename these files after wiring them into the shell without updating the top-bar,
side-nav, login, and metadata references.
