# Testing And Validation

## Confirmed commands

### Backend

```bash
cd server
source venv/bin/activate
pytest
```

### Frontend

```bash
cd client
npm test
npm run build
```

## Run selection

- Backend route or service changes:
  run `cd server && pytest`
- Frontend component or service changes:
  run at least the relevant frontend tests; consider `npm run build` for route or template changes
- Cross-cutting changes:
  run both backend and frontend checks that are available

## Commands requiring confirmation first

- `cd client && npm run lint`
  Defined in `package.json`, but no `lint` target is visible in `angular.json`.
- `cd client && npm run test:e2e:smoke`
  Defined in `package.json`, but Playwright config and test files are not visible in the current repository snapshot.

## Validation reminders

- Check route imports carefully because source drift already exists.
- Treat backend startup behaviour as part of validation when touching app initialisation.
- When a command cannot be run reliably, report that clearly in the final summary.
